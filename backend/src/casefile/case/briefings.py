"""Models for ``briefings.json``: what each suspect knows, hides and lies about.

These are the *authored* briefings, covering every game state. The engine filters one
of them into a per-turn ``SuspectBriefing`` for the AI layer (D03); the model never
sees an ``AuthoredBriefing`` whole.
"""

from typing import Annotated

from pydantic import Field, StringConstraints, model_validator

from casefile.case.base import CaseModel, NonEmptyStr, require_unique
from casefile.case.conditions import Condition
from casefile.case.ids import CaseId, CharacterId, FactId, GuardedFactId, LieId

Demeanor = Annotated[str, StringConstraints(pattern=r"^[a-z]+(?:_[a-z]+)*$")]
"""One lowercase word, e.g. ``hostile``. The set is open: each persona has its own."""


class Persona(CaseModel):
    summary: NonEmptyStr
    voice: NonEmptyStr
    sample_lines: tuple[NonEmptyStr, ...] = Field(min_length=1)
    default_demeanor: Demeanor


class OpeningStatement(CaseModel):
    """Said the first time the player meets the suspect; puts ``claims`` on record (D08)."""

    text: NonEmptyStr
    claims: tuple[LieId, ...]


class GatedFact(CaseModel):
    fact: FactId
    withheld_hint: NonEmptyStr
    """What the suspect is aware of withholding, phrased without giving the fact away."""
    reveal_when: Condition


class OnCaught(CaseModel):
    fallback_lie: LieId | None
    """The next lie the suspect retreats to; ``null`` when the ladder ends (D04)."""
    reveal: tuple[FactId, ...]
    reaction: NonEmptyStr
    """What the suspect says the moment they're caught, word for word: the fallback lie
    in their own voice, or the admission of what ``reveal`` gives up (D52)."""


class Lie(CaseModel):
    """A scripted false claim. Lies are claims, never false facts (D04)."""

    id: LieId
    claim: NonEmptyStr
    hides: FactId | GuardedFactId
    why: NonEmptyStr
    contradicted_by: tuple[FactId, ...] = Field(min_length=1)
    on_caught: OnCaught


class BreakingPoint(CaseModel):
    when: Condition
    reveal: tuple[FactId, ...]
    demeanor: Demeanor
    line_hint: NonEmptyStr | None = None


class AuthoredBriefing(CaseModel):
    suspect: CharacterId
    persona: Persona
    opening_statement: OpeningStatement
    shares_freely: tuple[FactId, ...]
    gated: tuple[GatedFact, ...]
    lies: tuple[Lie, ...]
    breaking_point: BreakingPoint

    @model_validator(mode="after")
    def _no_fact_listed_twice(self) -> "AuthoredBriefing":
        require_unique(
            [*self.shares_freely, *(g.fact for g in self.gated)],
            f"{self.suspect} shared-or-gated fact",
        )
        return self


class Briefings(CaseModel):
    """Top-level model for ``briefings.json``."""

    case_id: CaseId
    suspects: tuple[AuthoredBriefing, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def _unique(self) -> "Briefings":
        require_unique((s.suspect for s in self.suspects), "suspect")
        require_unique((lie.id for s in self.suspects for lie in s.lies), "lie")
        return self
