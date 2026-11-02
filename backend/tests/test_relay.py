"""Suspects played by the Ollama on the player's computer, through their browser (D60)."""

import json
from typing import Any

from casefile.case import CaseBundle

from .test_api import act, make_client, ok
from .test_claude_provider import GOOD


def ollama_says(payload: object, **extra: Any) -> dict[str, Any]:
    content = payload if isinstance(payload, str) else json.dumps(payload)
    return {"message": {"role": "assistant", "content": content}, "done": True, **extra}


def own_ollama_game(client: Any) -> str:
    made = client.post("/api/games", json={"played_by": "your_ollama"})
    assert made.status_code == 201
    assert made.json()["played_by"] == "your_ollama"
    game_id: str = made.json()["id"]
    ok(act(client, game_id, "talk", {"suspect": "S_RICHARD"}))
    return game_id


def test_a_question_first_returns_the_request_for_the_players_ollama(
    blackwood: CaseBundle,
) -> None:
    with make_client(blackwood) as client:
        assert ok(client.get("/api/case"))["ollama_model"] == "llama3.1:8b"
        game_id = own_ollama_game(client)
        before = ok(client.get(f"/api/games/{game_id}"))

        first = ok(act(client, game_id, "ask", {"text": "Where were you?"}))
        relay = first["relay"]
        assert first["line"] is None
        assert relay["model"] == "llama3.1:8b"
        assert relay["stream"] is False
        assert relay["messages"][0]["role"] == "system"
        assert "Where were you?" in relay["messages"][-1]["content"]
        assert first["game"] == before  # nothing happened yet

        second = ok(
            act(
                client,
                game_id,
                "ask",
                {
                    "text": "Where were you?",
                    "ollama": ollama_says(GOOD, prompt_eval_count=900, eval_count=40),
                },
            )
        )
        assert second["relay"] is None
        assert second["line"]["dialogue"] == GOOD["dialogue"]
        assert second["game"]["tokens"] == {"used": 940, "budget": None}


def test_a_broken_reply_from_the_players_ollama_changes_nothing(blackwood: CaseBundle) -> None:
    with make_client(blackwood) as client:
        game_id = own_ollama_game(client)
        before = ok(client.get(f"/api/games/{game_id}"))
        bad = act(client, game_id, "ask", {"text": "Hm?", "ollama": ollama_says("not json")})
        assert bad.status_code == 502
        cut = act(
            client,
            game_id,
            "ask",
            {"text": "Hm?", "ollama": ollama_says(GOOD, done_reason="length")},
        )
        assert cut.status_code == 502
        assert ok(client.get(f"/api/games/{game_id}")) == before


def test_the_culprits_guard_holds_for_relayed_replies(blackwood: CaseBundle) -> None:
    confession = {"reveals": [], "demeanor": "broken", "dialogue": "Fine. I killed him."}
    with make_client(blackwood) as client:
        made = client.post("/api/games", json={"played_by": "your_ollama"}).json()
        game_id = made["id"]
        ok(act(client, game_id, "talk", {"suspect": "S_VICTORIA"}))
        line = ok(
            act(client, game_id, "ask", {"text": "Did you?", "ollama": ollama_says(confession)})
        )["line"]
        assert "killed" not in line["dialogue"]


def test_other_games_ignore_a_relayed_reply(blackwood: CaseBundle) -> None:
    with make_client(blackwood) as client:  # the server's own suspects: the mock here
        made = client.post("/api/games", json={}).json()
        game_id = made["id"]
        ok(act(client, game_id, "talk", {"suspect": "S_RICHARD"}))
        line = ok(act(client, game_id, "ask", {"text": "Where?", "ollama": ollama_says(GOOD)}))[
            "line"
        ]
        assert line["dialogue"] != GOOD["dialogue"]
