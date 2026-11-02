"""One player's game: the engine, an NPC provider and the conversation, wired together.

The engine decides; the provider performs. A question to a suspect goes:

    player text -> length cap -> briefing (engine) -> provider -> leak guard (culprit)
                -> grounding (reveals must match the line shown, D41) -> reveal check
                (engine) -> dialogue shown, accepted facts learned

Everything that changes the truth is in ``log``, so ``engine.replay(log)`` rebuilds
the state. The transcript is kept for display and for the model's context, but it is
never trusted as a source of facts (D14).
"""

import math
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Self

from pydantic import BaseModel, ConfigDict, Field

from casefile.ai.contract import Exchange, Usage
from casefile.ai.grounding import ground, speaker_words
from casefile.ai.guard import find_confession, find_leaks
from casefile.ai.provider import NpcProvider
from casefile.case.ids import CharacterId, EvidenceId, FactId, LocationId
from casefile.case.world import HintPolicy
from casefile.engine.actions import (
    Accuse,
    Action,
    LogEntry,
    NpcReveal,
    SearchLocation,
    ShowEvidence,
    TalkTo,
)
from casefile.engine.briefing import SuspectBriefing, build_briefing
from casefile.engine.engine import Engine, IllegalActionError, Outcome, RejectedReveal
from casefile.engine.events import Event, LieCaught
from casefile.engine.hints import next_hint, parse_policy
from casefile.engine.scoring import Accusation
from casefile.engine.state import GameState

MAX_PLAYER_CHARS = 500
"""Injection defence layer 6: long inputs are where elaborate jailbreaks live."""

LEAK_FALLBACK = "I've told you what I know, Inspector."
"""Said instead of a reply that tripped a leak marker. Deliberately bland."""


@dataclass(frozen=True, slots=True)
class Reply:
    """The result of one question, for the UI and for the eval harness."""

    dialogue: str
    demeanor: str
    accepted: tuple[FactId, ...]
    rejected: tuple[RejectedReveal, ...]
    leaks: tuple[str, ...]
    """Leak markers or confessions in the culprit's dialogue (the line was replaced)."""
    unsupported: tuple[str, ...]
    """Facts the provider declared but the dialogue didn't say (dropped, D41)."""
    inferred: tuple[FactId, ...]
    """Facts the dialogue clearly said but the provider didn't declare (counted, D41)."""
    events: tuple[Event, ...]
    usage: Usage


class SavedGame(BaseModel):
    """Everything needed to pick a game up again (D53). The state itself isn't saved:
    replaying ``log`` rebuilds it (D25), so a save can't hold a state the rules
    wouldn't reach."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    detective: str | None
    log: tuple[LogEntry, ...]
    transcripts: dict[CharacterId, tuple[Exchange, ...]]
    current_suspect: CharacterId | None
    tokens_used: int = Field(ge=0)
    """Carried over so a restart doesn't refill the token budget."""
    hints: tuple[str, ...] = ()
    last_progress_at: float | None = None
    """Wall-clock time of the last new fact, catch or hint, for timed hints (D54)."""


class BudgetExhaustedError(IllegalActionError):
    """The session has spent its model tokens. Injection defence layer 6, and a cost cap."""


@dataclass
class GameSession:
    engine: Engine
    provider: NpcProvider
    token_budget: int | None = None
    """Model tokens (input + output) this session may spend. ``None``: no cap (mock mode)."""
    detective: str | None = None
    """The detective identity the player chose (D51). ``None``: the case default."""
    clock: Callable[[], float] = time.time
    """Wall clock, for timed hints. Replaced in tests."""
    tokens_used: int = field(default=0, init=False)
    state: GameState = field(init=False)
    log: list[LogEntry] = field(default_factory=list, init=False)
    transcripts: dict[CharacterId, list[Exchange]] = field(default_factory=dict, init=False)
    current_suspect: CharacterId | None = field(default=None, init=False)
    hints: list[str] = field(default_factory=list, init=False)
    """Hints given so far, oldest first (D54)."""
    last_progress_at: float = field(init=False)

    def __post_init__(self) -> None:
        try:
            self.engine.index.bundle.case.detective.identity(self.detective)
        except KeyError:
            raise IllegalActionError(f"there is no detective identity {self.detective!r}") from None
        self.state = self.engine.new_game()
        self.last_progress_at = self.clock()

    # ------------------------------------------------------------ save and resume

    def save(self) -> SavedGame:
        return SavedGame(
            detective=self.detective,
            log=tuple(self.log),
            transcripts={s: tuple(t) for s, t in self.transcripts.items()},
            current_suspect=self.current_suspect,
            tokens_used=self.tokens_used,
            hints=tuple(self.hints),
            last_progress_at=self.last_progress_at,
        )

    @classmethod
    def resume(
        cls, engine: Engine, provider: NpcProvider, token_budget: int | None, saved: SavedGame
    ) -> Self:
        """Rebuild a saved game by replaying its log. Raises ``IllegalActionError`` if the
        log no longer replays, e.g. because the case file changed since it was saved."""
        session = cls(engine, provider, token_budget, saved.detective)
        session.state = engine.replay(saved.log)
        session.log = list(saved.log)
        session.transcripts = {s: list(t) for s, t in saved.transcripts.items()}
        session.current_suspect = saved.current_suspect
        session.tokens_used = saved.tokens_used
        session.hints = list(saved.hints)
        if saved.last_progress_at is not None:
            session.last_progress_at = saved.last_progress_at
        return session

    # ------------------------------------------------------------ player actions

    def talk_to(self, suspect: CharacterId) -> Reply:
        """Start or resume an interview. The first meeting returns the opening statement."""
        first_meeting = suspect not in self.state.talked_to
        outcome = self._apply(TalkTo(suspect=suspect))
        self.current_suspect = suspect
        briefing = build_briefing(self.engine, self.state, suspect, self.detective)
        if not first_meeting:
            return Reply("", briefing.demeanor, (), (), (), (), (), outcome.events, Usage())
        # The opening statement is authored, not generated: it must put the suspect's
        # first lie on record word for word (D08), and it costs no model call.
        opening = self.engine.index.briefings[suspect].opening_statement.text
        self.transcripts.setdefault(suspect, []).append(
            Exchange(detective="", suspect=opening, demeanor=briefing.demeanor)
        )
        return Reply(opening, briefing.demeanor, (), (), (), (), (), outcome.events, Usage())

    def ask(self, text: str) -> Reply:
        if self.state.is_over:
            raise IllegalActionError("the accusation is final; the game is over")
        if self.current_suspect is None:
            raise IllegalActionError("talk to a suspect first")
        if not text.strip():
            raise IllegalActionError("say something")
        if len(text) > MAX_PLAYER_CHARS:
            raise IllegalActionError(f"keep it under {MAX_PLAYER_CHARS} characters")
        if self.token_budget is not None and self.tokens_used >= self.token_budget:
            raise BudgetExhaustedError("this session has used its model token budget")
        return self._ask(self.current_suspect, text)

    def search(self, location: LocationId) -> Outcome:
        return self._apply(SearchLocation(location=location))

    def show(self, evidence: EvidenceId) -> Reply:
        """Put evidence in front of the suspect. A catch gets the lie's authored reaction,
        word for word and with no model call (D52); otherwise they say nothing new."""
        suspect = self.current_suspect
        if suspect is None:
            raise IllegalActionError("talk to a suspect first")
        outcome = self._apply(ShowEvidence(suspect=suspect, evidence=evidence))
        ix = self.engine.index
        reaction = " ".join(
            ix.lies[e.lie].lie.on_caught.reaction
            for e in outcome.events
            if isinstance(e, LieCaught)
        )
        demeanor = build_briefing(self.engine, self.state, suspect, self.detective).demeanor
        if reaction:
            shown = ix.evidence[evidence].name
            self.transcripts.setdefault(suspect, []).append(
                Exchange(detective="", suspect=reaction, demeanor=demeanor, shown=shown)
            )
        return Reply(reaction, demeanor, (), (), (), (), (), outcome.events, Usage())

    def accuse(self, accusation: Accusation) -> Outcome:
        return self._apply(Accuse(accusation=accusation))

    # ------------------------------------------------------------ hints (D54)

    def hint_ready_at(self, policy: HintPolicy) -> float | None:
        """When the next hint unlocks under a timed policy; ``None`` for the others."""
        rule = parse_policy(policy)
        if rule.kind != "auto_after_minutes":
            return None
        return self.last_progress_at + rule.amount * 60

    def hints_left(self, policy: HintPolicy) -> int | None:
        """Hints still available under ``on_request:N``; ``None`` when not counted."""
        rule = parse_policy(policy)
        if rule.kind == "none":
            return 0
        if rule.kind == "on_request":
            return max(rule.amount - len(self.hints), 0)
        return None

    def hint(self, policy: HintPolicy) -> str:
        """The next nudge along the solution chain, if the difficulty allows one now.
        Changes nothing in the game itself: hints are help, not facts."""
        if self.state.is_over:
            raise IllegalActionError("the accusation is final; the game is over")
        if self.hints_left(policy) == 0:
            raise IllegalActionError("no hints left in this game")
        ready_at = self.hint_ready_at(policy)
        now = self.clock()
        if ready_at is not None and now < ready_at:
            minutes = math.ceil((ready_at - now) / 60)
            raise IllegalActionError(f"your next hint unlocks in about {minutes} min")
        text = next_hint(self.engine.index.bundle.solution, self.state)
        if text in self.hints:
            raise IllegalActionError("you already have the hint for where you are; see Hints")
        self.hints.append(text)
        self.last_progress_at = now
        return text

    # ------------------------------------------------------------ internals

    def _apply(self, action: Action) -> Outcome:
        outcome = self.engine.apply(self.state, action)
        self._advance(outcome.state)
        self.log.append(action)
        return outcome

    def _advance(self, state: GameState) -> None:
        """Move to a new state, noting the time if the player learned or caught something."""
        if len(state.known_facts) > len(self.state.known_facts) or len(state.caught_lies) > len(
            self.state.caught_lies
        ):
            self.last_progress_at = self.clock()
        self.state = state

    def _ask(self, suspect: CharacterId, text: str) -> Reply:
        briefing = build_briefing(self.engine, self.state, suspect, self.detective)
        history = self.transcripts.setdefault(suspect, [])
        turn = self.provider.respond(briefing, tuple(history), text)  # may raise ProviderError
        self.tokens_used += turn.usage.total_tokens
        npc = turn.reply

        # Guard first: everything after works on the line the player will actually see.
        leaks: tuple[str, ...] = ()
        dialogue = npc.dialogue
        if suspect == self.engine.index.bundle.solution.culprit:
            leaks = find_leaks(
                dialogue, self.engine.index.guarded.values(), self.state.known_facts
            ) + find_confession(dialogue, briefing.name)
            if leaks:
                dialogue = LEAK_FALLBACK

        grounding = ground(npc.reveals, dialogue, briefing.may_reveal, self._names(briefing))
        disclosure = self.engine.disclose(self.state, suspect, grounding.proposals)
        self._advance(disclosure.state)
        self.log.append(NpcReveal(suspect=suspect, reveals=grounding.proposals))

        history.append(Exchange(detective=text, suspect=dialogue, demeanor=npc.demeanor))
        return Reply(
            dialogue=dialogue,
            demeanor=npc.demeanor,
            accepted=disclosure.accepted,
            rejected=disclosure.rejected,
            leaks=leaks,
            unsupported=grounding.unsupported,
            inferred=grounding.inferred,
            events=disclosure.events,
            usage=turn.usage,
        )

    def _names(self, briefing: SuspectBriefing) -> frozenset[str]:
        """Names that don't count as overlap: the speaker says "I", and everyone says
        "him" for the victim."""
        victims = (c.name for c in self.engine.index.characters.values() if c.role == "victim")
        return speaker_words(briefing.name).union(*(speaker_words(v) for v in victims))
