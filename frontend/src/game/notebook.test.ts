import { describe, expect, it } from "vitest";

import type { NotebookEntry } from "../api/types";
import { arrangeNotebook, formatTime } from "./notebook";

function fact(id: string, subjects: string[], start?: string): NotebookEntry {
  return {
    fact: id,
    statement: id,
    source: "E01",
    source_name: "Body",
    subjects,
    time: start ? { start, end: null, approx: false } : null,
  };
}

const learned = [
  fact("F_LATE", ["S_RICHARD"], "22:30"),
  fact("F_UNTIMED", ["S_RICHARD"]),
  fact("F_EARLY", ["S_RICHARD", "S_VICTORIA"], "21:44"),
  fact("F_HOUSE", []),
];
const order = ["S_VICTORIA", "S_RICHARD"];
const ids = (g: { entries: NotebookEntry[] }) => g.entries.map((e) => e.fact);

describe("arrangeNotebook", () => {
  it("easy: by person in case order, then by time, untimed last", () => {
    const groups = arrangeNotebook(learned, "by_suspect_and_time", order);
    expect(groups.map((g) => g.key)).toEqual(["S_VICTORIA", "S_RICHARD", ""]);
    expect(ids(groups[1]!)).toEqual(["F_EARLY", "F_LATE", "F_UNTIMED"]);
  });

  it("normal: by person, in the order learned", () => {
    const groups = arrangeNotebook(learned, "by_suspect", order);
    expect(ids(groups[1]!)).toEqual(["F_LATE", "F_UNTIMED", "F_EARLY"]);
  });

  it("hard: one list, in the order learned", () => {
    const groups = arrangeNotebook(learned, "flat", order);
    expect(groups).toHaveLength(1);
    expect(ids(groups[0]!)).toEqual(["F_LATE", "F_UNTIMED", "F_EARLY", "F_HOUSE"]);
    expect(arrangeNotebook([], "flat", order)).toEqual([]);
  });
});

describe("formatTime", () => {
  it("marks approximate times and spans", () => {
    const entry = fact("F", []);
    expect(formatTime(entry)).toBe("");
    expect(formatTime({ ...entry, time: { start: "21:52", end: "22:15", approx: true } })).toBe(
      "~21:52–22:15",
    );
  });
});
