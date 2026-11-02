"""Serve the built web game from the API server (D57).

In production one process serves both, so the browser talks to one origin and the API
needs no CORS, as in development (D47). Any path that isn't a file gets ``index.html``,
so a reload of ``/game/<id>`` reaches the Vue router. ``/api/...`` is never answered
with the page: an unknown API path stays a 404.
"""

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope


class WebGame(StaticFiles):
    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            response = await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or path == "api" or path.startswith("api/"):
                raise
            response = await super().get_response("index.html", scope)
        if path.startswith("assets/"):
            # Vite puts a content hash in every asset name, so they never change.
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response
