"""The engine: applies player actions and validates NPC disclosures against the case.

The engine owns the truth. It decides what the player can find, which lies are caught,
what each suspect may reveal right now, and the score. The AI layer only proposes fact
IDs for a suspect to reveal, and ``disclose`` accepts or rejects each one (D14).
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, replace
from enum import StrEnum
from typing import assert_never

from casefile.case.conditions import holds
from casefile.case.ids import CharacterId, FactId
from casefile.case.index import CaseIndex
from casefile.case.loader import CaseBundle
from casefile.case.rules import (
    catches,
    evidence_discoverable,
    evidence_establishes,
    location_accessible,
)
from casefile.case.world import Fact
from casefile.engine.actions import (
    Accuse,
    Action,
    LogEntry,
    NpcReveal,
    SearchLocation,
    ShowEvidence,
    TalkTo,
)
from casefile.engine.events import (
    AccusationScored,
    Event,
    EvidenceFound,
    FactLearned,
    LieCaught,
    LieOnRecord,
    LocationSearched,
)
from casefile.engine.scoring import Accusation, score
from casefile.engine.state import FinalAccusation, GameState, NotebookEntry, Source


class IllegalActionError(Exception):
    """The action is not allowed in this state. Nothing changed."""


@dataclass(frozen=True, slots=True)
class Outcome:
    state: GameState
    events: tuple[Event, ...]


class RejectReason(StrEnum):
    GUARDED = "guarded"
    """A guarded (``G_``) fact: never revealable. In play this is a leak attempt (D06)."""
    UNKNOWN = "unknown"
    """Not a fact in this case: the model invented an ID."""
    NOT_ALLOWED = "not_allowed"
    """A real fact, but not one this suspect may reveal right now."""


@dataclass(frozen=True, slots=True)
class RejectedReveal:
    proposed: str
    reason: RejectReason


@dataclass(frozen=True, slots=True)
class Disclosure:
    """The result of validating one NPC reply's ``reveals``."""

    state: GameState
    events: tuple[Event, ...]
    accepted: tuple[FactId, ...]
    rejected: tuple[RejectedReveal, ...]


class Engine:
    """Stateless rules over one case. Safe to share across every game session."""

    def __init__(self, bundle: CaseBundle) -> None:
        self._ix = CaseIndex.build(bundle)

    @property
    def index(self) -> CaseIndex:
        return self._ix

    # ------------------------------------------------------------ public API

    def new_game(self) -> GameState:
        """A fresh game, with every item that is available from the start already found."""
        state, _ = self._settle(GameState(), [])
        return state

    def apply(self, state: GameState, action: Action) -> Outcome:
        if state.is_over:
            raise IllegalActionError("the accusation is final; the game is over")
        events: list[Event] = []
        match action:
            case TalkTo():
                state = self._talk_to(state, action, events)
            case SearchLocation():
                state = self._search(state, action, events)
            case ShowEvidence():
                state = self._show(state, action, events)
            case Accuse():
                state = self._accuse(state, action.accusation, events)
            case _:
                assert_never(action)
        state, events = self._settle(state, events)
        return Outcome(state, tuple(events))

    def replay(self, log: Iterable[LogEntry]) -> GameState:
        """Rebuild a game from its log. Deterministic: the same log gives the same state."""
        state = self.new_game()
        for entry in log:
            if isinstance(entry, NpcReveal):
                state = self.disclose(state, entry.suspect, entry.reveals).state
            else:
                state = self.apply(state, entry).state
        return state

    def allowed_reveals(self, state: GameState, suspect: CharacterId) -> frozenset[FactId]:
        """Every fact this suspect may disclose right now (the D03 context gate).

        Facts they share freely, gated facts whose condition holds, and the breaking
        point's facts once it is reached. Facts released by a caught lie are added to the
        notebook by the catch itself, so they need no entry here.
        """
        briefing = self._ix.briefings[suspect]
        allowed = set(briefing.shares_freely)
        allowed.update(g.fact for g in briefing.gated if holds(g.reveal_when, state, suspect))
        if holds(briefing.breaking_point.when, state, suspect):
            allowed.update(briefing.breaking_point.reveal)
        return frozenset(allowed)

    def disclose(
        self, state: GameState, suspect: CharacterId, proposed: Sequence[str]
    ) -> Disclosure:
        """Validate the fact IDs an NPC reply wants to reveal, and learn the valid ones.

        ``proposed`` is plain strings on purpose: it comes from a model and is untrusted.
        Rejections never raise; the caller logs them as eval failures (D14).
        """
        if state.is_over:
            raise IllegalActionError("the accusation is final; the game is over")
        if suspect not in state.talked_to:
            raise IllegalActionError(f"the player is not interviewing {suspect}")
        allowed = self.allowed_reveals(state, suspect)
        accepted: list[FactId] = []
        rejected: list[RejectedReveal] = []
        for raw in dict.fromkeys(proposed):  # de-duplicate, keep order
            item = self._ix.statements.get(raw)
            if item is None:
                rejected.append(RejectedReveal(raw, RejectReason.UNKNOWN))
            elif not isinstance(item, Fact):
                rejected.append(RejectedReveal(raw, RejectReason.GUARDED))
            elif item.id not in allowed:
                rejected.append(RejectedReveal(raw, RejectReason.NOT_ALLOWED))
            else:
                accepted.append(item.id)
        events: list[Event] = []
        state = self._learn(state, accepted, suspect, events)
        state, events = self._settle(state, events)
        return Disclosure(state, tuple(events), tuple(accepted), tuple(rejected))

    # ------------------------------------------------------------ actions

    def _talk_to(self, state: GameState, action: TalkTo, events: list[Event]) -> GameState:
        if action.suspect not in self._ix.briefings:
            raise IllegalActionError(f"{action.suspect} is not a suspect you can interview")
        if action.suspect in state.talked_to:
            return state
        briefing = self._ix.briefings[action.suspect]
        claims = [c for c in briefing.opening_statement.claims if c not in state.told_lies]
        events.extend(LieOnRecord(action.suspect, lie) for lie in claims)
        return replace(
            state,
            talked_to=state.talked_to | {action.suspect},
            told_lies=state.told_lies | set(claims),
        )

    def _search(self, state: GameState, action: SearchLocation, events: list[Event]) -> GameState:
        location = self._ix.locations.get(action.location)
        if location is None:
            raise IllegalActionError(f"there is no location {action.location}")
        if not location_accessible(location, state):
            raise IllegalActionError(f"{location.name} is not accessible yet")
        if location.id in state.searched_locations:
            return state
        events.append(LocationSearched(location.id))
        return replace(state, searched_locations=state.searched_locations | {location.id})

    def _show(self, state: GameState, action: ShowEvidence, events: list[Event]) -> GameState:
        suspect, ev_id = action.suspect, action.evidence
        if suspect not in state.talked_to:
            raise IllegalActionError(f"the player is not interviewing {suspect}")
        if ev_id not in state.found_evidence:
            raise IllegalActionError(f"{ev_id} has not been found")
        proves = evidence_establishes(self._ix.evidence[ev_id], state)
        before = state
        state = replace(state, shown=state.shown | {(suspect, ev_id)})
        # Only lies already on record can be caught. A fallback told because of this
        # catch must be caught by a later showing: the suspect has to say it first.
        for lie in self._ix.briefings[suspect].lies:
            if lie.id not in before.told_lies or lie.id in before.caught_lies:
                continue
            if not catches(lie, proves, self._ix.facts):
                continue
            events.append(LieCaught(suspect, lie.id, ev_id))
            state = replace(state, caught_lies=state.caught_lies | {lie.id})
            fallback = lie.on_caught.fallback_lie
            if fallback is not None and fallback not in state.told_lies:
                events.append(LieOnRecord(suspect, fallback))
                state = replace(state, told_lies=state.told_lies | {fallback})
            state = self._learn(state, lie.on_caught.reveal, suspect, events)
        return state

    def _accuse(self, state: GameState, accusation: Accusation, events: list[Event]) -> GameState:
        options = self._ix.bundle.case.accusation_options
        if accusation.culprit not in options.culprits:
            raise IllegalActionError(f"{accusation.culprit} is not one of the suspects")
        if accusation.motive not in {m.id for m in options.motives}:
            raise IllegalActionError(f"{accusation.motive} is not one of the motives")
        if accusation.method not in {m.id for m in options.methods}:
            raise IllegalActionError(f"{accusation.method} is not one of the methods")
        if len(set(accusation.evidence)) != len(accusation.evidence):
            raise IllegalActionError("the same evidence is cited twice")
        if len(accusation.evidence) > options.max_evidence:
            raise IllegalActionError(f"cite at most {options.max_evidence} evidence items")
        unfound = [e for e in accusation.evidence if e not in state.found_evidence]
        if unfound:
            raise IllegalActionError(f"evidence not found yet: {', '.join(unfound)}")
        result = score(accusation, self._ix.bundle.solution)
        events.append(AccusationScored(result))
        return replace(state, final=FinalAccusation(accusation, result))

    # ------------------------------------------------------------ consequences

    def _learn(
        self, state: GameState, facts: Iterable[FactId], source: Source, events: list[Event]
    ) -> GameState:
        new = [f for f in dict.fromkeys(facts) if f not in state.known_facts]
        if not new:
            return state
        events.extend(FactLearned(f, source) for f in new)
        return replace(
            state,
            known_facts=state.known_facts | set(new),
            notebook=state.notebook + tuple(NotebookEntry(f, source) for f in new),
        )

    def _settle(self, state: GameState, events: list[Event]) -> tuple[GameState, list[Event]]:
        """Apply automatic consequences until nothing changes.

        Items become findable as locations are searched and facts are learned, and items
        already held reveal more when a deeper read opens. Monotone, so it terminates.
        """
        while True:
            before = state
            for ev in self._ix.evidence.values():
                if ev.id not in state.found_evidence and evidence_discoverable(
                    ev, self._ix.locations[ev.location], state
                ):
                    events.append(EvidenceFound(ev.id))
                    state = replace(state, found_evidence=state.found_evidence | {ev.id})
            for ev_id in sorted(state.found_evidence):
                state = self._learn(
                    state, evidence_establishes(self._ix.evidence[ev_id], state), ev_id, events
                )
            if state == before:
                return state, events
