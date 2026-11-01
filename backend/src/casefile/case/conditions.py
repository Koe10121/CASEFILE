"""Reveal and unlock conditions (D05).

    Condition := {"all": [Condition, ...]} | {"any": [Condition, ...]} | Atom
    Atom      := {"location_searched": LOC} | {"evidence_found": E} | {"evidence_shown": E}
               | {"fact_known": F} | {"lie_caught": LIE} | {"talked_to": S}

Each condition is a JSON object with exactly one key, and the key picks the model.
There is deliberately no negation: every condition is monotone (once true, always
true), which is what makes solvability a simple fixpoint computation.
"""

from typing import Annotated, Any

from pydantic import Discriminator, Field, Tag

from casefile.case.base import CaseModel
from casefile.case.ids import CharacterId, EvidenceId, FactId, LieId, LocationId


class AllOf(CaseModel):
    all_: tuple["Condition", ...] = Field(alias="all", min_length=1)


class AnyOf(CaseModel):
    any_: tuple["Condition", ...] = Field(alias="any", min_length=1)


class LocationSearched(CaseModel):
    location_searched: LocationId


class EvidenceFound(CaseModel):
    evidence_found: EvidenceId


class EvidenceShown(CaseModel):
    """True when the player has shown this evidence to the suspect being evaluated."""

    evidence_shown: EvidenceId


class FactKnown(CaseModel):
    fact_known: FactId


class LieCaught(CaseModel):
    lie_caught: LieId


class TalkedTo(CaseModel):
    talked_to: CharacterId


_TAG_BY_TYPE: dict[type[CaseModel], str] = {
    AllOf: "all",
    AnyOf: "any",
    LocationSearched: "location_searched",
    EvidenceFound: "evidence_found",
    EvidenceShown: "evidence_shown",
    FactKnown: "fact_known",
    LieCaught: "lie_caught",
    TalkedTo: "talked_to",
}


def _condition_tag(value: Any) -> str | None:
    """Pick the model from the object's single key, so errors name the right variant."""
    if isinstance(value, dict):
        return next(iter(value)) if len(value) == 1 else None
    return _TAG_BY_TYPE.get(type(value))


Condition = Annotated[
    Annotated[AllOf, Tag("all")]
    | Annotated[AnyOf, Tag("any")]
    | Annotated[LocationSearched, Tag("location_searched")]
    | Annotated[EvidenceFound, Tag("evidence_found")]
    | Annotated[EvidenceShown, Tag("evidence_shown")]
    | Annotated[FactKnown, Tag("fact_known")]
    | Annotated[LieCaught, Tag("lie_caught")]
    | Annotated[TalkedTo, Tag("talked_to")],
    Discriminator(
        _condition_tag,
        custom_error_type="invalid_condition",
        custom_error_message=(
            "a condition must be an object with exactly one key: all, any, location_searched, "
            "evidence_found, evidence_shown, fact_known, lie_caught or talked_to"
        ),
    ),
]

AllOf.model_rebuild()
AnyOf.model_rebuild()
