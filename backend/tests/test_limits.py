"""Rate limits per visitor and the built web game served by the API (D57)."""

from pathlib import Path

import pytest

from casefile.api.app import Limits
from casefile.api.limits import RateLimitedError, RateLimiter
from casefile.case import CaseBundle

from .test_api import act, make_client, new_game, ok


class Clock:
    def __init__(self) -> None:
        self.now = 1_000.0

    def __call__(self) -> float:
        return self.now


def test_a_visitor_gets_limit_hits_per_window() -> None:
    clock = Clock()
    limiter = RateLimiter(2, 60, clock=clock)
    limiter.hit("a")
    limiter.hit("a")
    with pytest.raises(RateLimitedError) as refused:
        limiter.hit("a")
    assert refused.value.retry_after_s == 60
    limiter.hit("b")  # another visitor has their own count

    clock.now += 30
    with pytest.raises(RateLimitedError) as refused:
        limiter.hit("a")
    assert refused.value.retry_after_s == 30  # refusals don't count against them
    clock.now += 30
    limiter.hit("a")


def test_too_many_moves_get_429_with_retry_after(blackwood: CaseBundle) -> None:
    limits = Limits(new_games=RateLimiter(1, 3600), actions=RateLimiter(2, 60))
    with make_client(blackwood, limits=limits) as client:
        game_id = new_game(client)
        assert client.post("/api/games", json={"difficulty": "normal"}).status_code == 429

        ok(act(client, game_id, "talk", {"suspect": "S_RICHARD"}))
        ok(act(client, game_id, "search", {"location": "LOC_STUDY"}))
        refused = act(client, game_id, "ask", {"text": "Where were you?"})
        assert refused.status_code == 429
        assert int(refused.headers["Retry-After"]) > 0
        assert "too many requests" in refused.json()["detail"]
        ok(client.get(f"/api/games/{game_id}"))  # reading a game is never limited


@pytest.fixture
def dist(tmp_path: Path) -> Path:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<!doctype html><title>CASEFILE</title>")
    (tmp_path / "assets" / "index-abc123.js").write_text("console.log(1)")
    return tmp_path


def test_the_web_game_is_served_with_the_api(blackwood: CaseBundle, dist: Path) -> None:
    with make_client(blackwood, web=dist) as client:
        page = client.get("/")
        assert page.status_code == 200
        assert "<title>CASEFILE</title>" in page.text
        assert page.headers["Cache-Control"] == "no-cache"

        # A reload deep in the game gets the page; the Vue router takes it from there.
        assert client.get("/game/some-id").text == page.text

        asset = client.get("/assets/index-abc123.js")
        assert asset.text == "console.log(1)"
        assert "immutable" in asset.headers["Cache-Control"]

        assert ok(client.get("/api/case"))["title"]
        missing = client.get("/api/no-such-route")
        assert missing.status_code == 404
        assert missing.headers["content-type"] == "application/json"


def test_without_web_the_server_is_api_only(blackwood: CaseBundle) -> None:
    with make_client(blackwood) as client:
        assert client.get("/").status_code == 404
