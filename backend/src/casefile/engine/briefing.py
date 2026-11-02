"""Build the per-turn ``SuspectBriefing``: the only thing the AI layer ever sees (D03).

Context gating is the strongest prompt-injection defence we have: the model cannot leak
what it was never given. So the briefing holds what this suspect may say *right now*:
facts they may reveal, a vague hint of what they are withholding, the lies they are
keeping up, and nothing else. Gated facts that are still locked, other suspects'
knowledge and the solution never enter it. The culprit alone also gets their guarded
facts, because a liar must know what they are hiding (D06).
"""

from pydantic import BaseModel, ConfigDict

from casefile.case.conditions import holds
from casefile.case.ids import CharacterId, EvidenceId, FactId, LieId
from casefile.case.world import Detective
from casefile.engine.engine import Engine
from casefile.engine.state import GameState


class _Brief(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RevealableFact(_Brief):
    id: FactId
    statement: str
    already_told: bool
    """The player already has this fact; the suspect may repeat it but needn't reveal it."""


class LieToKeep(_Brief):
    id: LieId
    claim: str


class ShownItem(_Brief):
    id: EvidenceId
    name: str
    summary: str


class SuspectBriefing(_Brief):
    suspect: CharacterId
    name: str
    public_bio: str
    persona_summary: str
    voice: str
    sample_lines: tuple[str, ...]
    demeanor: str
    detective: str
    setting: str
    present: tuple[str, ...]
    """Names of everyone in the house. The closed world: nobody else exists."""
    offstage: tuple[str, ...]
    named_objects: tuple[str, ...]
    may_reveal: tuple[RevealableFact, ...]
    withholding: tuple[str, ...]
    """What the suspect knows they are holding back, phrased without the fact itself."""
    lies_to_keep: tuple[LieToKeep, ...]
    caught_out_on: tuple[str, ...]
    """Claims the player has already disproved; the suspect must not repeat them."""
    shown_evidence: tuple[ShownItem, ...]
    secrets: tuple[str, ...]
    """Guarded facts, second person. Empty for everyone but the culprit."""


def build_briefing(
    engine: Engine, state: GameState, suspect: CharacterId, detective: str | None = None
) -> SuspectBriefing:
    """``detective`` is the identity the player chose (D51); ``None`` is the case default."""
    ix = engine.index
    case = ix.bundle.case
    b = ix.briefings[suspect]
    character = ix.characters[suspect]
    allowed = engine.allowed_reveals(state, suspect)
    broken = holds(b.breaking_point.when, state, suspect)

    ordered = [*b.shares_freely, *(g.fact for g in b.gated), *b.breaking_point.reveal]
    may_reveal = tuple(
        RevealableFact(id=f, statement=ix.facts[f].statement, already_told=f in state.known_facts)
        for f in dict.fromkeys(ordered)
        if f in allowed
    )
    return SuspectBriefing(
        suspect=suspect,
        name=character.name,
        public_bio=character.public_bio,
        persona_summary=b.persona.summary,
        voice=b.persona.voice,
        sample_lines=b.persona.sample_lines,
        demeanor=b.breaking_point.demeanor if broken else b.persona.default_demeanor,
        detective=_detective(case.detective, detective),
        setting=f"{case.setting.place}, {case.setting.date:%A %d %B %Y}. {case.setting.intro}",
        present=tuple(ix.characters[c].name for c in case.world.present),
        offstage=case.world.offstage,
        named_objects=case.world.named_objects,
        may_reveal=may_reveal,
        withholding=tuple(g.withheld_hint for g in b.gated if g.fact not in allowed),
        lies_to_keep=tuple(
            LieToKeep(id=lie.id, claim=lie.claim)
            for lie in b.lies
            if lie.id in state.told_lies and lie.id not in state.caught_lies
        ),
        caught_out_on=tuple(lie.claim for lie in b.lies if lie.id in state.caught_lies),
        shown_evidence=tuple(
            ShownItem(id=e, name=ix.evidence[e].name, summary=ix.evidence[e].summary)
            for e in sorted(state.shown_to(suspect))
        ),
        secrets=tuple(g.statement for g in ix.guarded.values())
        if suspect == ix.bundle.solution.culprit
        else (),
    )


def _detective(detective: Detective, identity_id: str | None) -> str:
    """Name and pronouns, so the suspect refers to the detective the way the player chose."""
    identity = detective.identity(identity_id)
    return f"{detective.full_name(identity)} ({identity.pronouns})"
