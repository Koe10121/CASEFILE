"""What happened as the result of an action, for the UI and the notebook to show."""

from dataclasses import dataclass

from casefile.case.ids import CharacterId, EvidenceId, FactId, LieId, LocationId
from casefile.engine.scoring import ScoreBreakdown
from casefile.engine.state import Source


@dataclass(frozen=True, slots=True)
class FactLearned:
    fact: FactId
    source: Source


@dataclass(frozen=True, slots=True)
class EvidenceFound:
    evidence: EvidenceId


@dataclass(frozen=True, slots=True)
class LocationSearched:
    location: LocationId


@dataclass(frozen=True, slots=True)
class LieOnRecord:
    suspect: CharacterId
    lie: LieId


@dataclass(frozen=True, slots=True)
class LieCaught:
    suspect: CharacterId
    lie: LieId
    evidence: EvidenceId


@dataclass(frozen=True, slots=True)
class AccusationScored:
    score: ScoreBreakdown


Event = FactLearned | EvidenceFound | LocationSearched | LieOnRecord | LieCaught | AccusationScored
