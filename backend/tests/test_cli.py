"""The terminal game wins CASE #001 in mock AI mode, start to finish."""

import io
from pathlib import Path

import pytest

from casefile.ai.mock import MockNpc
from casefile.case import CaseBundle
from casefile.cli import Cli, main
from casefile.engine import Engine
from casefile.session import GameSession

WINNING_RUN = """\
talk S_THOMAS
ask Did you hear Arthur's voice through the intercom?
search LOC_STUDY
search LOC_HALL
talk S_VICTORIA
show E05
show E04
show E10
search LOC_GUEST_ROOM_2
show E11
accuse S_VICTORIA MOT_HIDE_THEFT MTH_AWARD_STAGED E05 E10 E02 E03
"""


def play(blackwood: CaseBundle, script: str) -> str:
    out = io.StringIO()
    Cli(GameSession(Engine(blackwood), MockNpc()), out).run(script.splitlines())
    return out.getvalue()


def test_the_case_is_winnable_from_the_terminal(blackwood: CaseBundle) -> None:
    transcript = play(blackwood, WINNING_RUN)
    assert transcript.count("! caught:") == 3
    assert "Score 100/100" in transcript
    assert blackwood.solution.epilogue in transcript


def test_bad_commands_explain_themselves(blackwood: CaseBundle) -> None:
    transcript = play(blackwood, "dance\nshow E01\nsearch LOC_GUEST_ROOM_2\ntalk S_NOBODY\n")
    assert "Unknown command 'dance'" in transcript
    assert "! talk to a suspect first" in transcript
    assert "! Guest room 2 (Victoria's) is not accessible yet" in transcript
    assert "! S_NOBODY is not a suspect you can interview" in transcript


def test_claude_mode_needs_a_key(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.chdir(tmp_path)  # no backend/.env to pick up
    with pytest.raises(SystemExit) as excinfo:
        main(["--ai", "claude"])
    assert excinfo.value.code == 2
