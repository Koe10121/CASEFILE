import type { ActionBodies, ActionResult, CaseCover, Difficulty, Game, Verb } from "./types";

/** A refused request, with the backend's one-line reason. Nothing changed in the game. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
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

  newGame: (difficulty: Difficulty, detective: string) =>
    request<Game>("/games", { method: "POST", body: JSON.stringify({ difficulty, detective }) }),

  getGame: (id: string) => request<Game>(`/games/${encodeURIComponent(id)}`),

  act: <V extends Verb>(id: string, verb: V, body: ActionBodies[V]) =>
    request<ActionResult>(`/games/${encodeURIComponent(id)}/${verb}`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
};
