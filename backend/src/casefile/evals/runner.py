"""Play eval scenarios against a provider and score every suspect line.

    uv run casefile-eval --ai ollama --model gemma3:12b
    uv run casefile-eval --ai claude --repeat 1

Prints a summary and writes a JSON report plus a readable transcript to
``backend/eval-results/`` (git-ignored).
"""

import argparse
import json
import statistics
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import get_args

from casefile.ai.contract import ProviderError
from casefile.ai.factory import make_provider
from casefile.ai.prompt import stable_instructions, turn_state
from casefile.case.validation import load_valid_case
from casefile.engine.briefing import build_briefing
from casefile.engine.engine import Engine, RejectReason
from casefile.evals.checks import forbidden, invented_times, lie_breaks, parroted
from casefile.evals.scenarios import Ask, EvalSuite, Scenario, Search, Show, Talk, load_suite
from casefile.session import GameSession
from casefile.settings import Ai, Settings

BACKEND = Path(__file__).resolve().parents[3]
CASES = BACKEND.parent / "cases"
DEFAULT_SUITE = BACKEND / "evals" / "blackwood_manor.json"
DEFAULT_OUT = BACKEND / "eval-results"


@dataclass(frozen=True)
class TurnResult:
    scenario: str
    run: int
    suspect: str
    question: str
    dialogue: str = ""
    error: str | None = None
    """The ProviderError ("kind: detail"), when the provider gave no usable reply."""
    accepted: tuple[str, ...] = ()
    invented_ids: tuple[str, ...] = ()
    guarded_attempts: tuple[str, ...] = ()
    not_allowed: tuple[str, ...] = ()
    leaks: tuple[str, ...] = ()
    invented_times: tuple[str, ...] = ()
    lie_breaks: tuple[str, ...] = ()
    prompt_breaks: tuple[str, ...] = ()
    parroted: tuple[str, ...] = ()
    expected: tuple[str, ...] = ()
    unsupported: tuple[str, ...] = ()
    """Declared but not said: dropped by grounding. Not a flag, the backend handled it."""
    inferred: tuple[str, ...] = ()
    """Said but not declared: counted by grounding."""
    latency_ms: int = 0
    tokens: int = 0

    @property
    def clue_hit(self) -> bool | None:
        return bool(set(self.expected) & set(self.accepted)) if self.expected else None

    @property
    def flags(self) -> list[str]:
        named = {
            "error": (self.error,) if self.error else (),
            "invented ID": self.invented_ids,
            "guarded ID": self.guarded_attempts,
            "gated ID": self.not_allowed,
            "leak": self.leaks,
            "invented time": self.invented_times,
            "broke lie": self.lie_breaks,
            "broke frame": self.prompt_breaks,
            "parroted": self.parroted,
        }
        found = [name for name, hits in named.items() if hits]
        if self.clue_hit is False:
            found.append("missed clue")
        return found


@dataclass
class Summary:
    provider: str
    turns: int
    clean_turns: int
    provider_errors: int
    invented_ids: int
    guarded_attempts: int
    not_allowed: int
    leaks: int
    invented_times: int
    lie_breaks: int
    prompt_breaks: int
    parroted: int
    unsupported: int
    inferred: int
    clue_hits: int
    clue_questions: int
    median_latency_ms: int
    p90_latency_ms: int
    tokens_per_turn: int

    @property
    def clue_rate(self) -> float:
        return self.clue_hits / self.clue_questions if self.clue_questions else 1.0


def run_scenario(
    engine: Engine, settings: Settings, ai: Ai, sc: Scenario, run: int
) -> list[TurnResult]:
    provider, budget = make_provider(ai, settings)
    session = GameSession(engine, provider, token_budget=budget)
    results: list[TurnResult] = []
    for step in sc.steps:
        match step:
            case Talk(suspect=suspect):
                session.talk_to(suspect)
            case Search(location=location):
                session.search(location)
            case Show(evidence=evidence):
                session.show(evidence)
            case Ask():
                results.append(_ask(session, sc.id, run, step))
    return results


def _ask(session: GameSession, scenario: str, run: int, step: Ask) -> TurnResult:
    suspect = session.current_suspect
    assert suspect is not None, f"{scenario}: ask before talk"
    briefing = build_briefing(session.engine, session.state, suspect)
    seen = f"{stable_instructions(briefing)}\n{turn_state(briefing)}\n{step.text}"
    base = TurnResult(scenario, run, suspect, step.text, expected=step.expect_reveal)
    try:
        reply = session.ask(step.text)
    except ProviderError as exc:
        return replace(base, error=str(exc))

    def rejected(reason: RejectReason) -> tuple[str, ...]:
        return tuple(r.proposed for r in reply.rejected if r.reason == reason)

    return replace(
        base,
        dialogue=reply.dialogue,
        accepted=tuple(reply.accepted),
        invented_ids=rejected(RejectReason.UNKNOWN),
        guarded_attempts=rejected(RejectReason.GUARDED),
        not_allowed=rejected(RejectReason.NOT_ALLOWED),
        leaks=reply.leaks,
        unsupported=reply.unsupported,
        inferred=tuple(reply.inferred),
        invented_times=invented_times(reply.dialogue, seen),
        lie_breaks=lie_breaks(reply.dialogue, step.must_not_say),
        prompt_breaks=forbidden(reply.dialogue, step.must_not_contain),
        parroted=parroted(reply.dialogue, briefing.sample_lines),
        latency_ms=reply.usage.latency_ms,
        tokens=reply.usage.total_tokens,
    )


def summarise(provider: str, results: list[TurnResult]) -> Summary:
    answered = [r for r in results if r.error is None]
    latencies = sorted(r.latency_ms for r in answered) or [0]

    def count(attr: str) -> int:
        return sum(1 for r in results if getattr(r, attr))

    clue = [r.clue_hit for r in results if r.clue_hit is not None]
    return Summary(
        provider=provider,
        turns=len(results),
        clean_turns=sum(1 for r in results if not r.flags),
        provider_errors=count("error"),
        invented_ids=count("invented_ids"),
        guarded_attempts=count("guarded_attempts"),
        not_allowed=count("not_allowed"),
        leaks=count("leaks"),
        invented_times=count("invented_times"),
        lie_breaks=count("lie_breaks"),
        prompt_breaks=count("prompt_breaks"),
        parroted=count("parroted"),
        unsupported=sum(len(r.unsupported) for r in results),
        inferred=sum(len(r.inferred) for r in results),
        clue_hits=sum(clue),
        clue_questions=len(clue),
        median_latency_ms=int(statistics.median(latencies)),
        p90_latency_ms=latencies[int(0.9 * (len(latencies) - 1))],
        tokens_per_turn=sum(r.tokens for r in answered) // max(len(answered), 1),
    )


class SetupError(Exception):
    """Every question in the first interview failed: the provider isn't usable."""


def run_suite(suite: EvalSuite, ai: Ai, settings: Settings, repeat: int) -> list[TurnResult]:
    """Run every scenario ``repeat`` times. Stops at once with ``SetupError`` if the first
    interview gets no replies at all (model not downloaded, Ollama not running, bad key)
    rather than failing every question for minutes."""
    engine = Engine(load_valid_case(CASES / suite.case))
    results: list[TurnResult] = []
    for sc in suite.scenarios:
        for run in range(1, repeat + 1):
            turns = run_scenario(engine, settings, ai, sc, run)
            if not results and turns and all(t.error for t in turns):
                raise SetupError(str(turns[0].error))
            results += turns
    return results


# ------------------------------------------------------------------ report

SUMMARY_ROWS = (
    ("Clean turns (no flags)", lambda s: f"{s.clean_turns}/{s.turns}"),
    ("Clue facts learned", lambda s: f"{s.clue_hits}/{s.clue_questions} ({s.clue_rate:.0%})"),
    ("Facts said but not declared (counted)", lambda s: s.inferred),
    ("Facts declared but not said (dropped)", lambda s: s.unsupported),
    ("Broke a lie", lambda s: s.lie_breaks),
    ("Invented a time", lambda s: s.invented_times),
    ("Broke frame (injection)", lambda s: s.prompt_breaks),
    ("Culprit leak", lambda s: s.leaks),
    ("Invented fact ID", lambda s: s.invented_ids),
    ("Tried a guarded ID", lambda s: s.guarded_attempts),
    ("Revealed a gated fact", lambda s: s.not_allowed),
    ("Parroted a sample line", lambda s: s.parroted),
    ("Provider errors", lambda s: s.provider_errors),
    (
        "Median / p90 latency",
        lambda s: f"{s.median_latency_ms / 1000:.1f}s / {s.p90_latency_ms / 1000:.1f}s",
    ),
    ("Tokens per turn", lambda s: s.tokens_per_turn),
)


def summary_table(s: Summary) -> str:
    lines = [f"| {s.provider} | |", "| --- | --- |"]
    lines += [f"| {label} | {value(s)} |" for label, value in SUMMARY_ROWS]
    return "\n".join(lines)


def transcript(results: list[TurnResult]) -> str:
    out: list[str] = []
    for r in results:
        out.append(f"### {r.scenario} (run {r.run}): {r.suspect}")
        out.append(f"> **Detective:** {r.question}")
        out.append(f"> **Suspect:** {r.dialogue or '(no reply: ' + str(r.error) + ')'}")
        learned = ", ".join(f + (" (matched)" if f in r.inferred else "") for f in r.accepted)
        out.append(f"Learned: {learned or 'nothing'}")
        if r.unsupported:
            out.append(f"Declared but not said: {', '.join(r.unsupported)}")
        if r.flags:
            details = [*r.lie_breaks, *r.invented_times, *r.prompt_breaks, *r.invented_ids]
            out.append(
                f"**Flags:** {', '.join(r.flags)}" + (f" ({'; '.join(details)})" if details else "")
            )
        out.append("")
    return "\n".join(out)


def write_report(out_dir: Path, s: Summary, results: list[TurnResult]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    stem = f"{stamp}-{s.provider.replace(':', '-').replace('/', '-')}"
    (out_dir / f"{stem}.json").write_text(
        json.dumps({"summary": asdict(s), "turns": [asdict(r) for r in results]}, indent=2),
        encoding="utf-8",
    )
    md = out_dir / f"{stem}.md"
    md.write_text(
        f"# Eval: {s.provider}\n\n{summary_table(s)}\n\n## Transcript\n\n{transcript(results)}",
        encoding="utf-8",
    )
    return md


def main(argv: list[str] | None = None) -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(
        prog="casefile-eval", description="Score how a model plays the suspects."
    )
    parser.add_argument("--ai", choices=get_args(Ai), default=settings.ai)
    parser.add_argument("--model", help="override the Ollama or Claude model for this run")
    parser.add_argument("--repeat", type=int, default=3, help="runs per scenario (default 3)")
    parser.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)
    if args.model:
        key = "claude_model" if args.ai == "claude" else "ollama_model"
        settings = settings.model_copy(update={key: args.model})
    if args.ai == "claude" and settings.anthropic_api_key is None:
        parser.error("--ai claude needs ANTHROPIC_API_KEY (see backend/.env.example)")
    name = {"mock": "mock", "ollama": settings.ollama_model, "claude": settings.claude_model}[
        args.ai
    ]

    suite = load_suite(args.suite)
    print(
        f"Running {len(suite.scenarios)} scenarios x {args.repeat} with {name}. "
        "This can take a few minutes."
    )
    try:
        results = run_suite(suite, args.ai, settings, args.repeat)
    except SetupError as exc:
        hint = f" Is it downloaded? Try: ollama pull {name}" if args.ai == "ollama" else ""
        parser.exit(1, f"No replies from {name}: {exc}.{hint}\n")
    summary = summarise(name, results)
    report = write_report(args.out, summary, results)
    print(summary_table(summary))
    print(f"\nFull transcript: {report}")
