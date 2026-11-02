"""Hints and the evidence picker (D54): help that depends on difficulty, never the truth."""

from dataclasses import replace

import pytest

from casefile.ai.mock import MockNpc
from casefile.case import CaseBundle
from casefile.case.ids import CharacterId, FactId, LieId, LocationId
from casefile.engine import Engine, IllegalActionError
from casefile.engine.hints import ALL_DONE, next_hint
from casefile.session import GameSession

from .test_api import act, make_client, new_game, ok

THOMAS = CharacterId("S_THOMAS")


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def engine(blackwood: CaseBundle) -> Engine:
    return Engine(blackwood)


def test_the_hint_follows_the_first_unfinished_step(engine: Engine) -> None:
    chain = engine.index.bundle.solution.solution_chain
    state = engine.new_game()
    assert next_hint(engine.index.bundle.solution, state) == chain[0].hint

    learned = state.known_facts | {FactId(f) for step in chain for f in step.learn}
    state = replace(state, known_facts=learned)
    assert next_hint(engine.index.bundle.solution, state) == chain[2].hint  # a lie to break

    caught = frozenset(LieId(s.breaks) for s in chain if s.breaks is not None)
    state = replace(state, caught_lies=caught)
    assert next_hint(engine.index.bundle.solution, state) == ALL_DONE


def test_hard_has_no_hints(engine: Engine) -> None:
    session = GameSession(engine, MockNpc())
    assert session.hints_left("none") == 0
    with pytest.raises(IllegalActionError, match="no hints"):
        session.hint("none")


def test_normal_gives_a_few_hints_on_request(engine: Engine) -> None:
    session = GameSession(engine, MockNpc())
    first = session.hint("on_request:2")
    assert first == engine.index.bundle.solution.solution_chain[0].hint
    with pytest.raises(IllegalActionError, match="already have"):
        session.hint("on_request:2")  # same step: refused, and not charged
    assert session.hints_left("on_request:2") == 1


def test_easy_unlocks_a_hint_after_minutes_without_progress(engine: Engine) -> None:
    clock = Clock()
    session = GameSession(engine, MockNpc(), clock=clock)
    assert session.hints_left("auto_after_minutes:5") is None
    clock.now += 4 * 60
    with pytest.raises(IllegalActionError, match="about 1 min"):
        session.hint("auto_after_minutes:5")

    session.talk_to(THOMAS)  # the opening statement teaches nothing, so no progress
    clock.now += 60
    assert session.hint("auto_after_minutes:5")
    assert session.hint_ready_at("auto_after_minutes:5") == clock.now + 300

    clock.now += 100
    session.search(LocationId("LOC_STUDY"))  # finds evidence: progress restarts the timer
    assert session.hint_ready_at("auto_after_minutes:5") == clock.now + 300


def test_hints_survive_save_and_resume(engine: Engine) -> None:
    session = GameSession(engine, MockNpc())
    session.hint("on_request:3")
    back = GameSession.resume(engine, MockNpc(), None, session.save())
    assert back.hints == session.hints
    assert back.last_progress_at == session.last_progress_at


# ------------------------------------------------------------------ over HTTP


def test_a_hint_over_http(blackwood: CaseBundle) -> None:
    with make_client(blackwood) as client:
        game_id = new_game(client, "normal")
        assert ok(client.get(f"/api/games/{game_id}"))["hints"] == {
            "given": [],
            "left": 3,
            "ready_at": None,
        }
        hints = ok(act(client, game_id, "hint", {}))["game"]["hints"]
        assert len(hints["given"]) == 1
        assert hints["left"] == 2

        hard = new_game(client, "hard")
        assert act(client, hard, "hint", {}).status_code == 409


@pytest.mark.parametrize(("difficulty", "picker"), [("easy", True), ("normal", False)])
def test_easy_marks_which_held_evidence_is_relevant(
    blackwood: CaseBundle, difficulty: str, picker: bool
) -> None:
    key = {i for g in blackwood.solution.key_evidence_groups for i in g.items}
    with make_client(blackwood) as client:
        game_id = new_game(client, difficulty)
        game = ok(act(client, game_id, "search", {"location": "LOC_STUDY"}))["game"]
        assert game["evidence"]
        for ev in game["evidence"]:
            assert ev["relevant"] == ((ev["id"] in key) if picker else None)
