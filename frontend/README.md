# CASEFILE frontend

The web game: Vue 3, TypeScript, Vite and Tailwind CSS. It renders what the game server sends and keeps no game rules of its own (D43, D47).

## Run it

Start the game server first (see [`backend/README.md`](../backend/README.md)), then:

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173; Vite forwards /api to the server on :8000
```

On Windows PowerShell, use two windows:

```powershell
cd C:\Users\User\CASEFILE\backend
uv run casefile-api
```

```powershell
cd C:\Users\User\CASEFILE\frontend
npm install
npm run dev
```

## Checks

```bash
npm run lint           # ESLint (Vue + type-aware TypeScript rules)
npm run format:check   # Prettier
npm run typecheck      # vue-tsc, strict
npm test               # Vitest
npm run build          # type check + production build into dist/
```

CI runs all of these on every pull request that touches `frontend/` or `backend/` (`.github/workflows/frontend.yml`).

## Browser test

`e2e/case.spec.ts` plays CASE #001 from the cover to a 100/100 accusation in Chromium. It covers asking, searching, a reload that resumes the game, catching Victoria's three lies, a hint and the accusation, and it fails on any console error. Playwright starts its own game server with the mock AI and a dev server, on ports 8765 and 5199, so a game you have open on 8000 and 5173 is left alone and no model is needed. Games from the test stay in memory and never reach `backend/games.sqlite3`.

The first time, download the browser:

```bash
cd frontend
npx playwright install chromium
```

Then run it whenever you like:

```bash
npm run e2e
```

CI runs it as its own job, and on a failure it uploads a report with a trace and a screenshot (`playwright-report`).

## API types

`src/api/schema.d.ts` is generated from the backend's OpenAPI schema, so the TypeScript types always match what the server sends. After changing anything in `backend/src/casefile/api/`:

```bash
cd backend && uv run casefile-api --openapi ../frontend/openapi.json
cd ../frontend && npm run gen:api
```

CI regenerates both files and fails if they differ from what is committed, so the frontend can't silently drift from the API.

## Layout

| Path                                 | What it is                                                                                |
| ------------------------------------ | ----------------------------------------------------------------------------------------- |
| `src/api/schema.d.ts`                | Generated API types (do not edit)                                                         |
| `src/api/types.ts`                   | Short names for the generated types                                                       |
| `src/api/client.ts`                  | `api`: one typed function per endpoint; `ApiError` carries the server's reason            |
| `src/game/useGame.ts`                | One game's state: replaced with the server's copy after every action; one move at a time  |
| `src/game/lastGame.ts`               | Remembers the last game ID so the cover can offer "continue"                              |
| `src/composables/useTypewriter.ts`   | Types out a suspect's finished line (D45); respects reduced motion; click to skip         |
| `src/views/CoverView.vue`            | The case cover: intro, detective, people, difficulty, start                               |
| `src/views/GameView.vue`             | The investigation: suspects and places, the interview, events and evidence                |
| `src/components/SuspectPortrait.vue` | A suspect's face for the current expression, falling back to neutral, then initials (D55) |
| `src/components/HintBox.vue`         | Hints given so far and the "I'm stuck" button, with the Easy countdown (D54)              |
| `src/components/InterviewRoom.vue`   | The transcript, the question box (Enter to ask) and "show evidence"                       |
| `src/components/CaseSidebar.vue`     | Suspects to interview and places to search                                                |
| `src/components/EventFeed.vue`       | What the last actions caused: facts learned, lies on record and caught                    |
| `src/components/EvidenceList.vue`    | Evidence held, with document text and closer reads                                        |
| `src/**/*.test.ts`                   | Unit and component tests                                                                  |
