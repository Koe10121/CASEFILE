"""Games in memory, keyed by an unguessable ID (D46).

Each game has its own lock. A turn with a local model can take seconds, and a second
request for the same game in that time (a double click, a second tab) must not
interleave with the first: ``GameSession`` is not thread-safe, and the reveal check
must see the state the briefing was built from. So a busy game refuses the second
request instead of queueing it. Different games never wait for each other.

Persistence (save/resume across server restarts) is the next step; the game log is
already all a game needs to be rebuilt (D25).
"""

import secrets
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

from casefile.session import GameSession

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
        new_session: Callable[[], GameSession],
        *,
        max_games: int,
        idle_ttl_s: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._new_session = new_session
        self._max_games = max_games
        self._idle_ttl_s = idle_ttl_s
        self._clock = clock
        self._games: dict[str, StoredGame] = {}
        self._lock = threading.Lock()

    def create(self, difficulty: Difficulty) -> str:
        with self._lock:
            self._drop_idle()
            if len(self._games) >= self._max_games:
                raise StoreFullError("the server is full; try again later")
            game_id = secrets.token_urlsafe(16)
            self._games[game_id] = StoredGame(self._new_session(), difficulty, self._clock())
            return game_id

    @contextmanager
    def use(self, game_id: str) -> Iterator[StoredGame]:
        """Hold one game for the length of a request."""
        with self._lock:
            self._drop_idle()
            game = self._games.get(game_id)
            if game is None:
                raise GameNotFoundError(game_id)
            if not game.lock.acquire(blocking=False):
                raise GameBusyError(game_id)
        try:
            yield game
        finally:
            game.last_used = self._clock()
            game.lock.release()

    def __len__(self) -> int:
        return len(self._games)

    def _drop_idle(self) -> None:
        """Forget games nobody has touched for a while. A busy game is never dropped."""
        cutoff = self._clock() - self._idle_ttl_s
        for game_id, game in list(self._games.items()):
            if game.last_used < cutoff and not game.lock.locked():
                del self._games[game_id]
