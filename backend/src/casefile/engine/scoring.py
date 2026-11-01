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

    Naming the wrong culprit scores 0: the case is unsolved, whatever else is right (D29).
    With the right culprit, motive and method are all-or-nothing, and evidence earns
    ``points_per_group`` for each key group at least one cited item belongs to, so two
    items from one group earn nothing extra.
    """
    rules = solution.scoring
    cited = set(accusation.evidence)
    covered = tuple(g.label for g in solution.key_evidence_groups if cited.intersection(g.items))
    if accusation.culprit != solution.culprit:
        return ScoreBreakdown(culprit=0, motive=0, method=0, evidence=0, groups_covered=covered)
    return ScoreBreakdown(
        culprit=rules.culprit,
        motive=rules.motive if accusation.motive == solution.motive else 0,
        method=rules.method if accusation.method == solution.method else 0,
        evidence=len(covered) * rules.points_per_group,
        groups_covered=covered,
    )
