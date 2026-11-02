# The public game in one image (D57): the API server also serves the built web game.
#
#   docker build -t casefile .
#   docker run -p 8000:8000 casefile                 # scripted suspects, no key needed
#
# Hosts such as Render set PORT; the server listens on it.

# --- the web game -------------------------------------------------------------------
FROM node:22-slim AS web
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx vite build

# --- the server ---------------------------------------------------------------------
FROM python:3.13-slim
RUN pip install --no-cache-dir uv==0.11.32
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never PYTHONUNBUFFERED=1
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
RUN uv sync --locked --no-dev --no-install-project
COPY backend/src ./src
RUN uv sync --locked --no-dev
COPY cases /app/cases
COPY --from=web /app/frontend/dist /app/web

RUN useradd --create-home casefile && mkdir -p /app/data && chown casefile /app/data
USER casefile

ENV PATH="/app/backend/.venv/bin:$PATH" \
    CASEFILE_AI=mock \
    CASEFILE_WEB_DIR=/app/web \
    CASEFILE_SAVE_FILE=/app/data/games.sqlite3 \
    CASEFILE_BEHIND_PROXY=true \
    PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "exec casefile-api --host 0.0.0.0 --port \"$PORT\""]
