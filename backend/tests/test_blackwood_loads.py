"""The real CASE #001 files parse, and the models capture every field in them."""

from typing import Any

import pytest
from pydantic import BaseModel, ValidationError

from casefile.case import CaseBundle
from casefile.case.base import CaseModel
from casefile.case.conditions import AnyOf, FactKnown, LieCaught
from tests.conftest import RawCase


def test_counts_match_the_story_spec(blackwood: CaseBundle) -> None:
    assert len(blackwood.case.facts) == 76
    assert len(blackwood.case.evidence) == 12
    assert len(blackwood.briefings.suspects) == 4
    assert sum(len(s.lies) for s in blackwood.briefings.suspects) == 8
    assert blackwood.solution.culprit == "S_VICTORIA"


@pytest.mark.parametrize("stem", ["case", "briefings", "solution"])
def test_round_trip_is_lossless(blackwood: CaseBundle, blackwood_raw: RawCase, stem: str) -> None:
    """Dumping a model gives back the exact JSON: no field is dropped, renamed or reformatted."""
    model: BaseModel = getattr(blackwood, stem)
    assert model.model_dump(mode="json", exclude_unset=True) == blackwood_raw[stem]


def test_conditions_parse_into_typed_variants(blackwood: CaseBundle) -> None:
    panel = next(e for e in blackwood.case.evidence if e.id == "E05")
    when = panel.deeper_reads[0].when
    assert isinstance(when, AnyOf)
    assert all(isinstance(c, FactKnown) for c in when.any_)
    assert [c.fact_known for c in when.any_ if isinstance(c, FactKnown)] == [
        "F_THOMAS_HEARD_VOICE",
        "F_ELEANOR_HEARD_VOICE",
    ]
    guest_room = next(loc for loc in blackwood.case.locations if loc.id == "LOC_GUEST_ROOM_2")
    assert isinstance(guest_room.accessible_when, LieCaught)
    assert guest_room.accessible_when.lie_caught == "LIE_VICTORIA_NO_CONTACT"


def test_loaded_case_is_immutable(blackwood: CaseBundle) -> None:
    fact = blackwood.case.facts[0]
    with pytest.raises(ValidationError, match="frozen"):
        setattr(fact, "statement", "rewritten")  # noqa: B010 (mypy already forbids the direct form)
    assert isinstance(blackwood.case.facts, tuple)
    assert isinstance(fact.subjects, tuple)


def _all_models(value: Any) -> list[CaseModel]:
    if isinstance(value, CaseModel):
        return [
            value,
            *(m for field in type(value).model_fields for m in _all_models(getattr(value, field))),
        ]
    if isinstance(value, tuple):
        return [m for item in value for m in _all_models(item)]
    return []


def test_every_nested_collection_is_a_tuple(blackwood: CaseBundle) -> None:
    """Frozen models only protect their own attributes; lists inside them would stay mutable."""
    for root in (blackwood.case, blackwood.briefings, blackwood.solution):
        for model in _all_models(root):
            for name in type(model).model_fields:
                assert not isinstance(getattr(model, name), list | dict | set), (
                    f"{type(model).__name__}.{name} is mutable"
                )
