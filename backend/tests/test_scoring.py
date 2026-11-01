"""Deterministic scoring (D10, D29): 40 culprit, 20 motive, 20 method, 5 per key group.

Nothing but the culprit scores without the right culprit.
"""

import pytest

from casefile.case import CaseBundle
from casefile.engine.scoring import Accusation, score


def accuse(culprit: str, motive: str, method: str, *evidence: str) -> Accusation:
    return Accusation.model_validate(
        {"culprit": culprit, "motive": motive, "method": method, "evidence": list(evidence)}
    )


@pytest.mark.parametrize(
    ("accusation", "expected"),
    [
        pytest.param(
            accuse("S_VICTORIA", "MOT_HIDE_THEFT", "MTH_AWARD_STAGED", "E05", "E10", "E02", "E03"),
            (40, 20, 20, 20),
            id="everything right",
        ),
        pytest.param(
            accuse("S_RICHARD", "MOT_HIDE_THEFT", "MTH_AWARD_STAGED"),
            (0, 0, 0, 0),
            id="right motive and method count for nothing with the wrong culprit",
        ),
        pytest.param(
            accuse("S_VICTORIA", "MOT_KEEP_JOB", "MTH_AWARD_AFTER_UNLOCK"),
            (40, 0, 0, 0),
            id="right culprit only",
        ),
        pytest.param(
            accuse("S_VICTORIA", "MOT_HIDE_THEFT", "MTH_AWARD_STAGED", "E10", "E04", "E03", "E11"),
            (40, 20, 20, 10),
            id="two items from the same group earn one group",
        ),
        pytest.param(
            accuse("S_RICHARD", "MOT_KESTREL", "MTH_PUSHED", "E05", "E10", "E02", "E03"),
            (0, 0, 0, 0),
            id="the right evidence scores nothing with the wrong culprit",
        ),
    ],
)
def test_score(
    blackwood: CaseBundle, accusation: Accusation, expected: tuple[int, int, int, int]
) -> None:
    result = score(accusation, blackwood.solution)
    assert (result.culprit, result.motive, result.method, result.evidence) == expected
    assert result.total == sum(expected)
