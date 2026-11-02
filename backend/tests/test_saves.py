"""Save and resume (D53): a game survives the browser closing, the idle drop and a
server restart, and a save can never hold a game the rules wouldn't reach."""

import sqlite3
from collections.abc import Sequence
from pathlib import Path

import pytest

from casefile.ai.contract import Exchange, NpcReply, NpcTurn, Usage
from casefile.ai.mock import MockNpc
from casefile.api.saves import SaveFile
from casefile.api.store import GameStore
from casefile.case import CaseBundle
from casefile.case.ids import CharacterId, EvidenceId, LocationId
from casefile.engine import Engine, IllegalActionError
from casefile.engine.actions import SearchLocation
from casefile.engine.briefing import SuspectBriefing
from casefile.session import GameSession, SavedGame

from .test_api import act, make_client, new_game, ok

RICHARD = CharacterId("S_RICHARD")


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def engine(blackwood: CaseBundle) -> Engine:
    return Engine(blackwood)


def played(engine: Engine) -> GameSession:
    session = GameSession(engine, MockNpc(), detective="man")
    session.talk_to(RICHARD)
    session.ask("Where were you tonight?")
    session.search(LocationId("LOC_OFFICE"))
    session.show(EvidenceId("E07"))
    return session


def test_a_resumed_game_is_the_same_game(engine: Engine) -> None:
    session = played(engine)
    saved = SavedGame.model_validate_json(session.save().model_dump_json())
    back = GameSession.resume(engine, MockNpc(), None, saved)
    assert back.state == session.state
    assert back.transcripts == session.transcripts
    assert back.current_suspect == RICHARD
    assert back.detective == "man"
    back.ask("What were you doing in the office?")  # and play goes on


class Billing:
    """Costs 1,000 tokens a question."""

    def respond(
        self, briefing: SuspectBriefing, history: Sequence[Exchange], player_text: str
    ) -> NpcTurn:
        return NpcTurn(
            reply=NpcReply(demeanor="tired", dialogue="No."),
            usage=Usage(input_tokens=900, output_tokens=100),
        )


def test_resuming_does_not_refill_the_token_budget(engine: Engine) -> None:
    session = GameSession(engine, Billing(), token_budget=1000)
    session.talk_to(RICHARD)
    session.ask("Where were you?")
    back = GameSession.resume(engine, Billing(), 1000, session.save())
    assert back.tokens_used == 1000
    with pytest.raises(IllegalActionError):
        back.ask("And then?")


def test_a_log_that_breaks_the_rules_does_not_load(engine: Engine) -> None:
    session = played(engine)
    saved = session.save()
    tampered = saved.model_copy(
        update={"log": (SearchLocation(location=LocationId("LOC_NOWHERE")),)}
    )
    with pytest.raises(IllegalActionError):
        GameSession.resume(engine, MockNpc(), None, tampered)


# ------------------------------------------------------------------ the save file


def test_a_game_survives_a_server_restart(blackwood: CaseBundle, tmp_path: Path) -> None:
    path = tmp_path / "games.sqlite3"
    with make_client(blackwood, saves=SaveFile(path, "blackwood-001", keep_days=30)) as first:
        game_id = new_game(first)
        ok(act(first, game_id, "talk", {"suspect": "S_RICHARD"}))
        ok(act(first, game_id, "ask", {"text": "Where were you?"}))
        before = ok(first.get(f"/api/games/{game_id}"))

    with make_client(blackwood, saves=SaveFile(path, "blackwood-001", keep_days=30)) as second:
        assert ok(second.get(f"/api/games/{game_id}")) == before
        ok(act(second, game_id, "search", {"location": "LOC_OFFICE"}))
        ok(act(second, game_id, "show", {"evidence": "E07"}))

    with make_client(blackwood, saves=SaveFile(path, "blackwood-001", keep_days=30)) as third:
        statements = ok(third.get(f"/api/games/{game_id}"))["statements"]
        assert any(s["caught"] for s in statements)


def test_without_a_save_file_a_restart_loses_the_game(blackwood: CaseBundle) -> None:
    with make_client(blackwood) as first:
        game_id = new_game(first)
    with make_client(blackwood) as second:
        assert second.get(f"/api/games/{game_id}").status_code == 404


def test_old_saves_are_deleted(blackwood: CaseBundle, tmp_path: Path) -> None:
    path, clock = tmp_path / "games.sqlite3", Clock()
    with make_client(
        blackwood, saves=SaveFile(path, "blackwood-001", keep_days=1, clock=clock)
    ) as c:
        game_id = new_game(c)
    clock.now += 2 * 86_400
    later = SaveFile(path, "blackwood-001", keep_days=1, clock=clock)
    assert later.get(game_id) is None
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT COUNT(*) FROM games").fetchone() == (0,)


def test_a_save_from_another_case_is_not_found(blackwood: CaseBundle, tmp_path: Path) -> None:
    path = tmp_path / "games.sqlite3"
    with make_client(blackwood, saves=SaveFile(path, "blackwood-001", keep_days=30)) as c:
        game_id = new_game(c)
    assert SaveFile(path, "another-case", keep_days=30).get(game_id) is None


def test_a_save_that_no_longer_replays_is_dropped(
    blackwood: CaseBundle, engine: Engine, tmp_path: Path
) -> None:
    saves = SaveFile(tmp_path / "games.sqlite3", "blackwood-001", keep_days=30)
    broken = played(engine).save()
    broken = broken.model_copy(
        update={"log": (*broken.log, SearchLocation(location=LocationId("LOC_NOWHERE")))}
    )
    saves.put("old-game", "normal", broken)
    with make_client(blackwood, saves=saves) as c:
        assert c.get("/api/games/old-game").status_code == 404
    assert saves.get("old-game") is None


def test_a_game_dropped_as_idle_is_loaded_again(engine: Engine, tmp_path: Path) -> None:
    clock = Clock()
    store = GameStore(
        lambda d: GameSession(engine, MockNpc(), detective=d),
        lambda saved: GameSession.resume(engine, MockNpc(), None, saved),
        saves=SaveFile(tmp_path / "games.sqlite3", "blackwood-001", keep_days=30),
        max_games=1,
        idle_ttl_s=60,
        clock=clock,
    )
    first = store.create("easy")
    with store.use(first) as game:
        game.session.talk_to(RICHARD)
    clock.now += 61
    store.create("normal")  # the first game leaves memory to make room
    clock.now += 61
    with store.use(first) as game:
        assert game.difficulty == "easy"
        assert game.session.current_suspect == RICHARD
    assert len(store) == 1
