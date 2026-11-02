"""Claude on the player's own API key (D58).

On the public server the players pay for their own suspects: the browser sends the
player's key with each question, and this provider makes that one call with it. The key
lives only for the request. It is never saved, logged or put in a game, so a restart, a
save file or a log can't leak it, and a player who closes the tab takes it with them.

The key reaches the provider through a context variable set around the request, so
``GameSession`` and the ``NpcProvider`` protocol don't change: a game played on a
player's key is the same game as any other.
"""

from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from contextvars import ContextVar

import anthropic

from casefile.ai.claude import ClaudeNpc
from casefile.ai.contract import Exchange, NpcTurn
from casefile.engine.briefing import SuspectBriefing
from casefile.settings import Settings

MAX_KEY_CHARS = 256

_key: ContextVar[str | None] = ContextVar("player_key", default=None)


class MissingKeyError(Exception):
    """The server plays suspects on the player's key, and none came with the request."""


@contextmanager
def player_key(key: str | None) -> Iterator[None]:
    """Make ``key`` the key for model calls inside this block, in this thread."""
    token = _key.set(key.strip() if key else None)
    try:
        yield
    finally:
        _key.reset(token)


class PlayerKeyClaude:
    def __init__(
        self,
        settings: Settings,
        make_client: Callable[[str], anthropic.Anthropic] | None = None,
    ) -> None:
        self._settings = settings
        self._make_client = make_client or (
            lambda key: anthropic.Anthropic(api_key=key, timeout=settings.request_timeout_s)
        )

    def respond(
        self, briefing: SuspectBriefing, history: Sequence[Exchange], player_text: str
    ) -> NpcTurn:
        key = _key.get()
        if not key:
            raise MissingKeyError
        client = self._make_client(key)
        try:
            return ClaudeNpc(self._settings, client).respond(briefing, history, player_text)
        finally:
            client.close()
