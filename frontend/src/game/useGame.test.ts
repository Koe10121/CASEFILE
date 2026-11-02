import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, api } from "../api/client";
import { cover, makeGame, talkResult } from "../test/fixtures";
import { useGame } from "./useGame";

afterEach(() => vi.restoreAllMocks());

describe("useGame", () => {
  it("takes the server's game after every action, and remembers what happened", async () => {
    vi.spyOn(api, "getCase").mockResolvedValue(cover);
    vi.spyOn(api, "getGame").mockResolvedValue(makeGame());
    vi.spyOn(api, "act").mockResolvedValue(talkResult());

    const g = useGame("g1");
    await g.load();
    await g.act("talk", { suspect: "S_RICHARD" });

    expect(g.game.value).toEqual(talkResult().game);
    expect(g.suspect.value?.name).toBe("Richard Okafor");
    expect(g.feed.value.map((e) => e.type)).toEqual(["location_searched", "lie_on_record"]);
    expect(g.fresh.value).toEqual({ suspect: "S_RICHARD", index: 0 });
  });

  it("sends one move at a time", async () => {
    let answer: (r: ReturnType<typeof talkResult>) => void = () => undefined;
    const act = vi
      .spyOn(api, "act")
      .mockImplementation(() => new Promise((resolve) => (answer = resolve)));
    const g = useGame("g1");
    const first = g.act("talk", { suspect: "S_RICHARD" });
    await g.act("ask", { text: "And then?" }); // ignored while the first is out
    expect(g.busy.value).toBe(true);
    answer(talkResult());
    await first;
    expect(act).toHaveBeenCalledTimes(1);
    expect(g.busy.value).toBe(false);
  });

  it("reports a refusal without changing the game, and notices a lost game", async () => {
    vi.spyOn(api, "act").mockRejectedValueOnce(new ApiError(409, "talk to a suspect first"));
    const g = useGame("g1");
    await g.act("ask", { text: "Hello?" });
    expect(g.error.value).toBe("talk to a suspect first");
    expect(g.game.value).toBeNull();
    expect(g.lost.value).toBe(false);

    vi.spyOn(api, "getCase").mockResolvedValue(cover);
    vi.spyOn(api, "getGame").mockRejectedValueOnce(new ApiError(404, "no such game"));
    await g.load();
    expect(g.lost.value).toBe(true);
  });
});
