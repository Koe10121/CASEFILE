import type { Help, NotebookEntry } from "../api/types";

export interface NotebookGroup {
  /** A character ID, or "" for facts about no one in particular. */
  key: string;
  entries: NotebookEntry[];
}

/** "21:52" sorts before "22:05" as text; untimed facts go last, in the order learned. */
function byTime(a: NotebookEntry, b: NotebookEntry): number {
  if (!a.time) return b.time ? 1 : 0;
  if (!b.time) return -1;
  return a.time.start.localeCompare(b.time.start);
}

/**
 * Arrange the notebook the way the difficulty says (D11): grouped by person and sorted
 * by time (easy), grouped by person in the order learned (normal), or one flat list in
 * the order learned (hard). A fact about two people appears under both.
 */
export function arrangeNotebook(
  entries: readonly NotebookEntry[],
  mode: Help["notebook"],
  order: readonly string[],
): NotebookGroup[] {
  if (mode === "flat") return entries.length ? [{ key: "", entries: [...entries] }] : [];

  const groups = new Map<string, NotebookEntry[]>();
  for (const entry of entries) {
    for (const key of entry.subjects.length ? entry.subjects : [""]) {
      groups.set(key, [...(groups.get(key) ?? []), entry]);
    }
  }
  const rank = (key: string) => (key === "" ? order.length : order.indexOf(key));
  return [...groups.entries()]
    .sort(([a], [b]) => rank(a) - rank(b))
    .map(([key, list]) => ({
      key,
      // Array.sort is stable, so untimed facts keep the order they were learned in.
      entries: mode === "by_suspect_and_time" ? [...list].sort(byTime) : list,
    }));
}

export function formatTime(entry: NotebookEntry): string {
  if (!entry.time) return "";
  const { start, end, approx } = entry.time;
  return `${approx ? "~" : ""}${start}${end ? `–${end}` : ""}`;
}
