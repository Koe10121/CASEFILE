"""Explore everything a player could ever reach in a case (the solvability fixpoint).

Every condition is monotone (D05): once true it stays true. So we can start from an
empty game and apply every action that is possible, round after round, until a round
adds nothing. Whatever is still missing at that point can never be reached in play.

Each round reads only the previous round's state, so ``depth`` counts unlock layers:
depth 1 is available at the start, depth 2 needs something from depth 1, and so on.
"""

from collections.abc import Iterable
from dataclasses import dataclass, field

from casefile.case.conditions import holds
from casefile.case.ids import CharacterId, EvidenceId, FactId, LieId, LocationId
from casefile.case.index import CaseIndex
from casefile.case.rules import (
    catches,
    evidence_discoverable,
    evidence_establishes,
    location_accessible,
)


@dataclass(frozen=True, slots=True)
class Reach:
    """A snapshot of everything reached so far. Satisfies ``ConditionState``."""

    known_facts: frozenset[FactId] = frozenset()
    found_evidence: frozenset[EvidenceId] = frozenset()
    searched_locations: frozenset[LocationId] = frozenset()
    caught_lies: frozenset[LieId] = frozenset()
    talked_to: frozenset[CharacterId] = frozenset()
    told_lies: frozenset[LieId] = frozenset()

    def shown_to(self, suspect: CharacterId) -> frozenset[EvidenceId]:
        """The player can show any item they hold to any suspect."""
        return self.found_evidence


@dataclass(frozen=True, slots=True)
class Reachability:
    final: Reach
    rounds: int
    depth: dict[str, int] = field(default_factory=dict)
    """The round in which each fact, evidence item, location and lie was first reached."""


def _step(ix: CaseIndex, prev: Reach) -> Reach:
    known = set(prev.known_facts)
    found = set(prev.found_evidence)
    searched = set(prev.searched_locations)
    caught = set(prev.caught_lies)
    told = set(prev.told_lies)

    for suspect, briefing in ix.briefings.items():
        told.update(briefing.opening_statement.claims)
        known.update(briefing.shares_freely)
        known.update(g.fact for g in briefing.gated if holds(g.reveal_when, prev, suspect))
        if holds(briefing.breaking_point.when, prev, suspect):
            known.update(briefing.breaking_point.reveal)

    searched.update(
        loc_id for loc_id, loc in ix.locations.items() if location_accessible(loc, prev)
    )

    for ev_id, ev in ix.evidence.items():
        if evidence_discoverable(ev, ix.locations[ev.location], prev):
            found.add(ev_id)
            known.update(evidence_establishes(ev, prev))

    for lie_id, owned in ix.lies.items():
        if lie_id not in prev.told_lies or lie_id in prev.caught_lies:
            continue
        for ev_id in prev.shown_to(owned.suspect):
            if catches(owned.lie, evidence_establishes(ix.evidence[ev_id], prev), ix.facts):
                caught.add(lie_id)
                if owned.lie.on_caught.fallback_lie is not None:
                    told.add(owned.lie.on_caught.fallback_lie)
                known.update(owned.lie.on_caught.reveal)
                break

    return Reach(
        known_facts=frozenset(known),
        found_evidence=frozenset(found),
        searched_locations=frozenset(searched),
        caught_lies=frozenset(caught),
        talked_to=prev.talked_to,
        told_lies=frozenset(told),
    )


def explore(ix: CaseIndex) -> Reachability:
    """Run rounds until nothing changes. Terminates: every set only grows, and is finite."""
    state = Reach(talked_to=frozenset(ix.briefings))
    depth: dict[str, int] = {}
    rounds = 0
    while True:
        nxt = _step(ix, state)
        if nxt == state:
            return Reachability(final=state, rounds=rounds, depth=depth)
        rounds += 1
        for ids in _all_ids(nxt):
            for item in ids:
                depth.setdefault(item, rounds)
        state = nxt


def _all_ids(r: Reach) -> Iterable[frozenset[str]]:
    return (r.known_facts, r.found_evidence, r.searched_locations, r.caught_lies)
