"""The HTTP API: a thin JSON layer over ``GameSession`` (D43).

    uv run casefile-api                  # http://127.0.0.1:8000, scripted suspects
    uv run casefile-api --ai ollama      # a local model plays them: free

Interactive docs at ``/docs``. Every action answers with what the suspect said, what
happened, and the whole game as the player now sees it, so the browser never has to
work out game state for itself: the backend owns the truth.
"""

import argparse
from typing import get_args

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from casefile.ai.contract import ProviderError
from casefile.ai.factory import make_provider
from casefile.ai.provider import NpcProvider
from casefile.case.validation import load_valid_case
from casefile.cli import DEFAULT_CASE
from casefile.engine.engine import Engine, IllegalActionError, Outcome
from casefile.session import BudgetExhaustedError, GameSession, Reply
from casefile.settings import Ai, Settings

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
from .views import case_view, events_view, game_view, line_view

_ERRORS: dict[int | str, dict[str, object]] = {
    code: {"model": ErrorOut} for code in (404, 409, 429, 502, 503)
}


def create_app(
    engine: Engine,
    provider: NpcProvider,
    *,
    ai: Ai,
    token_budget: int | None,
    max_games: int,
    idle_ttl_s: float,
) -> FastAPI:
    app = FastAPI(title="CASEFILE", version="0.1.0", responses=_ERRORS)
    store = GameStore(
        lambda: GameSession(engine, provider, token_budget),
        max_games=max_games,
        idle_ttl_s=idle_ttl_s,
    )
    case = case_view(engine, ai)

    def action(game_id: str, game: StoredGame, outcome: Reply | Outcome) -> ActionOut:
        line = line_view(game.session, outcome) if isinstance(outcome, Reply) else None
        return ActionOut(
            line=line,
            events=events_view(engine, outcome.events),
            game=game_view(game_id, game.difficulty, game.session),
        )

    # Plain ``def`` handlers: FastAPI runs them in a worker thread, so a slow model
    # reply in one game doesn't block requests for the others.

    @app.get("/api/case")
    def get_case() -> CaseOut:
        return case

    @app.post("/api/games", status_code=201)
    def new_game(body: NewGame) -> GameOut:
        game_id = store.create(body.difficulty)
        with store.use(game_id) as game:
            return game_view(game_id, game.difficulty, game.session)

    @app.get("/api/games/{game_id}")
    def get_game(game_id: str) -> GameOut:
        with store.use(game_id) as game:
            return game_view(game_id, game.difficulty, game.session)

    @app.post("/api/games/{game_id}/talk")
    def talk(game_id: str, body: TalkRequest) -> ActionOut:
        with store.use(game_id) as game:
            return action(game_id, game, game.session.talk_to(body.suspect))

    @app.post("/api/games/{game_id}/ask")
    def ask(game_id: str, body: AskRequest) -> ActionOut:
        with store.use(game_id) as game:
            return action(game_id, game, game.session.ask(body.text))

    @app.post("/api/games/{game_id}/search")
    def search(game_id: str, body: SearchRequest) -> ActionOut:
        with store.use(game_id) as game:
            return action(game_id, game, game.session.search(body.location))

    @app.post("/api/games/{game_id}/show")
    def show(game_id: str, body: ShowRequest) -> ActionOut:
        with store.use(game_id) as game:
            return action(game_id, game, game.session.show(body.evidence))

    @app.post("/api/games/{game_id}/accuse")
    def accuse(game_id: str, body: AccuseRequest) -> ActionOut:
        with store.use(game_id) as game:
            return action(game_id, game, game.session.accuse(body.accusation))

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

    @app.exception_handler(ProviderError)
    def provider_failed(_: Request, exc: ProviderError) -> JSONResponse:
        # The kind is for logs; the player only needs to know nothing changed.
        return error(502, f"the suspect didn't answer ({exc.kind}); nothing changed, try again")

    @app.exception_handler(StoreFullError)
    def full(_: Request, exc: StoreFullError) -> JSONResponse:
        return error(503, str(exc))

    return app


def main(argv: list[str] | None = None) -> None:
    settings = Settings()
    parser = argparse.ArgumentParser(prog="casefile-api", description="Serve the CASEFILE API.")
    parser.add_argument("--ai", choices=get_args(Ai), default=settings.ai)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    if args.ai == "claude" and settings.anthropic_api_key is None:
        parser.error("--ai claude needs ANTHROPIC_API_KEY (see backend/.env.example)")
    provider, budget = make_provider(args.ai, settings)
    app = create_app(
        Engine(load_valid_case(DEFAULT_CASE)),
        provider,
        ai=args.ai,
        token_budget=budget,
        max_games=settings.max_games,
        idle_ttl_s=settings.game_idle_minutes * 60,
    )
    uvicorn.run(app, host=args.host, port=args.port)
