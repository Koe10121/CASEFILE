"""The HTTP API: a thin JSON layer over ``GameSession`` (D43).

    uv run casefile-api                  # http://127.0.0.1:8000, a local model (Ollama): free
    uv run casefile-api --ai mock        # scripted suspects: no setup at all
    uv run casefile-api --openapi ../frontend/openapi.json   # write the API schema
    uv run casefile-api --web ../frontend/dist   # also serve the built web game (D57)

Interactive docs at ``/docs``. Every action answers with what the suspect said, what
happened, and the whole game as the player now sees it, so the browser never has to
work out game state for itself: the backend owns the truth.
"""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, cast, get_args

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from casefile.ai.contract import ProviderError
from casefile.ai.factory import make_provider, setup_problem
from casefile.ai.mock import MockNpc
from casefile.ai.player_key import MAX_KEY_CHARS, MissingKeyError, PlayerKeyClaude, player_key
from casefile.ai.provider import NpcProvider
from casefile.ai.relay import RelayedOllama, RelayNeededError, relayed
from casefile.case.ids import CharacterId
from casefile.case.validation import load_valid_case
from casefile.cli import DEFAULT_CASE
from casefile.engine.engine import Engine, IllegalActionError, Outcome
from casefile.expressions import Expression
from casefile.session import BudgetExhaustedError, GameSession, PlayedBy, Reply, SavedGame
from casefile.settings import Ai, Settings

from .limits import RateLimitedError, RateLimiter
from .portraits import Portraits, find_portraits
from .saves import SaveFile
from .schemas import (
    AccuseRequest,
    ActionOut,
    AskRequest,
    CaseOut,
    ErrorOut,
    GameOut,
    NewGame,
    SearchRequest,
    ShowRequest,
    TalkRequest,
)
from .store import GameBusyError, GameNotFoundError, GameStore, StoredGame, StoreFullError
from .views import case_view, difficulty_help, events_view, game_view, line_view
from .web import WebGame

_ERRORS: dict[int | str, dict[str, object]] = {
    code: {"model": ErrorOut} for code in (401, 404, 409, 429, 502, 503)
}


@dataclass(frozen=True, slots=True)
class Limits:
    """Rate limits per visitor (D57): new games, and moves in any game."""

    new_games: RateLimiter
    actions: RateLimiter


def create_app(
    engine: Engine,
    provider: NpcProvider,
    *,
    ai: Ai,
    token_budget: int | None,
    max_games: int,
    idle_ttl_s: float,
    saves: SaveFile | None = None,
    portraits: Portraits | None = None,
    limits: Limits | None = None,
    web: Path | None = None,
    player_keys: bool = False,
    ollama_model: str = "llama3.1:8b",
    max_output_tokens: int = 2048,
) -> FastAPI:
    app = FastAPI(title="CASEFILE", version="0.1.0", responses=_ERRORS)
    # Who plays the suspects, per game (D59, D60). Scripted suspects and the player's
    # own Ollama cost the server nothing, so they have no token cap.
    players: dict[PlayedBy, tuple[NpcProvider, int | None]] = {
        "server": (provider, token_budget),
        "scripted": (MockNpc(), None),
        "your_ollama": (RelayedOllama(ollama_model, max_output_tokens), None),
    }

    def new_session(detective: str | None, played_by: PlayedBy) -> GameSession:
        npc, budget = players[played_by]
        return GameSession(engine, npc, budget, detective, played_by=played_by)

    def resume_session(saved: SavedGame) -> GameSession:
        npc, budget = players[saved.played_by]
        return GameSession.resume(engine, npc, budget, saved)

    store = GameStore(
        new_session,
        resume_session,
        saves=saves,
        max_games=max_games,
        idle_ttl_s=idle_ttl_s,
    )
    faces = portraits or {}
    case = case_view(engine, ai, faces, player_keys=player_keys, ollama_model=ollama_model)

    def action(
        game_id: str, game: StoredGame, outcome: Reply | Outcome, *, caught: bool = False
    ) -> ActionOut:
        line = (
            line_view(game.session, outcome, caught=caught) if isinstance(outcome, Reply) else None
        )
        return ActionOut(
            line=line,
            events=events_view(engine, outcome.events),
            game=game_view(game_id, game.difficulty, game.session),
        )

    def visitor(request: Request) -> str:
        # Behind a proxy, uvicorn's proxy headers make this the visitor, not the proxy.
        return request.client.host if request.client else "unknown"

    def new_game_limit(request: Request) -> None:
        if limits is not None:
            limits.new_games.hit(visitor(request))

    def action_limit(request: Request) -> None:
        if limits is not None:
            limits.actions.hit(visitor(request))

    limit_new_games = [Depends(new_game_limit)]
    limit_actions = [Depends(action_limit)]

    # Plain ``def`` handlers: FastAPI runs them in a worker thread, so a slow model
    # reply in one game doesn't block requests for the others.

    @app.get(
        "/api/portraits/{character}/{expression}",
        response_class=FileResponse,
        responses={404: {"model": ErrorOut}},
    )
    def portrait(character: str, expression: str) -> FileResponse:
        """A portrait image (D55). Only files the startup scan found are served."""
        path = faces.get(CharacterId(character), {}).get(cast(Expression, expression))
        if path is None:
            raise HTTPException(404, "no such portrait")
        return FileResponse(path, headers={"Cache-Control": "public, max-age=3600"})

    @app.get("/api/case")
    def get_case() -> CaseOut:
        return case

    @app.post("/api/games", status_code=201, dependencies=limit_new_games)
    def new_game(body: NewGame) -> GameOut:
        game_id = store.create(body.difficulty, body.detective, played_by=body.played_by)
        with store.use(game_id) as game:
            return game_view(game_id, game.difficulty, game.session)

    @app.get("/api/games/{game_id}")
    def get_game(game_id: str) -> GameOut:
        with store.use(game_id) as game:
            return game_view(game_id, game.difficulty, game.session)

    @app.post("/api/games/{game_id}/talk", dependencies=limit_actions)
    def talk(game_id: str, body: TalkRequest) -> ActionOut:
        with store.use(game_id) as game:
            return action(game_id, game, game.session.talk_to(body.suspect))

    @app.post("/api/games/{game_id}/ask", dependencies=limit_actions)
    def ask(
        game_id: str,
        body: AskRequest,
        x_claude_key: Annotated[str | None, Header(max_length=MAX_KEY_CHARS)] = None,
    ) -> ActionOut:
        """``X-Claude-Key`` is the player's Anthropic API key, needed only when the cover
        says ``player_keys`` (D58). It is used for this one call and never stored."""
        with store.use(game_id) as game:
            own_ollama = body.ollama if game.session.played_by == "your_ollama" else None
            with player_key(x_claude_key if player_keys else None), relayed(own_ollama):
                try:
                    reply = game.session.ask(body.text)
                except RelayNeededError as relay:
                    view = game_view(game_id, game.difficulty, game.session)
                    return ActionOut(line=None, events=(), game=view, relay=relay.request)
            return action(game_id, game, reply)

    @app.post("/api/games/{game_id}/search", dependencies=limit_actions)
    def search(game_id: str, body: SearchRequest) -> ActionOut:
        with store.use(game_id) as game:
            return action(game_id, game, game.session.search(body.location))

    @app.post("/api/games/{game_id}/show", dependencies=limit_actions)
    def show(game_id: str, body: ShowRequest) -> ActionOut:
        with store.use(game_id) as game:
            return action(game_id, game, game.session.show(body.evidence), caught=True)

    @app.post("/api/games/{game_id}/accuse", dependencies=limit_actions)
    def accuse(game_id: str, body: AccuseRequest) -> ActionOut:
        with store.use(game_id) as game:
            return action(game_id, game, game.session.accuse(body.accusation))

    @app.post("/api/games/{game_id}/hint", dependencies=limit_actions)
    def hint(game_id: str) -> ActionOut:
        """The next nudge, if the difficulty allows one now (D54). It arrives in
        ``game.hints.given``; nothing else in the game changes."""
        with store.use(game_id) as game:
            game.session.hint(difficulty_help(engine, game.difficulty).hints)
            return ActionOut(
                line=None, events=(), game=game_view(game_id, game.difficulty, game.session)
            )

    # Errors keep one shape, ``{"detail": "..."}``, like FastAPI's own. The order of
    # these doesn't matter: Starlette picks the most specific class.

    def error(status: int, detail: str) -> JSONResponse:
        return JSONResponse(status_code=status, content={"detail": detail})

    @app.exception_handler(GameNotFoundError)
    def not_found(_: Request, __: GameNotFoundError) -> JSONResponse:
        return error(404, "no such game; it may have expired")

    @app.exception_handler(IllegalActionError)
    def illegal(_: Request, exc: IllegalActionError) -> JSONResponse:
        return error(409, str(exc))

    @app.exception_handler(GameBusyError)
    def busy(_: Request, __: GameBusyError) -> JSONResponse:
        return error(409, "still working on your last move")

    @app.exception_handler(BudgetExhaustedError)
    def budget(_: Request, exc: BudgetExhaustedError) -> JSONResponse:
        return error(429, str(exc))

    @app.exception_handler(MissingKeyError)
    def missing_key(_: Request, __: MissingKeyError) -> JSONResponse:
        return error(401, "this server plays the suspects on your own Claude API key; add it")

    @app.exception_handler(ProviderError)
    def provider_failed(_: Request, exc: ProviderError) -> JSONResponse:
        if exc.kind == "auth":
            return error(401, "Anthropic refused your Claude API key; check it and try again")
        # The kind is for logs; the player only needs to know nothing changed.
        return error(502, f"the suspect didn't answer ({exc.kind}); nothing changed, try again")

    @app.exception_handler(StoreFullError)
    def full(_: Request, exc: StoreFullError) -> JSONResponse:
        return error(503, str(exc))

    @app.exception_handler(RateLimitedError)
    def limited(_: Request, exc: RateLimitedError) -> JSONResponse:
        response = error(429, str(exc))
        response.headers["Retry-After"] = str(exc.retry_after_s)
        return response

    if web is not None:
        # Last, so every /api route above wins over the catch-all page.
        app.mount("/", WebGame(directory=web), name="web")
    return app


def main(argv: list[str] | None = None) -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(prog="casefile-api", description="Serve the CASEFILE API.")
    parser.add_argument("--ai", choices=get_args(Ai), default=settings.ai)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--openapi", type=Path, metavar="FILE", help="write the OpenAPI schema to FILE and exit"
    )
    parser.add_argument(
        "--web",
        type=Path,
        default=settings.web_dir,
        metavar="DIR",
        help="also serve the built web game from DIR (frontend/dist)",
    )
    args = parser.parse_args(argv)
    if args.openapi is not None:
        args.ai = "mock"  # the schema is the same whoever plays the suspects
    if args.web is not None and not (args.web / "index.html").is_file():
        parser.error(f"--web {args.web}: no index.html there; run `npm run build` in frontend/")
    provider: NpcProvider
    budget: int | None
    if settings.player_keys and args.openapi is None:
        args.ai = "claude"
        provider, budget = PlayerKeyClaude(settings), settings.session_token_budget
    else:
        problem = setup_problem(args.ai, settings)
        if problem is not None:
            parser.error(problem)
        provider, budget = make_provider(args.ai, settings)
    engine = Engine(load_valid_case(DEFAULT_CASE))
    saves = None
    if args.openapi is None and settings.save_file is not None:
        saves = SaveFile(
            settings.save_file, engine.index.bundle.case.case_id, keep_days=settings.keep_saves_days
        )
    app = create_app(
        engine,
        provider,
        ai=args.ai,
        token_budget=budget,
        max_games=settings.max_games,
        idle_ttl_s=settings.game_idle_minutes * 60,
        saves=saves,
        portraits=find_portraits(
            DEFAULT_CASE / "portraits", (c.id for c in engine.index.bundle.case.characters)
        ),
        limits=Limits(
            new_games=RateLimiter(settings.new_games_per_hour, 3600),
            actions=RateLimiter(settings.moves_per_minute, 60),
        ),
        web=args.web,
        player_keys=settings.player_keys and args.openapi is None,
        ollama_model=settings.ollama_model,
        max_output_tokens=settings.max_output_tokens,
    )
    if args.openapi is not None:
        # Written as UTF-8 by Python, not piped: PowerShell 5 redirects as UTF-16.
        args.openapi.write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
        return
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        # Trust X-Forwarded-For only when a proxy in front sets it; otherwise anyone
        # could pick their own address and dodge the rate limits.
        proxy_headers=settings.behind_proxy,
        forwarded_allow_ips="*" if settings.behind_proxy else None,
    )
