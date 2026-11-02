// The last game's ID, so the cover can offer "continue". A convenience only: the
// server holds the game, and storage can be unavailable (private windows), so every
// access is allowed to fail.
const KEY = "casefile:last-game";

export function rememberGame(id: string): void {
  try {
    localStorage.setItem(KEY, id);
  } catch {
    // storage blocked: the player can still play, they just can't "continue"
  }
}

export function lastGame(): string | null {
  try {
    return localStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function forgetGame(): void {
  try {
    localStorage.removeItem(KEY);
  } catch {
    // nothing to forget
  }
}
