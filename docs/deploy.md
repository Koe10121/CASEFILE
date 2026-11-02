# Deploy the public game

The whole game is one Docker image (D57): the API server also serves the built web game. Anything that runs Docker can host it. We use Render's free tier.

## On Render

The first time:

1. Sign in at [render.com](https://render.com) with GitHub. The free tier needs no card.
2. Click **New**, then **Blueprint**, and pick the `CASEFILE` repository. Render reads `render.yaml`.
3. Click **Apply**. The first build takes a few minutes. When it is done, the game is at the address Render shows, such as `https://casefile.onrender.com`.

After that, every push to `main` deploys again on its own.

What the free tier means for players:

| Limit | What it means |
| --- | --- |
| Sleep | After 15 minutes with no visitors the server sleeps. The next visitor waits about a minute while it wakes. |
| Saved games | The disk is wiped on every deploy and restart, so saved games last until then. |
| Suspects | Each player picks: the free scripted suspects (the default, no key), or Claude on their own API key (D58, D59). |

## Who pays for the suspects

With `CASEFILE_PLAYER_KEYS=true` (the Render default), each player pastes their own Anthropic API key on the cover. The browser keeps it (for the tab, or on the device if they tick "remember") and sends it with each question only. The server uses it for that one reply and never saves or logs it. Every game still has a token cap (`CASEFILE_SESSION_TOKEN_BUDGET`, 400,000), so one game can't run up a large bill. Players should also set a spend limit on their key at console.anthropic.com.

A player without a key can always pick the free scripted suspects on the cover (D59), so the site works for everyone. Ollama can't run on Render: the free server has no GPU. To play with Ollama, run the game on your own PC (see the backend and frontend READMEs).

To turn Claude off entirely, set `CASEFILE_PLAYER_KEYS=false` and `CASEFILE_AI=mock` in the service's **Environment** tab. The suspects are then scripted.

The settings are in `render.yaml` and in the service's **Environment** tab on Render. Every setting is listed in [`backend/.env.example`](../backend/.env.example).

## Try the image on your own machine

With Docker Desktop installed, run these from the repository folder:

```
docker build -t casefile .
docker run -p 8000:8000 casefile
```

The image plays the scripted suspects unless you pass `-e CASEFILE_PLAYER_KEYS=true`.

Then open http://localhost:8000.

## Without Docker

Build the web game, then serve it from the API server:

```
cd frontend
npm run build
cd ../backend
uv run casefile-api --ai mock --web ../frontend/dist
```
