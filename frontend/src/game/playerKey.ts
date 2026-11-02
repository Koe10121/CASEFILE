// The player's own Claude API key, on a server that plays the suspects with it (D58).
// It stays in this browser: sessionStorage by default (gone when the tab closes), or
// localStorage if the player ticks "remember". The server uses it for one call at a
// time and never stores it. Storage can be unavailable (private windows), so every
// access is allowed to fail; the key then lasts until the page reloads.
const KEY = "casefile:claude-key";
let inMemory: string | null = null;

function stores(): Storage[] {
  const found: Storage[] = [];
  for (const get of [() => sessionStorage, () => localStorage]) {
    try {
      found.push(get());
    } catch {
      // blocked
    }
  }
  return found;
}

export function playerKey(): string | null {
  for (const store of stores()) {
    try {
      const key = store.getItem(KEY);
      if (key) return key;
    } catch {
      // blocked
    }
  }
  return inMemory;
}

export function savePlayerKey(key: string, remember: boolean): void {
  forgetPlayerKey();
  inMemory = key.trim();
  try {
    (remember ? localStorage : sessionStorage).setItem(KEY, inMemory);
  } catch {
    // kept in memory only
  }
}

export function forgetPlayerKey(): void {
  inMemory = null;
  for (const store of stores()) {
    try {
      store.removeItem(KEY);
    } catch {
      // nothing to forget
    }
  }
}
