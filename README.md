# CASEFILE

An AI-powered detective game. Players interrogate LLM-driven suspects, uncover evidence and solve a mystery. A deterministic game engine controls the truth of the mystery, not the model.

Status: Milestones 1 (case design), 2 (backend engine) and 4 (AI suspects) are done. Milestone 3 (the web game) is in progress. See [docs/design/README.md](docs/design/README.md) for the milestone plan.

## Play it in the browser

You need [uv](https://docs.astral.sh/uv/) and [Node.js](https://nodejs.org) 22 or later. Run two terminals from the repository root:

```bash
cd backend && uv run casefile-api            # the game server; suspects run on Ollama (free), or add --ai mock
cd frontend && npm install && npm run dev    # then open http://localhost:5173
```

| Folder | What it is |
| --- | --- |
| [`backend/`](backend/README.md) | Python: the case data models, the engine, the AI suspects, the eval harness and the HTTP API. Also a terminal version of the game: `uv run casefile` |
| [`frontend/`](frontend/README.md) | Vue 3 + TypeScript: the web game |
| [`cases/`](cases) | Case data (CASE #001, Blackwood Manor: spoilers) |
| [`docs/`](docs/design/README.md) | Design docs and the decision log |
