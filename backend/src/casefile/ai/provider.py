"""The seam between the game and any model provider."""

from collections.abc import Sequence
from typing import Protocol

from casefile.ai.contract import Exchange, NpcTurn
from casefile.engine.briefing import SuspectBriefing


class NpcProvider(Protocol):
    """Anything that can play a suspect: the mock, Claude, or a scripted test double.

    It receives only the briefing, the conversation so far and the player's words, and
    returns a structured reply with its cost. It never sees the case files or the game
    state. On failure it raises ``ProviderError``.
    """

    def respond(
        self, briefing: SuspectBriefing, history: Sequence[Exchange], player_text: str
    ) -> NpcTurn: ...
