"""Reveal and unlock conditions (D05).

    Condition := {"all": [Condition, ...]} | {"any": [Condition, ...]} | Atom
    Atom      := {"location_searched": LOC} | {"evidence_found": E} | {"evidence_shown": E}
               | {"fact_known": F} | {"lie_caught": LIE} | {"talked_to": S}

Each condition is a JSON object with exactly one key, and the key picks the model.
There is deliberately no negation: every condition is monotone (once true, always
true), which is what makes solvability a simple fixpoint computation.
"""

from collections.abc import Iterator, Set
from typing import Annotated, Any, Protocol, assert_never

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


class ConditionState(Protocol):
    """What a condition can ask about: the player's recorded actions so far.

    The engine's game state and the validator's reachability search both satisfy this,
    so a condition means exactly the same thing in play and in the solvability proof.
    """

    @property
    def known_facts(self) -> Set[FactId]: ...
    @property
    def found_evidence(self) -> Set[EvidenceId]: ...
    @property
    def searched_locations(self) -> Set[LocationId]: ...
    @property
    def caught_lies(self) -> Set[LieId]: ...
    @property
    def talked_to(self) -> Set[CharacterId]: ...
    def shown_to(self, suspect: CharacterId) -> Set[EvidenceId]: ...


def holds(condition: Condition, state: ConditionState, suspect: CharacterId | None = None) -> bool:
    """Evaluate a condition. ``evidence_shown`` needs the suspect it is evaluated for."""
    match condition:
        case AllOf(all_=parts):
            return all(holds(c, state, suspect) for c in parts)
        case AnyOf(any_=parts):
            return any(holds(c, state, suspect) for c in parts)
        case LocationSearched(location_searched=loc):
            return loc in state.searched_locations
        case EvidenceFound(evidence_found=ev):
            return ev in state.found_evidence
        case EvidenceShown(evidence_shown=ev):
            return suspect is not None and ev in state.shown_to(suspect)
        case FactKnown(fact_known=fact):
            return fact in state.known_facts
        case LieCaught(lie_caught=lie):
            return lie in state.caught_lies
        case TalkedTo(talked_to=who):
            return who in state.talked_to
        case _:
            assert_never(condition)


ConditionRef = tuple[str, str]
"""``(atom key, referenced ID)``, e.g. ``("fact_known", "F_DINNER")``."""


def condition_refs(condition: Condition) -> Iterator[ConditionRef]:
    """Every ID a condition mentions, for the referential-integrity check."""
    match condition:
        case AllOf(all_=parts) | AnyOf(any_=parts):
            for part in parts:
                yield from condition_refs(part)
        case LocationSearched(location_searched=ref):
            yield "location_searched", ref
        case EvidenceFound(evidence_found=ref):
            yield "evidence_found", ref
        case EvidenceShown(evidence_shown=ref):
            yield "evidence_shown", ref
        case FactKnown(fact_known=ref):
            yield "fact_known", ref
        case LieCaught(lie_caught=ref):
            yield "lie_caught", ref
        case TalkedTo(talked_to=ref):
            yield "talked_to", ref
        case _:
            assert_never(condition)
