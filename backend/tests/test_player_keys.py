"""Claude on the player's own API key (D58): used for one call, never kept."""

import json
import threading
from pathlib import Path
from typing import Any, cast

import anthropic
import httpx2

from casefile.ai.player_key import PlayerKeyClaude
from casefile.api.saves import SaveFile
from casefile.case import CaseBundle
from casefile.settings import Settings

from .test_api import act, make_client, new_game, ok
from .test_claude_provider import GOOD, FakeClient, message

KEY = "sk-ant-api03-player-own-key"


class Keys:
    """Builds fake clients and remembers which key each was built with."""

    def __init__(self, result: object = None) -> None:
        self.result = result if result is not None else message(GOOD)
        self.seen: list[str] = []
        self.closed = 0

    def __call__(self, key: str) -> anthropic.Anthropic:
        self.seen.append(key)
        fake = FakeClient(cast(Any, self.result))
        fake.close = self._close  # type: ignore[attr-defined]
        return cast(anthropic.Anthropic, fake)

    def _close(self) -> None:
        self.closed += 1


def interview(client: Any) -> str:
    game_id = new_game(client)
    ok(act(client, game_id, "talk", {"suspect": "S_RICHARD"}))
    return game_id


def ask(client: Any, game_id: str, key: str | None) -> httpx2.Response:
    headers = {"X-Claude-Key": key} if key is not None else {}
    return cast(
        httpx2.Response,
        client.post(f"/api/games/{game_id}/ask", json={"text": "Where were you?"}, headers=headers),
    )


def test_the_cover_says_when_players_bring_a_key(blackwood: CaseBundle) -> None:
    with make_client(blackwood, PlayerKeyClaude(Settings()), player_keys=True) as client:
        assert ok(client.get("/api/case"))["player_keys"] is True
    with make_client(blackwood) as client:
        assert ok(client.get("/api/case"))["player_keys"] is False


def test_each_question_uses_the_key_it_came_with(blackwood: CaseBundle) -> None:
    keys = Keys()
    provider = PlayerKeyClaude(Settings(), keys)
    with make_client(blackwood, provider, player_keys=True) as client:
        game_id = interview(client)
        line = ok(ask(client, game_id, f"  {KEY}  "))["line"]
        assert line["dialogue"] == GOOD["dialogue"]
        ok(ask(client, game_id, "sk-ant-another-key"))
    assert keys.seen == [KEY, "sk-ant-another-key"]
    assert keys.closed == 2


def test_no_key_is_a_401_and_changes_nothing(blackwood: CaseBundle) -> None:
    provider = PlayerKeyClaude(Settings(), Keys())
    with make_client(blackwood, provider, player_keys=True) as client:
        game_id = interview(client)
        before = ok(client.get(f"/api/games/{game_id}"))
        for key in (None, "", "   "):
            refused = ask(client, game_id, key)
            assert refused.status_code == 401
            assert "your own Claude API key" in refused.json()["detail"]
        assert ok(client.get(f"/api/games/{game_id}")) == before


def test_a_refused_key_is_a_401(blackwood: CaseBundle) -> None:
    refused = anthropic.AuthenticationError(
        "invalid x-api-key",
        response=httpx2.Response(401, request=httpx2.Request("POST", "https://x")),
        body=None,
    )
    provider = PlayerKeyClaude(Settings(), Keys(refused))
    with make_client(blackwood, provider, player_keys=True) as client:
        game_id = interview(client)
        answer = ask(client, game_id, KEY)
        assert answer.status_code == 401
        assert "refused your Claude API key" in answer.json()["detail"]


def test_a_server_without_player_keys_ignores_the_header(blackwood: CaseBundle) -> None:
    keys = Keys()
    provider = PlayerKeyClaude(Settings(), keys)
    with make_client(blackwood, provider) as client:  # player_keys off
        game_id = interview(client)
        assert ask(client, game_id, KEY).status_code == 401
    assert keys.seen == []


def test_the_key_is_never_saved(blackwood: CaseBundle, tmp_path: Path) -> None:
    path = tmp_path / "games.sqlite3"
    provider = PlayerKeyClaude(Settings(), Keys())
    saves = SaveFile(path, "blackwood-001", keep_days=30)
    with make_client(blackwood, provider, player_keys=True, saves=saves) as client:
        game_id = interview(client)
        ok(ask(client, game_id, KEY))
        assert KEY not in json.dumps(ok(client.get(f"/api/games/{game_id}")))
    assert KEY.encode() not in path.read_bytes()


def test_keys_do_not_cross_between_threads(blackwood: CaseBundle) -> None:
    keys = Keys()
    provider = PlayerKeyClaude(Settings(), keys)
    with make_client(blackwood, provider, player_keys=True) as client:
        games = [interview(client) for _ in range(8)]
        results: dict[str, int] = {}

        def play(i: int) -> None:
            results[f"key-{i}"] = ask(client, games[i], f"key-{i}").status_code

        threads = [threading.Thread(target=play, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    assert set(results.values()) == {200}
    assert sorted(keys.seen) == sorted(results)
