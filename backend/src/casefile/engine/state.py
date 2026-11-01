"""Game state: an immutable record of everything the player has done and learned.

Every engine call takes a state and returns a new one; nothing is updated in place.
That makes a game a pure fold over its actions: replaying the same actions always
gives the same state, which is what save/resume and the eval harness rely on.
"""

from dataclasses import dataclass, field

from casefile.case.ids import CharacterId, EvidenceId, FactId, LieId, LocationId
from casefile.engine.scoring import Accusation, ScoreBreakdown

Source = EvidenceId | CharacterId
"""Where the player learned a fact: an evidence item, or a suspect's testimony."""


@dataclass(frozen=True, slots=True)
class NotebookEntry:
    fact: FactId
    source: Source


@dataclass(frozen=True, slots=True)
class FinalAccusation:
    accusation: Accusation
    score: ScoreBreakdown


@dataclass(frozen=True, slots=True)
class GameState:
    """Satisfies ``ConditionState``, so case conditions evaluate directly against it."""

    notebook: tuple[NotebookEntry, ...] = ()
    """Facts in the order the player learned them. The UI shows each fact's statement."""
    known_facts: frozenset[FactId] = frozenset()
    found_evidence: frozenset[EvidenceId] = frozenset()
    searched_locations: frozenset[LocationId] = frozenset()
    talked_to: frozenset[CharacterId] = frozenset()
    told_lies: frozenset[LieId] = frozenset()
    """Lies on record: said in an opening statement, or fallen back to (D08)."""
    caught_lies: frozenset[LieId] = frozenset()
    shown: frozenset[tuple[CharacterId, EvidenceId]] = field(default_factory=frozenset)
    final: FinalAccusation | None = None
    """Set once the player accuses. The game is then over (D10)."""

    def shown_to(self, suspect: CharacterId) -> frozenset[EvidenceId]:
        return frozenset(ev for who, ev in self.shown if who == suspect)

    @property
    def is_over(self) -> bool:
        return self.final is not None
