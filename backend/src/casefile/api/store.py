"""Games in memory, keyed by an unguessable ID (D46).

Each game has its own lock. A turn with a local model can take seconds, and a second
request for the same game in that time (a double click, a second tab) must not
interleave with the first: ``GameSession`` is not thread-safe, and the reveal check
must see the state the briefing was built from. So a busy game refuses the second
request instead of queueing it. Different games never wait for each other.

With a ``SaveFile`` (D53), every request that touches a game saves it on the way out,
and a game that isn't in memory (dropped as idle, or the server restarted) is loaded
from the file by replaying its log. Memory is then only a cache of recent games.
"""

import secrets
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from casefile.engine.engine import IllegalActionError
from casefile.session import GameSession, PlayedBy, SavedGame

from .saves import SaveFile
from .schemas import Difficulty


class GameNotFoundError(Exception):
    """No game with this ID: never created, or expired."""


class GameBusyError(Exception):
    """Another request for this game is still running."""


class StoreFullError(Exception):
    """The server holds as many games as it may. Nothing was created."""


@dataclass
class StoredGame:
    session: GameSession
    difficulty: Difficulty
    last_used: float
    lock: threading.Lock = field(default_factory=threading.Lock)


class GameStore:
    def __init__(
        self,
        new_session: Callable[[str | None, PlayedBy], GameSession],
        resume_session: Callable[[SavedGame], GameSession],
        *,
        saves: SaveFile | None = None,
        max_games: int,
        idle_ttl_s: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._new_session = new_session
        self._resume_session = resume_session
        self._saves = saves
        self._max_games = max_games
        self._idle_ttl_s = idle_ttl_s
        self._clock = clock
        self._games: dict[str, StoredGame] = {}
        self._lock = threading.Lock()

    def create(
        self,
        difficulty: Difficulty,
        detective: str | None = None,
        *,
        played_by: PlayedBy = "server",
    ) -> str:
        with self._lock:
            self._make_room()
            session = self._new_session(detective, played_by)  # raises on an unknown identity
            game_id = secrets.token_urlsafe(16)
            game = StoredGame(session, difficulty, self._clock())
            self._games[game_id] = game
        self._save(game_id, game)
        return game_id

    @contextmanager
    def use(self, game_id: str) -> Iterator[StoredGame]:
        """Hold one game for the length of a request."""
        with self._lock:
            self._drop_idle()
            game = self._games.get(game_id) or self._load(game_id)
            if not game.lock.acquire(blocking=False):
                raise GameBusyError(game_id)
        try:
            yield game
        finally:
            try:
                self._save(game_id, game)
            finally:
                game.last_used = self._clock()
                game.lock.release()

    def __len__(self) -> int:
        return len(self._games)

    def _load(self, game_id: str) -> StoredGame:
        """Bring a saved game back into memory. Called with the store lock held."""
        found = self._saves.get(game_id) if self._saves is not None else None
        if found is None:
            raise GameNotFoundError(game_id)
        difficulty, saved = found
        self._make_room()
        try:
            session = self._resume_session(saved)
        except IllegalActionError:  # the case changed and the log no longer replays
            assert self._saves is not None
            self._saves.delete(game_id)
            raise GameNotFoundError(game_id) from None
        game = StoredGame(session, difficulty, self._clock())
        self._games[game_id] = game
        return game

    def _save(self, game_id: str, game: StoredGame) -> None:
        if self._saves is not None:
            self._saves.put(game_id, game.difficulty, game.session.save())

    def _make_room(self) -> None:
        self._drop_idle()
        if len(self._games) >= self._max_games:
            raise StoreFullError("the server is full; try again later")

    def _drop_idle(self) -> None:
        """Forget games nobody has touched for a while. A busy game is never dropped, and a
        saved one can be loaded again."""
        cutoff = self._clock() - self._idle_ttl_s
        for game_id, game in list(self._games.items()):
            if game.last_used < cutoff and not game.lock.locked():
                del self._games[game_id]
