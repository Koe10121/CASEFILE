"""Portraits and expressions (D55)."""

import json
from pathlib import Path

from casefile.api.portraits import find_portraits
from casefile.case import CaseBundle
from casefile.case.ids import CharacterId
from casefile.expressions import KNOWN_DEMEANORS, expression_for

from .test_api import act, make_client, new_game, ok

CASE = Path(__file__).resolve().parents[2] / "cases" / "blackwood_manor"


def test_every_authored_demeanor_has_a_face() -> None:
    """A demeanour the author writes should map on purpose, not fall through to neutral.
    A new word in a case fails here until it is added to ``expressions.py``."""
    text = (CASE / "briefings.json").read_text(encoding="utf-8")
    words: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                if key in ("demeanor", "default_demeanor") and isinstance(value, str):
                    words.add(value)
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(json.loads(text))
    assert words
    for word in words:
        assert word in KNOWN_DEMEANORS, word


def test_unknown_words_show_the_neutral_face() -> None:
    assert expression_for("Hostile ") == "angry"
    assert expression_for("whimsical") == "neutral"


def portraits(tmp_path: Path) -> Path:
    folder = tmp_path / "portraits"
    (folder / "S_RICHARD").mkdir(parents=True)
    (folder / "S_RICHARD" / "neutral.webp").write_bytes(b"RIFF-neutral")
    (folder / "S_RICHARD" / "angry.png").write_bytes(b"PNG-angry")
    (folder / "S_RICHARD" / "smirk.png").write_bytes(b"not an expression")
    (folder / "S_NOBODY").mkdir()
    (folder / "S_NOBODY" / "neutral.png").write_bytes(b"not a character")
    (tmp_path / "secret.txt").write_text("keep out")
    return folder


def test_the_server_serves_only_the_portraits_it_found(
    blackwood: CaseBundle, tmp_path: Path
) -> None:
    faces = find_portraits(portraits(tmp_path), (c.id for c in blackwood.case.characters))
    with make_client(blackwood, portraits=faces) as client:
        assert ok(client.get("/api/case"))["portraits"] == {"S_RICHARD": ["neutral", "angry"]}
        image = client.get("/api/portraits/S_RICHARD/angry")
        assert image.status_code == 200
        assert image.content == b"PNG-angry"
        for path in ("S_RICHARD/sad", "S_RICHARD/smirk", "S_NOBODY/neutral", "..%2Fsecret.txt/x"):
            assert client.get(f"/api/portraits/{path}").status_code == 404


def test_a_caught_suspect_looks_shaken(blackwood: CaseBundle) -> None:
    with make_client(blackwood) as client:
        game_id = new_game(client)
        ok(act(client, game_id, "talk", {"suspect": "S_RICHARD"}))
        ok(act(client, game_id, "search", {"location": "LOC_OFFICE"}))
        caught = ok(act(client, game_id, "show", {"evidence": "E07"}))
        assert caught["line"]["expression"] == "shaken"
        interview = caught["game"]["interviews"][CharacterId("S_RICHARD")]
        assert interview[0]["expression"] == "angry"  # hostile, his opening manner
        assert interview[-1]["expression"] == "shaken"
