"""The case validator passes the real case and catches each kind of authoring mistake.

Each mutation starts from the real Blackwood Manor JSON and breaks one thing. The
first six are the mutations from the Milestone 1 prototype validator; the rest cover
the rules it did not have a mutation for.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from casefile.case import CaseBundle
from casefile.case.briefings import Briefings
from casefile.case.solution import Solution
from casefile.case.validation import (
    CaseInvalidError,
    Rule,
    load_valid_case,
    validate_case,
)
from casefile.case.world import Case
from tests.conftest import BLACKWOOD, RawCase, write_raw

Mutation = Callable[[RawCase], None]


def bundle(raw: RawCase) -> CaseBundle:
    return CaseBundle(
        case=Case.model_validate(raw["case"]),
        briefings=Briefings.model_validate(raw["briefings"]),
        solution=Solution.model_validate(raw["solution"]),
    )


def ev(raw: RawCase, evidence_id: str) -> dict[str, Any]:
    return next(e for e in raw["case"]["evidence"] if e["id"] == evidence_id)


def fact(raw: RawCase, fact_id: str) -> dict[str, Any]:
    return next(f for f in raw["case"]["facts"] if f["id"] == fact_id)


def sus(raw: RawCase, suspect_id: str) -> dict[str, Any]:
    return next(s for s in raw["briefings"]["suspects"] if s["suspect"] == suspect_id)


def lie(raw: RawCase, lie_id: str) -> dict[str, Any]:
    return next(x for s in raw["briefings"]["suspects"] for x in s["lies"] if x["id"] == lie_id)


# ------------------------------------------------------------------ the real case


def test_blackwood_manor_is_valid_with_no_warnings(blackwood: CaseBundle) -> None:
    report = validate_case(blackwood)
    assert report.issues == (), "\n".join(map(str, report.issues))


def test_every_fact_evidence_and_lie_is_reachable(blackwood: CaseBundle) -> None:
    final = validate_case(blackwood).reachability.final
    assert final.known_facts == {f.id for f in blackwood.case.facts}
    assert final.found_evidence == {e.id for e in blackwood.case.evidence}
    assert final.caught_lies == {x.id for s in blackwood.briefings.suspects for x in s.lies}


def test_critical_path_depth(blackwood: CaseBundle) -> None:
    """The unlock layers of Victoria's ladder. A change here changes how long the case plays."""
    reach = validate_case(blackwood).reachability
    assert reach.rounds == 6
    assert {
        item: reach.depth[item]
        for item in [
            "F_THOMAS_HEARD_VOICE",  # talk to Thomas
            "F_AUTOREPLY_2215",  # the wall panel's intercom history opens
            "E10",  # the audit export is released
            "LIE_VICTORIA_NO_CONTACT",
            "LIE_VICTORIA_LEFT_2150",
            "LIE_VICTORIA_ANYONE",
            "F_VICTORIA_MOTHER",
        ]
    } == {
        "F_THOMAS_HEARD_VOICE": 1,
        "F_AUTOREPLY_2215": 2,
        "E10": 3,
        "LIE_VICTORIA_NO_CONTACT": 3,
        "LIE_VICTORIA_LEFT_2150": 4,
        "LIE_VICTORIA_ANYONE": 5,
        "F_VICTORIA_MOTHER": 6,
    }


def test_load_valid_case_accepts_blackwood() -> None:
    assert load_valid_case(BLACKWOOD).solution.culprit == "S_VICTORIA"


def test_load_valid_case_refuses_a_broken_case(blackwood_raw: RawCase, tmp_path: Path) -> None:
    ev(blackwood_raw, "E05")["deeper_reads"] = []
    write_raw(tmp_path, blackwood_raw)
    with pytest.raises(CaseInvalidError, match="solvability") as excinfo:
        load_valid_case(tmp_path)
    assert excinfo.value.report.errors


# ------------------------------------------------------------------ mutations


def _swap_gated_to_shared(raw: RawCase) -> None:
    richard = sus(raw, "S_RICHARD")
    richard["gated"] = [g for g in richard["gated"] if g["fact"] != "F_RICHARD_BILLIARD_2050_2136"]
    richard["shares_freely"].append("F_RICHARD_BILLIARD_2050_2136")


def _victoria_in_two_places(raw: RawCase) -> None:
    raw["case"]["facts"].append(
        {
            "id": "F_BAD",
            "statement": "Victoria was in the billiard room.",
            "kind": "presence",
            "subjects": ["S_VICTORIA"],
            "location": "LOC_BILLIARD_ROOM",
            "time": {"from": "21:50", "to": "21:55", "precision": "exact"},
        }
    )


def _richard_hole(raw: RawCase) -> None:
    shared = sus(raw, "S_RICHARD")["shares_freely"]
    shared.remove("F_RICHARD_TERRACE")
    shared.remove("F_RICHARD_BILLIARD_2230_2245")


def _unreachable_item(raw: RawCase) -> None:
    ev(raw, "E12")["discover_when"] = {"evidence_found": "E12"}


MUTATIONS: list[tuple[str, Mutation, Rule, str]] = [
    # From the Milestone 1 prototype.
    (
        "wall panel loses its intercom history",
        lambda r: ev(r, "E05").__setitem__("deeper_reads", []),
        Rule.SOLVABILITY,
        "lie LIE_VICTORIA_NO_CONTACT can never be caught",
    ),
    (
        "Richard volunteers a time next to his lie",
        _swap_gated_to_shared,
        Rule.BOUNDARY_LEAK,
        "S_RICHARD freely shares F_RICHARD_BILLIARD_2050_2136",
    ),
    (
        "Victoria in two places",
        _victoria_in_two_places,
        Rule.PHYSICAL,
        "S_VICTORIA is in LOC_BILLIARD_ROOM (F_BAD) and LOC_STUDY (G_01) at once",
    ),
    (
        "gate camera removed",
        lambda r: r["case"]["evidence"].remove(ev(r, "E06")),
        Rule.SOLVABILITY,
        "lie LIE_THOMAS_PANTRY can never be caught",
    ),
    (
        "innocent suspect's lie hides a guarded fact",
        lambda r: lie(r, "LIE_THOMAS_PANTRY").__setitem__("hides", "G_01"),
        Rule.GUARD_ISOLATION,
        "LIE_THOMAS_PANTRY belongs to S_THOMAS, not the culprit",
    ),
    (
        "lie never put on record",
        lambda r: sus(r, "S_ELEANOR")["opening_statement"].__setitem__("claims", []),
        Rule.ON_RECORD,
        "LIE_ELEANOR_NEVER_IN is never said",
    ),
    # New in Milestone 2.
    (
        "evidence proves a fact that does not exist",
        lambda r: ev(r, "E04")["establishes"].append("F_NOPE"),
        Rule.REFERENCES,
        "E04.establishes: unknown fact F_NOPE",
    ),
    (
        "condition names a lie that does not exist",
        lambda r: ev(r, "E08").__setitem__("discover_when", {"lie_caught": "LIE_NOPE"}),
        Rule.REFERENCES,
        "E08.discover_when (lie_caught): unknown lie LIE_NOPE",
    ),
    (
        "suspect without a briefing",
        lambda r: r["briefings"]["suspects"].remove(sus(r, "S_THOMAS")),
        Rule.CAST,
        "suspect S_THOMAS has no briefing",
    ),
    (
        "accusation form allows too few evidence items",
        lambda r: r["case"]["accusation_options"].__setitem__("max_evidence", 3),
        Rule.ANSWER_KEY,
        "full evidence marks are impossible",
    ),
    (
        "right motive missing from the form",
        lambda r: r["solution"].__setitem__("motive", "MOT_GREED"),
        Rule.ANSWER_KEY,
        "motive MOT_GREED is not an accusation option",
    ),
    (
        "lie contradicted only by testimony",
        lambda r: lie(r, "LIE_RICHARD_BILLIARD").__setitem__(
            "contradicted_by", ["F_RICHARD_BILLIARD_2050_2136"]
        ),
        Rule.CATCHABLE_LIES,
        "LIE_RICHARD_BILLIARD: no contradicting fact",
    ),
    (
        "lie contradicted only by an approximate time",
        lambda r: fact(r, "F_RICHARD_OFFICE")["time"].__setitem__("precision", "approx"),
        Rule.CATCHABLE_LIES,
        "LIE_RICHARD_BILLIARD: no contradicting fact is both proved by evidence and exactly timed",
    ),
    (
        "lie ladder loops",
        lambda r: lie(r, "LIE_RICHARD_NOTE")["on_caught"].__setitem__(
            "fallback_lie", "LIE_RICHARD_BILLIARD"
        ),
        Rule.ON_RECORD,
        "lie ladder loops: LIE_RICHARD_BILLIARD -> LIE_RICHARD_NOTE -> LIE_RICHARD_BILLIARD",
    ),
    (
        "fact after the crime window",
        lambda r: fact(r, "F_RICHARD_999")["time"].__setitem__("from", "23:30"),
        Rule.TIME_WINDOW,
        "F_RICHARD_999 falls outside 20:00-23:00",
    ),
    (
        "suspect's evening has a hole",
        _richard_hole,
        Rule.COVERAGE,
        "S_RICHARD's briefing has a 27-minute gap from 22:20",
    ),
]


@pytest.mark.parametrize(
    ("mutate", "rule", "expected"),
    [pytest.param(m, rule, text, id=name) for name, m, rule, text in MUTATIONS],
)
def test_validator_catches(
    blackwood_raw: RawCase, mutate: Mutation, rule: Rule, expected: str
) -> None:
    mutate(blackwood_raw)
    report = validate_case(bundle(blackwood_raw))
    hits = [i for i in report.errors if i.rule == rule]
    assert any(expected in i.message for i in hits), "\n".join(map(str, report.issues))


def test_dead_weight_is_a_warning_not_an_error(blackwood_raw: RawCase) -> None:
    _unreachable_item(blackwood_raw)
    report = validate_case(bundle(blackwood_raw))
    assert report.ok
    assert [str(w) for w in report.warnings] == [
        "[warning] dead_weight: evidence E12 can never be found",
        "[warning] dead_weight: fact F_JOURNAL can never be learned",
    ]
