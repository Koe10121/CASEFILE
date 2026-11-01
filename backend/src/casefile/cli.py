"""A terminal front end for playing a case.

    uv run casefile                      # CASE #001 with scripted suspects: no setup
    uv run casefile --ai ollama          # a local model plays them: free, needs Ollama
    uv run casefile --ai claude          # Claude plays them: needs ANTHROPIC_API_KEY
    uv run casefile path/to/case-folder

Type ``help`` for commands. This is a developer tool for exercising the engine end to
end, not the real UI.
"""

import argparse
import sys
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import TextIO, get_args

from pydantic import ValidationError

from casefile.ai.contract import ProviderError
from casefile.ai.factory import make_provider
from casefile.case.ids import CharacterId, EvidenceId, LocationId
from casefile.case.validation import load_valid_case
from casefile.engine.engine import Engine, IllegalActionError
from casefile.engine.events import (
    AccusationScored,
    Event,
    EvidenceFound,
    FactLearned,
    LieCaught,
    LieOnRecord,
    LocationSearched,
)
from casefile.engine.scoring import Accusation
from casefile.session import GameSession
from casefile.settings import Ai, Settings

DEFAULT_CASE = Path(__file__).resolve().parents[3] / "cases" / "blackwood_manor"

HELP = """\
  people                       who you can interview
  places                       where you can search
  talk S_RICHARD               start or resume an interview
  ask <question>               ask the suspect you are talking to
  search LOC_OFFICE            search a location
  evidence                     what you have found
  show E07                     show evidence to the suspect you are talking to
  notebook                     everything you have learned
  accuse S_X MOT_X MTH_X E01 E02 ...   final accusation
  quit"""


class Cli:
    def __init__(self, session: GameSession, out: TextIO) -> None:
        self.s = session
        self.out = out
        self.ix = session.engine.index
        self.commands: dict[str, Callable[[str], None]] = {
            "help": lambda _: self.say(HELP),
            "people": self.people,
            "places": self.places,
            "talk": self.talk,
            "ask": self.ask,
            "search": self.search,
            "evidence": self.evidence,
            "show": self.show,
            "notebook": self.notebook,
            "accuse": self.accuse,
        }

    def say(self, text: str) -> None:
        print(text, file=self.out)

    def run(self, lines: Iterable[str]) -> None:
        case = self.ix.bundle.case
        self.say(f"{case.title}\n{case.setting.intro}\nType 'help' for commands.")
        for line in lines:
            command, _, rest = line.strip().partition(" ")
            if command == "quit":
                return
            if not command:
                continue
            handler = self.commands.get(command)
            if handler is None:
                self.say(f"Unknown command '{command}'. Type 'help'.")
                continue
            try:
                handler(rest.strip())
            except (IllegalActionError, ValidationError) as exc:
                self.say(f"  ! {_first_line(exc)}")
            except ProviderError as exc:
                self.say(f"  ! the suspect didn't answer ({exc.kind}). Try again.")
            if self.s.state.is_over:
                return

    # ------------------------------------------------------------ commands

    def people(self, _: str) -> None:
        for sid in self.ix.briefings:
            self.say(f"  {sid:<12} {self.ix.characters[sid].name}")

    def places(self, _: str) -> None:
        for loc in self.ix.locations.values():
            mark = "searched" if loc.id in self.s.state.searched_locations else ""
            self.say(f"  {loc.id:<18} {loc.name:<28} {mark}")

    def talk(self, arg: str) -> None:
        reply = self.s.talk_to(CharacterId(arg))
        self.say(f"You sit down with {self.ix.characters[CharacterId(arg)].name}.")
        if reply.dialogue:
            self.say(f'  [{reply.demeanor}] "{reply.dialogue}"')
        self.report(reply.events)

    def ask(self, arg: str) -> None:
        reply = self.s.ask(arg)
        self.say(f'  [{reply.demeanor}] "{reply.dialogue}"')
        self.report(reply.events)

    def search(self, arg: str) -> None:
        self.report(self.s.search(LocationId(arg)).events)

    def evidence(self, _: str) -> None:
        for eid in sorted(self.s.state.found_evidence):
            ev = self.ix.evidence[eid]
            self.say(f"  {eid}  {ev.name}: {ev.summary}")

    def show(self, arg: str) -> None:
        outcome = self.s.show(EvidenceId(arg))
        if not any(isinstance(e, LieCaught) for e in outcome.events):
            self.say("  They look at it, and say nothing new.")
        self.report(outcome.events)

    def notebook(self, _: str) -> None:
        for entry in self.s.state.notebook:
            self.say(f"  ({entry.source}) {self.ix.facts[entry.fact].statement}")

    def accuse(self, arg: str) -> None:
        culprit, motive, method, *evidence = arg.split()
        accusation = Accusation.model_validate(
            {"culprit": culprit, "motive": motive, "method": method, "evidence": evidence}
        )
        self.report(self.s.accuse(accusation).events)

    # ------------------------------------------------------------ output

    def report(self, events: Iterable[Event]) -> None:
        for e in events:
            match e:
                case FactLearned(fact=fact):
                    self.say(f"  + notebook: {self.ix.facts[fact].statement}")
                case EvidenceFound(evidence=eid):
                    self.say(f"  + found {eid}: {self.ix.evidence[eid].name}")
                case LocationSearched(location=loc):
                    self.say(f"  You search: {self.ix.locations[loc].name}.")
                case LieOnRecord(lie=lie):
                    self.say(f'  ~ on record: "{self.ix.lies[lie].lie.claim}"')
                case LieCaught(lie=lie):
                    self.say(f'  ! caught: "{self.ix.lies[lie].lie.claim}"')
                case AccusationScored(score=sc):
                    self.say(
                        f"  Score {sc.total}/100: culprit {sc.culprit}, motive {sc.motive}, "
                        f"method {sc.method}, evidence {sc.evidence}"
                    )
                    self.say(f"\n{self.ix.bundle.solution.epilogue}")


def _first_line(exc: Exception) -> str:
    return str(exc).splitlines()[0]


def main(argv: list[str] | None = None) -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(prog="casefile", description="Play a CASEFILE case.")
    parser.add_argument("case", nargs="?", type=Path, default=DEFAULT_CASE)
    parser.add_argument(
        "--ai",
        choices=get_args(Ai),
        default=settings.ai,
        help="who plays the suspects (default: %(default)s)",
    )
    args = parser.parse_args(argv)
    if args.ai == "claude" and settings.anthropic_api_key is None:
        parser.error("--ai claude needs ANTHROPIC_API_KEY (see backend/.env.example)")
    engine = Engine(load_valid_case(args.case))
    session = GameSession(engine, *make_provider(args.ai, settings))
    Cli(session, sys.stdout).run(_prompted_lines())


def _prompted_lines() -> Iterable[str]:
    while True:
        try:
            yield input("> ")
        except EOFError:
            return
