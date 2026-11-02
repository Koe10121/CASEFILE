"""Hints from the solution chain (D54).

A hint is the authored ``hint`` of the first step of the solution chain the player
hasn't finished: a step is finished once its facts are all in the notebook and the lie
it breaks is caught. The hints are written as nudges ("Doors here keep better time than
people."), so the answer key itself never leaves the server.

How many hints a player gets, and when, is the difficulty's ``hints`` policy:
``none``, ``on_request:N`` (N per game, any time) or ``auto_after_minutes:M`` (as many
as needed, each one unlocking after M minutes without progress).
"""

from dataclasses import dataclass
from typing import Literal

from casefile.case.solution import Solution
from casefile.case.world import HintPolicy
from casefile.engine.state import GameState

ALL_DONE = "You have what you need. Make your accusation."


@dataclass(frozen=True, slots=True)
class HintRule:
    kind: Literal["none", "on_request", "auto_after_minutes"]
    amount: int = 0
    """How many hints (``on_request``), or how many minutes (``auto_after_minutes``)."""


def parse_policy(policy: HintPolicy) -> HintRule:
    if policy == "none":
        return HintRule("none")
    kind, _, amount = policy.partition(":")
    if kind == "on_request":
        return HintRule("on_request", int(amount))
    if kind == "auto_after_minutes":
        return HintRule("auto_after_minutes", int(amount))
    raise ValueError(f"unknown hint policy {policy!r}")  # the case schema rules this out


def next_hint(solution: Solution, state: GameState) -> str:
    for step in solution.solution_chain:
        learned = all(fact in state.known_facts for fact in step.learn)
        broken = step.breaks is None or step.breaks in state.caught_lies
        if not (learned and broken):
            return step.hint
    return ALL_DONE
