import { playerKey } from "../game/playerKey";
import type {
  ActionBodies,
  ActionResult,
  CaseCover,
  Difficulty,
  Game,
  PlayedBy,
  Verb,
} from "./types";

/** A refused request, with the backend's one-line reason. Nothing changed in the game. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }

  /** The server plays the suspects on the player's own Claude key, and it is missing
   * or was refused (D58). */
  get needsKey(): boolean {
    return this.status === 401;
  }

  /** The game is gone: never existed, or the server forgot it (restart or idle expiry). */
  get gameLost(): boolean {
    return this.status === 404;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...init?.headers },
    });
  } catch {
    throw new ApiError(0, "Can't reach the game server. Is it running?");
  }
  if (!response.ok) throw new ApiError(response.status, await reason(response));
  return (await response.json()) as T;
}

/** The backend's errors are `{"detail": "..."}`; a 422 has a list of field errors. */
async function reason(response: Response): Promise<string> {
  try {
    const body = (await response.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail)) return "That request wasn't valid.";
  } catch {
    // not JSON: fall through
  }
  return `The server answered ${response.status}.`;
}

export const api = {
  getCase: () => request<CaseCover>("/case"),

  newGame: (difficulty: Difficulty, detective: string, playedBy: PlayedBy = "server") =>
    request<Game>("/games", {
      method: "POST",
      body: JSON.stringify({ difficulty, detective, played_by: playedBy }),
    }),

  getGame: (id: string) => request<Game>(`/games/${encodeURIComponent(id)}`),

  act: <V extends Verb>(id: string, verb: V, body: ActionBodies[V]) => {
    // Only a question calls the model, so only a question carries the key (D58).
    const key = verb === "ask" ? playerKey() : null;
    return request<ActionResult>(`/games/${encodeURIComponent(id)}/${verb}`, {
      method: "POST",
      body: JSON.stringify(body),
      headers: key ? { "X-Claude-Key": key } : {},
    });
  },
};
