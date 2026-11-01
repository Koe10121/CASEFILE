"""Deterministic accusation scoring (D10). The AI may explain a score; it never awards one."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict

from casefile.case.ids import CharacterId, EvidenceId, MethodId, MotiveId
from casefile.case.solution import Solution


class Accusation(BaseModel):
    """The player's structured, final accusation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    culprit: CharacterId
    motive: MotiveId
    method: MethodId
    evidence: tuple[EvidenceId, ...]


@dataclass(frozen=True, slots=True)
class ScoreBreakdown:
    culprit: int
    motive: int
    method: int
    evidence: int
    groups_covered: tuple[str, ...]
    """Labels of the key evidence groups the cited evidence covered."""

    @property
    def total(self) -> int:
        return self.culprit + self.motive + self.method + self.evidence


def score(accusation: Accusation, solution: Solution) -> ScoreBreakdown:
    """Score an accusation that the engine has already checked is well-formed.

    Culprit, motive and method are all-or-nothing. Motive and method count only with the
    right culprit when the case says so. Evidence earns ``points_per_group`` for each key
    group that at least one cited item belongs to, so citing two items from one group
    earns nothing extra.
    """
    rules = solution.scoring
    right_culprit = accusation.culprit == solution.culprit
    counts_rest = right_culprit or not rules.motive_method_require_culprit
    cited = set(accusation.evidence)
    covered = tuple(g.label for g in solution.key_evidence_groups if cited.intersection(g.items))
    return ScoreBreakdown(
        culprit=rules.culprit if right_culprit else 0,
        motive=rules.motive if counts_rest and accusation.motive == solution.motive else 0,
        method=rules.method if counts_rest and accusation.method == solution.method else 0,
        evidence=len(covered) * rules.points_per_group,
        groups_covered=covered,
    )
