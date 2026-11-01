"""Condition evaluation, on a hand-built state."""

from dataclasses import dataclass, field

import pytest
from pydantic import TypeAdapter

from casefile.case.conditions import Condition, condition_refs, holds
from casefile.case.ids import CharacterId, EvidenceId, FactId, LieId, LocationId

parse = TypeAdapter(Condition).validate_python


@dataclass
class State:
    known_facts: set[FactId] = field(default_factory=set)
    found_evidence: set[EvidenceId] = field(default_factory=set)
    searched_locations: set[LocationId] = field(default_factory=set)
    caught_lies: set[LieId] = field(default_factory=set)
    talked_to: set[CharacterId] = field(default_factory=set)
    shown: dict[str, set[EvidenceId]] = field(default_factory=dict)

    def shown_to(self, suspect: CharacterId) -> set[EvidenceId]:
        return self.shown.get(suspect, set())


STATE = State(
    known_facts={FactId("F_A")},
    caught_lies={LieId("LIE_X")},
    shown={"S_VICTORIA": {EvidenceId("E11")}},
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ({"fact_known": "F_A"}, True),
        ({"fact_known": "F_B"}, False),
        ({"all": [{"fact_known": "F_A"}, {"lie_caught": "LIE_X"}]}, True),
        ({"all": [{"fact_known": "F_A"}, {"lie_caught": "LIE_Y"}]}, False),
        ({"any": [{"fact_known": "F_B"}, {"lie_caught": "LIE_X"}]}, True),
        ({"evidence_found": "E11"}, False),
    ],
)
def test_holds(raw: object, expected: bool) -> None:
    assert holds(parse(raw), STATE) is expected


def test_evidence_shown_is_per_suspect() -> None:
    cond = parse({"evidence_shown": "E11"})
    assert holds(cond, STATE, CharacterId("S_VICTORIA"))
    assert not holds(cond, STATE, CharacterId("S_RICHARD"))
    assert not holds(cond, STATE), "with no suspect, nothing has been shown"


def test_condition_refs_walks_nested_trees() -> None:
    cond = parse({"all": [{"fact_known": "F_A"}, {"any": [{"talked_to": "S_THOMAS"}]}]})
    assert list(condition_refs(cond)) == [("fact_known", "F_A"), ("talked_to", "S_THOMAS")]
