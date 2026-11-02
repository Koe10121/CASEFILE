// The Ollama on the player's own computer, for games played by it (D60). The game
// server can't reach it, so the browser makes the call: the server hands over the exact
// request, and the reply goes back to the server to be checked like any other.
import type { components } from "../api/schema";

export type OllamaReply = components["schemas"]["OllamaReply"];

const KEY = "casefile:ollama-url";
export const DEFAULT_OLLAMA_URL = "http://localhost:11434";

/** What a player has to do once, so Ollama accepts calls from this site. */
export function originsCommand(): string {
  return `setx OLLAMA_ORIGINS ${window.location.origin}`;
}

export class OllamaError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "OllamaError";
  }
}

export function ollamaUrl(): string {
  try {
    return localStorage.getItem(KEY) ?? DEFAULT_OLLAMA_URL;
  } catch {
    return DEFAULT_OLLAMA_URL;
  }
}

export function saveOllamaUrl(url: string): void {
  try {
    localStorage.setItem(KEY, url.trim().replace(/\/+$/, "") || DEFAULT_OLLAMA_URL);
  } catch {
    // the default is used next time
  }
}

function unreachable(): OllamaError {
  return new OllamaError(
    "Can't reach Ollama on this computer. Check that the Ollama app is running, and that you " +
      `ran "${originsCommand()}" and then restarted Ollama.`,
  );
}

/** Check that Ollama answers and has the model. ``null`` when all is well. */
export async function checkOllama(model: string): Promise<string | null> {
  let response: Response;
  try {
    response = await fetch(`${ollamaUrl()}/api/tags`);
  } catch {
    return unreachable().message;
  }
  if (!response.ok) return `Ollama answered ${response.status}.`;
  const tags = (await response.json()) as { models?: { name: string }[] };
  const names = new Set((tags.models ?? []).map((m) => m.name));
  if (!names.has(model) && !names.has(`${model}:latest`)) {
    return `Ollama is running, but doesn't have ${model} yet. Run: ollama pull ${model}`;
  }
  return null;
}

/** Send the server's request to the player's Ollama and return its reply. */
export async function askOllama(request: Record<string, unknown>): Promise<OllamaReply> {
  let response: Response;
  try {
    response = await fetch(`${ollamaUrl()}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    });
  } catch {
    throw unreachable();
  }
  if (!response.ok) {
    const detail = (await response.text()).slice(0, 200);
    throw new OllamaError(`Ollama answered ${response.status}: ${detail}`);
  }
  return (await response.json()) as OllamaReply;
}
