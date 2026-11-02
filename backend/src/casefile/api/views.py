"""Project the engine's state into what the player may see (D44).

This module is the API's spoiler boundary. It reads the case through the engine's
index, but only ever emits: the public cover of the case, evidence the player holds,
facts already in the notebook, lies already on record, and the epilogue once the game
is over. Locked facts, briefings, a lie's ``why``, guarded facts and the answer key
never leave it, and ``test_api.py`` checks that over a whole game.
"""

from casefile.case.base import TimeSpan
from casefile.case.conditions import holds
from casefile.case.ids import CharacterId, EvidenceId
from casefile.case.rules import location_accessible
from casefile.engine.engine import Engine
from casefile.engine.events import (
    AccusationScored,
    Event,
    EvidenceFound,
    FactLearned,
    LieCaught,
    LieOnRecord,
    LocationSearched,
)
from casefile.engine.state import GameState, Source
from casefile.session import GameSession, Reply

from .schemas import (
    AccusationOptionsOut,
    AccusationScoredOut,
    CaseOut,
    DetectiveOut,
    Difficulty,
    EventOut,
    EvidenceFoundOut,
    EvidenceOut,
    ExchangeOut,
    FactLearnedOut,
    GameOut,
    LieCaughtOut,
    LieOnRecordOut,
    LineOut,
    LocationOut,
    LocationSearchedOut,
    NotebookEntryOut,
    OptionOut,
    PersonOut,
    ResultOut,
    StatementOut,
    SuspectOut,
    TimeOut,
    TokensOut,
)


def case_view(engine: Engine, ai: str) -> CaseOut:
    case = engine.index.bundle.case
    options = case.accusation_options
    return CaseOut(
        id=case.case_id,
        title=case.title,
        place=case.setting.place,
        date=case.setting.date.isoformat(),
        intro=case.setting.intro,
        detective=DetectiveOut(
            name=case.detective.name, callsign=case.detective.callsign, bio=case.detective.bio
        ),
        people=tuple(
            PersonOut(id=c.id, name=c.name, age=c.age, bio=c.public_bio, role=c.role)
            for c in case.characters
        ),
        accusation=AccusationOptionsOut(
            culprits=options.culprits,
            motives=tuple(OptionOut(id=m.id, label=m.label) for m in options.motives),
            methods=tuple(OptionOut(id=m.id, label=m.label) for m in options.methods),
            max_evidence=options.max_evidence,
        ),
        ai=ai,
    )


def game_view(game_id: str, difficulty: Difficulty, session: GameSession) -> GameOut:
    ix = session.engine.index
    state = session.state
    profiles = ix.bundle.case.difficulty_profiles
    help_ = {"easy": profiles.easy, "normal": profiles.normal, "hard": profiles.hard}
    return GameOut(
        id=game_id,
        difficulty=difficulty,
        help=help_[difficulty],
        over=state.is_over,
        current_suspect=session.current_suspect,
        suspects=tuple(
            SuspectOut(id=s, name=ix.characters[s].name, interviewed=s in state.talked_to)
            for s in ix.briefings
        ),
        locations=tuple(
            LocationOut(
                id=loc.id,
                name=loc.name,
                description=loc.description,
                accessible=location_accessible(loc, state),
                searched=loc.id in state.searched_locations,
            )
            for loc in ix.locations.values()
        ),
        evidence=_evidence(session.engine, state),
        notebook=tuple(
            NotebookEntryOut(
                fact=entry.fact,
                statement=ix.facts[entry.fact].statement,
                source=entry.source,
                source_name=_source_name(session.engine, entry.source),
                time=_time(ix.facts[entry.fact].time),
            )
            for entry in state.notebook
        ),
        statements=tuple(
            StatementOut(
                lie=lie_id,
                suspect=ix.lies[lie_id].suspect,
                claim=ix.lies[lie_id].lie.claim,
                caught=lie_id in state.caught_lies,
            )
            for lie_id in ix.lies  # case order, so the list doesn't reshuffle between turns
            if lie_id in state.told_lies
        ),
        interviews={
            suspect: tuple(
                ExchangeOut(detective=x.detective, suspect=x.suspect, demeanor=x.demeanor)
                for x in exchanges
            )
            for suspect, exchanges in session.transcripts.items()
        },
        tokens=TokensOut(used=session.tokens_used, budget=session.token_budget),
        result=_result(session.engine, state),
    )


def line_view(session: GameSession, reply: Reply) -> LineOut | None:
    """The suspect's line, if the action produced one. Only dialogue and demeanor leave:
    the reply's leak, grounding and rejection details would tell the player who the
    culprit is (D45)."""
    if not reply.dialogue or session.current_suspect is None:
        return None
    return LineOut(
        suspect=session.current_suspect, dialogue=reply.dialogue, demeanor=reply.demeanor
    )


def events_view(engine: Engine, events: tuple[Event, ...]) -> tuple[EventOut, ...]:
    ix = engine.index
    out: list[EventOut] = []
    for e in events:
        match e:
            case FactLearned(fact=fact, source=source):
                out.append(
                    FactLearnedOut(fact=fact, statement=ix.facts[fact].statement, source=source)
                )
            case EvidenceFound(evidence=ev):
                out.append(EvidenceFoundOut(evidence=ev, name=ix.evidence[ev].name))
            case LocationSearched(location=loc):
                out.append(LocationSearchedOut(location=loc, name=ix.locations[loc].name))
            case LieOnRecord(suspect=suspect, lie=lie):
                out.append(LieOnRecordOut(suspect=suspect, lie=lie, claim=ix.lies[lie].lie.claim))
            case LieCaught(suspect=suspect, lie=lie, evidence=ev):
                out.append(
                    LieCaughtOut(
                        suspect=suspect, lie=lie, claim=ix.lies[lie].lie.claim, evidence=ev
                    )
                )
            case AccusationScored(score=score):
                out.append(AccusationScoredOut(total=score.total))
    return tuple(out)


# ------------------------------------------------------------------ helpers


def _evidence(engine: Engine, state: GameState) -> tuple[EvidenceOut, ...]:
    ix = engine.index
    return tuple(
        EvidenceOut(
            id=ev.id,
            name=ev.name,
            location=ev.location,
            summary=ev.summary,
            text=ev.text,
            reads=tuple(read.text for read in ev.deeper_reads if holds(read.when, state)),
        )
        for ev in ix.evidence.values()
        if ev.id in state.found_evidence
    )


def _source_name(engine: Engine, source: Source) -> str:
    ix = engine.index
    evidence = ix.evidence.get(EvidenceId(source))
    return evidence.name if evidence else ix.characters[CharacterId(source)].name


def _time(span: TimeSpan | None) -> TimeOut | None:
    if span is None:
        return None
    return TimeOut(
        start=f"{span.start:%H:%M}",
        end=None if span.end is None else f"{span.end:%H:%M}",
        approx=span.precision == "approx",
    )


def _result(engine: Engine, state: GameState) -> ResultOut | None:
    if state.final is None:
        return None
    score = state.final.score
    return ResultOut(
        culprit=score.culprit,
        motive=score.motive,
        method=score.method,
        evidence=score.evidence,
        total=score.total,
        groups_covered=score.groups_covered,
        epilogue=engine.index.bundle.solution.epilogue,
    )
