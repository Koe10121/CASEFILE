import { describe, expect, it } from "vitest";

import { makeGame } from "../test/fixtures";
import { questionsLeft } from "./budget";

const asked = (n: number) => ({
  S_RICHARD: [
    {
      detective: "",
      suspect: "Opening.",
      demeanor: "calm",
      shown: null,
      expression: "neutral" as const,
    },
    ...Array.from({ length: n }, () => ({
      detective: "Q",
      suspect: "A",
      demeanor: "calm",
      shown: null,
      expression: "neutral" as const,
    })),
  ],
});

describe("questionsLeft", () => {
  it("projects from the average cost of the questions asked so far", () => {
    const game = makeGame({ tokens: { used: 40_000, budget: 2_000_000 }, interviews: asked(10) });
    expect(questionsLeft(game)).toBe(490);
  });

  it("is unknown with no budget or before the first question", () => {
    expect(questionsLeft(makeGame({ tokens: { used: 0, budget: null } }))).toBeNull();
    expect(questionsLeft(makeGame({ tokens: { used: 0, budget: 1000 } }))).toBeNull();
  });

  it("never goes below zero", () => {
    const game = makeGame({ tokens: { used: 1200, budget: 1000 }, interviews: asked(3) });
    expect(questionsLeft(game)).toBe(0);
  });
});
