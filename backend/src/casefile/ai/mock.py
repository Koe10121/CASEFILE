"""A deterministic stand-in for the model, so the game runs and tests pass with no API spend.

It plays by the same contract as a real provider and only knows what the briefing gives
it. It answers by matching the player's words against the facts it may reveal; with no
match it volunteers the next fact it hasn't told yet, and once it has told everything it
falls back on its current lie or a stock line. It never proposes an ID that is not in
its briefing, so every rejection in mock mode is a bug in the engine, not the mock.
"""

import re
from collections.abc import Sequence

from casefile.ai.contract import Exchange, NpcReply, NpcTurn
from casefile.engine.briefing import RevealableFact, SuspectBriefing

_WORD = re.compile(r"[a-z0-9']+")
_STOPWORD_TEXT = "about what when where which with your have that this there they tell were from"
_STOPWORDS = frozenset(_STOPWORD_TEXT.split())
MAX_REVEALS_PER_REPLY = 2


def _keywords(text: str) -> set[str]:
    return {w for w in _WORD.findall(text.lower()) if len(w) >= 4 and w not in _STOPWORDS}


class MockNpc:
    def respond(
        self, briefing: SuspectBriefing, history: Sequence[Exchange], player_text: str
    ) -> NpcTurn:
        return NpcTurn(reply=self._reply(briefing, history, player_text))

    def _reply(
        self, briefing: SuspectBriefing, history: Sequence[Exchange], player_text: str
    ) -> NpcReply:
        reveals = self._pick(briefing.may_reveal, player_text)
        if reveals:
            dialogue = " ".join(f.statement for f in reveals)
        elif briefing.lies_to_keep:
            dialogue = briefing.lies_to_keep[-1].claim
        else:
            dialogue = briefing.sample_lines[len(history) % len(briefing.sample_lines)]
        return NpcReply(
            reveals=tuple(f.id for f in reveals), demeanor=briefing.demeanor, dialogue=dialogue
        )

    @staticmethod
    def _pick(facts: Sequence[RevealableFact], player_text: str) -> list[RevealableFact]:
        untold = [f for f in facts if not f.already_told]
        asked = _keywords(player_text)
        scored = [(len(asked & _keywords(f.statement)), i) for i, f in enumerate(untold)]
        matches = [untold[i] for score, i in sorted(scored, key=lambda s: (-s[0], s[1])) if score]
        return (matches or untold)[:MAX_REVEALS_PER_REPLY]
