"""The HTTP API: CASE #001 is winnable over HTTP, and nothing secret reaches the browser."""

import json
import re
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from httpx2 import Response

from casefile.ai.contract import Exchange, NpcReply, NpcTurn, ProviderError, Usage
from casefile.ai.mock import MockNpc
from casefile.ai.provider import NpcProvider
from casefile.api.app import Limits, create_app, main
from casefile.api.portraits import Portraits
from casefile.api.saves import SaveFile
from casefile.api.store import GameBusyError, GameNotFoundError, GameStore, StoreFullError
from casefile.case import CaseBundle
from casefile.engine import Engine
from casefile.engine.briefing import SuspectBriefing
from casefile.session import MAX_PLAYER_CHARS, GameSession

WINNING_ACCUSATION = {
    "culprit": "S_VICTORIA",
    "motive": "MOT_HIDE_THEFT",
    "method": "MTH_AWARD_STAGED",
    "evidence": ["E05", "E10", "E02", "E03"],
}

WINNING_RUN: list[tuple[str, dict[str, Any]]] = [
    ("talk", {"suspect": "S_THOMAS"}),
    ("ask", {"text": "Did you hear Arthur's voice through the intercom?"}),
    ("search", {"location": "LOC_STUDY"}),
    ("search", {"location": "LOC_HALL"}),
    ("talk", {"suspect": "S_VICTORIA"}),
    ("show", {"evidence": "E05"}),
    ("show", {"evidence": "E04"}),
    ("show", {"evidence": "E10"}),
    ("search", {"location": "LOC_GUEST_ROOM_2"}),
    ("show", {"evidence": "E11"}),
]


def make_client(
    blackwood: CaseBundle,
    provider: NpcProvider | None = None,
    *,
    token_budget: int | None = None,
    max_games: int = 10,
    saves: SaveFile | None = None,
    portraits: Portraits | None = None,
    limits: Limits | None = None,
    web: Path | None = None,
    player_keys: bool = False,
) -> TestClient:
    app = create_app(
        Engine(blackwood),
        provider or MockNpc(),
        ai="mock",
        token_budget=token_budget,
        max_games=max_games,
        idle_ttl_s=3600,
        saves=saves,
        portraits=portraits,
        limits=limits,
        web=web,
        player_keys=player_keys,
    )
    return TestClient(app)


@pytest.fixture
def client(blackwood: CaseBundle) -> Iterator[TestClient]:
    with make_client(blackwood) as c:
        yield c


def new_game(client: TestClient, difficulty: str = "normal") -> str:
    response = client.post("/api/games", json={"difficulty": difficulty})
    assert response.status_code == 201
    game_id: str = response.json()["id"]
    return game_id


def act(client: TestClient, game_id: str, verb: str, body: dict[str, Any]) -> Response:
    return client.post(f"/api/games/{game_id}/{verb}", json=body)


def ok(response: Response) -> dict[str, Any]:
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


# ------------------------------------------------------------------ playing


def test_the_case_is_winnable_over_http(client: TestClient, blackwood: CaseBundle) -> None:
    game_id = new_game(client)
    caught = 0
    for verb, body in WINNING_RUN:
        events = ok(act(client, game_id, verb, body))["events"]
        caught += sum(e["type"] == "lie_caught" for e in events)
    assert caught == 3

    final = ok(act(client, game_id, "accuse", {"accusation": WINNING_ACCUSATION}))
    assert final["events"][-1] == {"type": "accusation_scored", "total": 100}
    assert final["game"]["over"] is True
    assert final["game"]["result"]["total"] == 100
    out_of = final["game"]["result"]["out_of"]
    assert sum(out_of.values()) == 100
    assert final["game"]["result"]["epilogue"] == blackwood.solution.epilogue

    # The accusation is final (D10), and a finished game makes no model calls.
    assert act(client, game_id, "ask", {"text": "Anything to add?"}).status_code == 409


def test_the_first_meeting_is_the_opening_statement(
    client: TestClient, blackwood: CaseBundle
) -> None:
    game_id = new_game(client)
    first = ok(act(client, game_id, "talk", {"suspect": "S_RICHARD"}))
    (richard,) = [b for b in blackwood.briefings.suspects if b.suspect == "S_RICHARD"]
    assert first["line"]["dialogue"] == richard.opening_statement.text
    assert [e["type"] for e in first["events"]] == ["lie_on_record"]
    assert first["game"]["statements"][0]["caught"] is False
    assert first["game"]["interviews"]["S_RICHARD"][0]["detective"] == ""

    again = ok(act(client, game_id, "talk", {"suspect": "S_RICHARD"}))
    assert again["line"] is None  # resuming an interview says nothing new
    assert again["events"] == []


def test_a_game_can_be_fetched_again(client: TestClient) -> None:
    game_id = new_game(client, "easy")
    ok(act(client, game_id, "search", {"location": "LOC_STUDY"}))
    game = ok(client.get(f"/api/games/{game_id}"))
    assert game["difficulty"] == "easy"
    assert game["help"]["contradictions"] == "auto_flag"
    assert {loc["id"] for loc in game["locations"] if loc["searched"]} == {"LOC_STUDY"}
    assert game["tokens"] == {"used": 0, "budget": None}


def test_the_case_cover(client: TestClient, blackwood: CaseBundle) -> None:
    case = ok(client.get("/api/case"))
    assert case["title"] == blackwood.case.title
    assert case["ai"] == "mock"
    assert case["max_question_chars"] == MAX_PLAYER_CHARS
    assert len(case["accusation"]["motives"]) == len(blackwood.case.accusation_options.motives)


# ------------------------------------------------------------------ the spoiler boundary


class SnoopingNpc:
    """A model that tries everything: proposes guarded and invented IDs, and the culprit
    blurts out a leak marker. None of it may reach the player."""

    def respond(
        self, briefing: SuspectBriefing, history: Sequence[Exchange], player_text: str
    ) -> NpcTurn:
        line = "I killed him." if briefing.secrets else "I was in the billiard room."
        return NpcTurn(
            reply=NpcReply(reveals=("G_01", "F_MADE_UP"), demeanor="calm", dialogue=line)
        )


def secrets_of(blackwood: CaseBundle) -> list[str]:
    """Strings that would spoil the case if the API ever sent them before the end."""
    sol = blackwood.solution
    found: list[str] = [sol.epilogue]
    for g in sol.guarded_facts:
        found += [g.id, g.statement]
    for b in blackwood.briefings.suspects:
        found += [b.persona.summary, *(g.withheld_hint for g in b.gated)]
        found += [lie.why for lie in b.lies]
    found += [step.hint for step in sol.solution_chain]
    return found


@pytest.mark.parametrize("provider", [MockNpc(), SnoopingNpc()], ids=["mock", "snooping"])
def test_nothing_secret_reaches_the_browser(blackwood: CaseBundle, provider: NpcProvider) -> None:
    """Every response of a whole game: no guarded fact, briefing text, lie motive, hint or
    epilogue, and no fact, evidence item or lie before the game has announced it, even
    with a model that tries to leak."""
    secrets = secrets_of(blackwood)
    facts = {f.id: f.statement for f in blackwood.case.facts}
    items = {e.id: e.summary for e in blackwood.case.evidence}
    lies = {lie.id: lie.claim for b in blackwood.briefings.suspects for lie in b.lies}
    found = {str(e) for e in Engine(blackwood).new_game().found_evidence}
    told: set[str] = set()

    def check(text: str) -> None:
        assert not [s for s in secrets if s in text]
        payload = json.loads(text)
        for event in payload.get("events", []):
            found.update([event["evidence"]] if event["type"] == "evidence_found" else [])
            told.update([event["lie"]] if event["type"] == "lie_on_record" else [])
        game = payload.get("game", payload)
        known = {e["fact"] for e in game.get("notebook", [])}
        sent = set(re.findall(r"\bF_[A-Z0-9_]+\b", text))
        assert sent <= known, f"facts sent before they were learned: {sent - known}"
        assert not [f for f, statement in facts.items() if f not in known and statement in text]
        assert not [e for e, summary in items.items() if e not in found and summary in text]
        assert not [lie for lie, claim in lies.items() if lie not in told and claim in text]
        assert {e["id"] for e in game.get("evidence", [])} <= found
        assert {s["lie"] for s in game.get("statements", [])} <= told

    with make_client(blackwood, provider) as client:
        game_id = new_game(client)
        check(client.get("/api/case").text)
        check(client.get(f"/api/games/{game_id}").text)
        for verb, body in WINNING_RUN:
            check(act(client, game_id, verb, body).text)
            reply = act(client, game_id, "ask", {"text": "Tell me everything."}).text
            check(reply)
            assert "I killed him" not in reply  # the culprit's guard replaced the line
            check(client.get(f"/api/games/{game_id}").text)
    assert found > {str(e) for e in Engine(blackwood).new_game().found_evidence}
    assert len(told) >= 2


# ------------------------------------------------------------------ errors


def test_errors_explain_themselves(client: TestClient) -> None:
    game_id = new_game(client)
    assert client.get("/api/games/nope").status_code == 404
    response = act(client, game_id, "ask", {"text": "Hello?"})
    assert (response.status_code, response.json()) == (409, {"detail": "talk to a suspect first"})
    assert act(client, game_id, "search", {"location": "LOC_GUEST_ROOM_2"}).status_code == 409
    assert act(client, game_id, "talk", {"suspect": "S_NOBODY"}).status_code == 409
    assert act(client, game_id, "talk", {"suspect": "richard"}).status_code == 422
    assert act(client, game_id, "show", {"evidence": "E01", "extra": 1}).status_code == 422
    ok(act(client, game_id, "talk", {"suspect": "S_RICHARD"}))
    too_long = act(client, game_id, "ask", {"text": "x" * (MAX_PLAYER_CHARS + 1)})
    assert too_long.status_code == 409
    assert act(client, game_id, "show", {"evidence": "E11"}).status_code == 409  # not found yet


class FailingNpc:
    def respond(
        self, briefing: SuspectBriefing, history: Sequence[Exchange], player_text: str
    ) -> NpcTurn:
        raise ProviderError("api", "is Ollama running?")


class MeteredNpc:
    def respond(
        self, briefing: SuspectBriefing, history: Sequence[Exchange], player_text: str
    ) -> NpcTurn:
        reply = NpcReply(demeanor="calm", dialogue="Ask me something else, Inspector.")
        return NpcTurn(reply=reply, usage=Usage(input_tokens=900, output_tokens=100))


def test_a_provider_failure_changes_nothing(blackwood: CaseBundle) -> None:
    with make_client(blackwood, FailingNpc()) as client:
        game_id = new_game(client)
        before = ok(act(client, game_id, "talk", {"suspect": "S_RICHARD"}))["game"]
        response = act(client, game_id, "ask", {"text": "Where were you?"})
        assert response.status_code == 502
        assert "nothing changed" in response.json()["detail"]
        assert ok(client.get(f"/api/games/{game_id}")) == before


def test_the_token_budget_stops_a_game(blackwood: CaseBundle) -> None:
    with make_client(blackwood, MeteredNpc(), token_budget=1000) as client:
        game_id = new_game(client)
        ok(act(client, game_id, "talk", {"suspect": "S_RICHARD"}))
        first = ok(act(client, game_id, "ask", {"text": "Where were you?"}))
        assert first["game"]["tokens"] == {"used": 1000, "budget": 1000}
        assert act(client, game_id, "ask", {"text": "And then?"}).status_code == 429


def test_a_full_server_refuses_new_games(blackwood: CaseBundle) -> None:
    with make_client(blackwood, max_games=1) as client:
        new_game(client)
        assert client.post("/api/games", json={}).status_code == 503


# ------------------------------------------------------------------ the store


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


def make_store(blackwood: CaseBundle, clock: Clock, max_games: int = 2) -> GameStore:
    engine = Engine(blackwood)
    return GameStore(
        lambda d: GameSession(engine, MockNpc(), detective=d),
        lambda saved: GameSession.resume(engine, MockNpc(), None, saved),
        max_games=max_games,
        idle_ttl_s=60,
        clock=clock,
    )


def test_a_busy_game_refuses_a_second_request(blackwood: CaseBundle) -> None:
    store = make_store(blackwood, Clock())
    game_id = store.create("normal")
    with store.use(game_id), pytest.raises(GameBusyError), store.use(game_id):
        pass
    with store.use(game_id):  # released afterwards
        pass


def test_idle_games_expire_but_busy_ones_do_not(blackwood: CaseBundle) -> None:
    clock = Clock()
    store = make_store(blackwood, clock)
    idle, busy = store.create("normal"), store.create("normal")
    with pytest.raises(StoreFullError):
        store.create("normal")

    with store.use(busy):
        clock.now = 61
        store.create("normal")  # makes room by dropping the idle game only
    with pytest.raises(GameNotFoundError), store.use(idle):
        pass
    with store.use(busy):
        pass
    assert len(store) == 2


def test_the_schema_can_be_written_for_the_frontend(tmp_path: Path) -> None:
    out = tmp_path / "openapi.json"
    main(["--openapi", str(out)])
    schema = json.loads(out.read_text(encoding="utf-8"))
    assert "/api/games/{game_id}/ask" in schema["paths"]
    assert "GameOut" in schema["components"]["schemas"]


@pytest.mark.parametrize(("difficulty", "flagged"), [("easy", True), ("normal", False)])
def test_easy_flags_a_claim_that_held_evidence_disproves(
    client: TestClient, difficulty: str, flagged: bool
) -> None:
    game_id = new_game(client, difficulty)
    for verb, body in WINNING_RUN[:5]:  # up to meeting Victoria, with the wall panel held
        game = ok(act(client, game_id, verb, body))["game"]
    flags = {s["lie"]: s["flagged"] for s in game["statements"]}
    assert flags["LIE_VICTORIA_NO_CONTACT"] is flagged
    assert flags["LIE_THOMAS_PANTRY"] is False  # nothing held disproves it yet

    game = ok(act(client, game_id, "show", {"evidence": "E05"}))["game"]
    caught = {s["lie"]: s for s in game["statements"]}["LIE_VICTORIA_NO_CONTACT"]
    assert caught["caught"] is True
    assert caught["flagged"] is False  # a caught lie needs no flag


def test_the_player_chooses_who_the_detective_is(client: TestClient, blackwood: CaseBundle) -> None:
    cover = ok(client.get("/api/case"))["detective"]
    assert [i["id"] for i in cover["identities"]] == ["woman", "man", "nonbinary"]

    default = ok(client.get(f"/api/games/{new_game(client)}"))
    assert default["detective"]["name"] == "DI Rhea Voss"

    response = client.post("/api/games", json={"detective": "man"})
    assert response.status_code == 201
    assert response.json()["detective"] == {
        "id": "man",
        "label": "Man",
        "name": "DI Rhys Voss",
        "pronouns": "he/him",
        "bio": blackwood.case.detective.identity("man").bio,
    }
    unknown = client.post("/api/games", json={"detective": "wizard"})
    assert unknown.status_code == 409
