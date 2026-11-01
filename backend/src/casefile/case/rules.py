"""Game rules that the validator and the engine must agree on.

The solvability proof is only worth something if it uses the same rules as play, so
these live in one place and both sides call them.
"""

from collections.abc import Mapping, Set

from casefile.case.briefings import Lie
from casefile.case.conditions import ConditionState, holds
from casefile.case.ids import FactId
from casefile.case.world import Evidence, Fact, Location


def location_accessible(location: Location, state: ConditionState) -> bool:
    return location.accessible_when is None or holds(location.accessible_when, state)


def evidence_discoverable(evidence: Evidence, location: Location, state: ConditionState) -> bool:
    """Whether the player can pick up this item now.

    Items without ``discover_when`` are available from the start, as long as their
    location is open. Others also need their location searched and the condition met.
    """
    if not location_accessible(location, state):
        return False
    if evidence.discover_when is None:
        return True
    return location.id in state.searched_locations and holds(evidence.discover_when, state)


def evidence_establishes(evidence: Evidence, state: ConditionState) -> frozenset[FactId]:
    """The facts an item proves right now, including any deeper reads that have opened."""
    facts = set(evidence.establishes)
    for read in evidence.deeper_reads:
        if holds(read.when, state):
            facts.update(read.establishes)
    return frozenset(facts)


def can_catch_lies(fact: Fact) -> bool:
    """An approximate time is never enough to call someone a liar."""
    return fact.time is None or fact.time.precision == "exact"


def catches(lie: Lie, shown_facts: Set[FactId], facts: Mapping[FactId, Fact]) -> bool:
    """Whether showing evidence that proves ``shown_facts`` catches this lie.

    Only call this for a lie that is on record and not yet caught.
    """
    return any(f in shown_facts and can_catch_lies(facts[f]) for f in lie.contradicted_by)
