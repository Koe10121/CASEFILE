"""ID lookups over a loaded case, built once and shared by the validator and the engine."""

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from casefile.case.briefings import AuthoredBriefing, Lie
from casefile.case.ids import CharacterId, EvidenceId, FactId, GuardedFactId, LieId, LocationId
from casefile.case.loader import CaseBundle
from casefile.case.solution import GuardedFact
from casefile.case.world import Character, Evidence, Fact, Location


@dataclass(frozen=True, slots=True)
class OwnedLie:
    """A lie together with the suspect who tells it."""

    suspect: CharacterId
    lie: Lie


@dataclass(frozen=True, slots=True)
class CaseIndex:
    bundle: CaseBundle
    characters: Mapping[CharacterId, Character]
    locations: Mapping[LocationId, Location]
    facts: Mapping[FactId, Fact]
    evidence: Mapping[EvidenceId, Evidence]
    briefings: Mapping[CharacterId, AuthoredBriefing]
    lies: Mapping[LieId, OwnedLie]
    guarded: Mapping[GuardedFactId, GuardedFact]
    statements: Mapping[str, Fact | GuardedFact]
    """Facts and guarded facts together, for fields that may hold either (``Lie.hides``)."""

    @classmethod
    def build(cls, bundle: CaseBundle) -> "CaseIndex":
        case, briefings, solution = bundle.case, bundle.briefings, bundle.solution
        return cls(
            bundle=bundle,
            characters=MappingProxyType({c.id: c for c in case.characters}),
            locations=MappingProxyType({loc.id: loc for loc in case.locations}),
            facts=MappingProxyType({f.id: f for f in case.facts}),
            evidence=MappingProxyType({e.id: e for e in case.evidence}),
            briefings=MappingProxyType({b.suspect: b for b in briefings.suspects}),
            lies=MappingProxyType(
                {lie.id: OwnedLie(b.suspect, lie) for b in briefings.suspects for lie in b.lies}
            ),
            guarded=MappingProxyType({g.id: g for g in solution.guarded_facts}),
            statements=MappingProxyType(
                {**{f.id: f for f in case.facts}, **{g.id: g for g in solution.guarded_facts}}
            ),
        )
