import type { Game } from "../api/types";

/**
 * Roughly how many more questions this game's token budget allows, judged from what
 * questions have cost so far. ``null`` when there is no budget (scripted suspects) or
 * nothing to judge from yet. The budget is a safety cap, not money: on a local model
 * it costs only GPU time (D49).
 */
export function questionsLeft(game: Game): number | null {
  const { used, budget } = game.tokens;
  if (budget === null || used === 0) return null;
  const asked = Object.values(game.interviews)
    .flat()
    .filter((x) => x.detective !== "").length;
  if (asked === 0) return null;
  return Math.max(0, Math.floor((budget - used) / (used / asked)));
}
