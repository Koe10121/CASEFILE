"""Models for ``solution.json``: the answer key.

Only the engine reads this file. The culprit's guarded facts reach the culprit's
briefing (D06); nothing else in it is ever sent to a model.
"""

from pydantic import Field, NonNegativeInt, PositiveInt, model_validator

from casefile.case.base import CaseModel, NonEmptyStr, TimeSpan, require_unique
from casefile.case.ids import (
    CaseId,
    CharacterId,
    EvidenceId,
    FactId,
    GuardedFactId,
    LieId,
    LocationId,
    MethodId,
    MotiveId,
)
from casefile.case.world import FactKind


class LeakMarker(CaseModel):
    """A phrase that, in the culprit's output, means a guarded fact is leaking (D07)."""

    phrase: NonEmptyStr
    unless_known: FactId | None = None
    """Stop flagging the phrase once the player knows this fact."""


class GuardedFact(CaseModel):
    """A secret only the culprit knows. Never disclosable through ``reveal_fact`` (D06)."""

    id: GuardedFactId
    statement: NonEmptyStr
    """Second person, for the culprit's briefing."""
    time: TimeSpan | None = None
    location: LocationId | None = None
    subjects: tuple[CharacterId, ...] = ()
    kind: FactKind | None = None
    leak_markers: tuple[LeakMarker, ...] = Field(min_length=1)


class KeyEvidenceGroup(CaseModel):
    """Citing any one item in the group earns its points (D10)."""

    label: NonEmptyStr
    items: tuple[EvidenceId, ...] = Field(min_length=1)


class SolutionStep(CaseModel):
    step: PositiveInt
    learn: tuple[FactId, ...] = ()
    breaks: LieId | None = None
    via: NonEmptyStr
    """Author's note on how the player gets there, e.g. ``show:E05->S_VICTORIA``."""
    hint: NonEmptyStr

    @model_validator(mode="after")
    def _has_goal(self) -> "SolutionStep":
        if not self.learn and self.breaks is None:
            raise ValueError(f"step {self.step} must `learn` facts or `breaks` a lie")
        return self


class Scoring(CaseModel):
    """Points per part of the accusation. Nothing but the culprit scores without it (D29)."""

    culprit: NonNegativeInt
    motive: NonNegativeInt
    method: NonNegativeInt
    evidence: NonNegativeInt
    points_per_group: PositiveInt

    @model_validator(mode="after")
    def _totals_100(self) -> "Scoring":
        total = self.culprit + self.motive + self.method + self.evidence
        if total != 100:
            raise ValueError(f"scoring must total 100 points, got {total}")
        return self


class Solution(CaseModel):
    """Top-level model for ``solution.json``."""

    case_id: CaseId
    culprit: CharacterId
    motive: MotiveId
    method: MethodId
    guarded_facts: tuple[GuardedFact, ...] = Field(min_length=3, max_length=5)
    key_evidence_groups: tuple[KeyEvidenceGroup, ...] = Field(min_length=1)
    solution_chain: tuple[SolutionStep, ...] = Field(min_length=1)
    epilogue: NonEmptyStr
    scoring: Scoring

    @model_validator(mode="after")
    def _consistent(self) -> "Solution":
        require_unique((g.id for g in self.guarded_facts), "guarded fact")
        numbers = [s.step for s in self.solution_chain]
        if numbers != list(range(1, len(numbers) + 1)):
            raise ValueError(f"solution steps must be numbered 1..n in order, got {numbers}")
        reachable = self.scoring.points_per_group * len(self.key_evidence_groups)
        if reachable != self.scoring.evidence:
            raise ValueError(
                f"evidence is worth {self.scoring.evidence} points but "
                f"{len(self.key_evidence_groups)} groups x {self.scoring.points_per_group} "
                f"= {reachable}"
            )
        return self
