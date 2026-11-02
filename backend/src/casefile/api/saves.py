"""Saved games on disk, in one SQLite file (D53).

A game is saved after every request that touches it, so closing the browser, a server
restart or the two-hour idle drop no longer loses it. What is saved is the game's log
and transcript (``SavedGame``), never its state: loading replays the log through the
engine, so a saved game is only ever a game the rules could have produced.

SQLite comes with Python, needs no server, and keeps a local game free to run. Each
call opens its own short connection, so FastAPI's worker threads never share one.
"""

import sqlite3
import time
from collections.abc import Callable, Iterator
from contextlib import closing, contextmanager
from pathlib import Path
from typing import get_args

from pydantic import ValidationError

from casefile.session import SavedGame

from .schemas import Difficulty

_SCHEMA = """
CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    difficulty TEXT NOT NULL,
    data TEXT NOT NULL,
    saved_at REAL NOT NULL
)
"""


class SaveFile:
    def __init__(
        self,
        path: Path,
        case_id: str,
        *,
        keep_days: float,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._path = path
        self._case_id = case_id
        self._keep_s = keep_days * 86_400
        self._clock = clock
        with self._connect() as db:
            db.execute(_SCHEMA)
            db.execute("DELETE FROM games WHERE saved_at < ?", (clock() - self._keep_s,))

    def put(self, game_id: str, difficulty: Difficulty, saved: SavedGame) -> None:
        with self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO games VALUES (?, ?, ?, ?, ?)",
                (game_id, self._case_id, difficulty, saved.model_dump_json(), self._clock()),
            )

    def get(self, game_id: str) -> tuple[Difficulty, SavedGame] | None:
        """The saved game, or ``None`` if there is none for this case, it is older than
        the keep time, or it no longer reads (saved by an older version)."""
        with self._connect() as db:
            row = db.execute(
                "SELECT difficulty, data FROM games WHERE id = ? AND case_id = ? AND saved_at >= ?",
                (game_id, self._case_id, self._clock() - self._keep_s),
            ).fetchone()
        if row is None:
            return None
        difficulty, data = row
        if difficulty not in get_args(Difficulty):
            return None
        try:
            return difficulty, SavedGame.model_validate_json(data)
        except ValidationError:
            return None

    def delete(self, game_id: str) -> None:
        with self._connect() as db:
            db.execute("DELETE FROM games WHERE id = ?", (game_id,))

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        with closing(sqlite3.connect(self._path, timeout=10)) as db, db:
            yield db
