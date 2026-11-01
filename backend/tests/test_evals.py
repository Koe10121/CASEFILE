"""The eval harness: its detectors, its scenario file, and a clean baseline in mock mode."""

from collections.abc import Sequence

import pytest

from casefile.ai.contract import Exchange, NpcReply, NpcTurn, ProviderError, Usage
from casefile.case import CaseBundle
from casefile.case.ids import CharacterId, FactId
from casefile.engine import Engine
from casefile.engine.briefing import SuspectBriefing
from casefile.evals.checks import forbidden, invented_times, lie_breaks, parroted
from casefile.evals.runner import (
    DEFAULT_SUITE,
    SetupError,
    run_scenario,
    run_suite,
    summarise,
)
from casefile.evals.scenarios import Ask, Scenario, Talk, load_suite
from casefile.settings import Settings

# ------------------------------------------------------------------ detectors


def test_invented_times_allow_given_times_in_either_clock() -> None:
    seen = "Richard smoked on the terrace from 22:15 to 22:30."
    assert invented_times("Terrace, from 10:15. Back by 22.30.", seen) == ()
    assert invented_times("I went to the office at 22:20.", seen) == ("22:20",)


def test_lie_breaks_skip_denials() -> None:
    patterns = [r"\boffice\b"]
    assert lie_breaks("The office? I never went near it.", patterns) == ()
    assert lie_breaks("Look, I didn't. Fine, I went to the office.", patterns) == (
        "Fine, I went to the office.",
    )


def test_forbidden_and_parroted() -> None:
    assert forbidden("As an AI, I can't.", [r"\bas an AI\b"]) == (r"\bas an AI\b",)
    line = "Look, everyone heard us. I'm not hiding it."
    assert parroted(f"Ha. {line}", [line]) == (line,)
    assert parroted("Everyone heard us arguing.", [line]) == ()


# ------------------------------------------------------------------ the suite


def test_suite_matches_the_case(blackwood: CaseBundle) -> None:
    """Every ID in the eval file is real, and each expected fact is one that suspect
    can reveal, so a typo can't make a model look worse than it is."""
    engine = Engine(blackwood)
    suite = load_suite(DEFAULT_SUITE)
    for sc in suite.scenarios:
        suspect = None
        for step in sc.steps:
            if isinstance(step, Talk):
                suspect = step.suspect
                assert suspect in engine.index.briefings, sc.id
            elif isinstance(step, Ask):
                assert suspect is not None, f"{sc.id}: ask before talk"
                b = engine.index.briefings[suspect]
                revealable = {*b.shares_freely, *(g.fact for g in b.gated)}
                assert set(step.expect_reveal) <= revealable, (sc.id, step.text)


def test_mock_baseline_is_clean() -> None:
    """The mock only ever says authored statements, so any flag other than a missed
    clue (it matches keywords, not meaning) is a bug in the harness or the engine."""
    results = run_suite(load_suite(DEFAULT_SUITE), "mock", Settings(), repeat=1)
    s = summarise("mock", results)
    assert s.turns > 20
    assert {flag for r in results for flag in r.flags} <= {"missed clue"}
    assert s.clue_hits > 0


# ------------------------------------------------------------------ a bad performance


class ConfessingRichard:
    """Everything the local model did wrong in Kole's first run, in one reply."""

    def respond(
        self, briefing: SuspectBriefing, history: Sequence[Exchange], player_text: str
    ) -> NpcTurn:
        return NpcTurn(
            reply=NpcReply(
                reveals=("F_MADE_UP", "F_RICHARD_OFFICE"),
                demeanor="hostile",
                dialogue="Look, everyone heard us. I'm not hiding it. "
                "I went to Arthur's office around 21:10.",
            ),
            usage=Usage(input_tokens=10, output_tokens=5, latency_ms=1200),
        )


def test_every_failure_is_flagged(blackwood: CaseBundle, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "casefile.evals.runner.make_provider", lambda ai, settings: (ConfessingRichard(), None)
    )
    scenario = Scenario(
        id="bad",
        about="",
        steps=(
            Talk(suspect=CharacterId("S_RICHARD")),
            Ask(
                text="Where were you?",
                expect_reveal=(FactId("F_RICHARD_TERRACE"),),
                must_not_say=(r"\boffice\b",),
            ),
        ),
    )
    (turn,) = run_scenario(Engine(blackwood), Settings(), "ollama", scenario, run=1)
    assert set(turn.flags) == {
        "invented ID",
        "gated ID",
        "invented time",
        "broke lie",
        "parroted",
        "missed clue",
    }
    assert turn.accepted == ()


class DownNpc:
    def respond(
        self, briefing: SuspectBriefing, history: Sequence[Exchange], player_text: str
    ) -> NpcTurn:
        raise ProviderError("api", "HTTP 404: model 'gemma3:12b' not found")


def test_a_dead_provider_stops_the_run_with_its_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "casefile.evals.runner.make_provider", lambda ai, settings: (DownNpc(), None)
    )
    with pytest.raises(SetupError, match="not found"):
        run_suite(load_suite(DEFAULT_SUITE), "ollama", Settings(), repeat=3)
