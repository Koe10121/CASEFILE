import { afterEach, describe, expect, it, vi } from "vitest";

import { jsonResponse, makeGame } from "../test/fixtures";
import { forgetPlayerKey, savePlayerKey } from "../game/playerKey";
import { ApiError, api } from "./client";

afterEach(() => {
  vi.unstubAllGlobals();
  forgetPlayerKey();
});

function stubFetch(response: Response | Error) {
  const fetch = vi.fn(() =>
    response instanceof Error ? Promise.reject(response) : Promise.resolve(response),
  );
  vi.stubGlobal("fetch", fetch);
  return fetch;
}

describe("api", () => {
  it("posts an action as JSON to the game's endpoint", async () => {
    const fetch = stubFetch(jsonResponse(200, { line: null, events: [], game: makeGame() }));
    await api.act("a b", "ask", { text: "Where were you?" });
    expect(fetch).toHaveBeenCalledWith("/api/games/a%20b/ask", {
      method: "POST",
      body: '{"text":"Where were you?"}',
      headers: { "Content-Type": "application/json" },
    });
  });

  it("sends the player's Claude key with questions only", async () => {
    savePlayerKey("  sk-ant-test  ", false);
    const fetch = stubFetch(jsonResponse(200, { line: null, events: [], game: makeGame() }));
    await api.act("g1", "ask", { text: "Where were you?" });
    expect(fetch.mock.lastCall).toMatchObject([
      "/api/games/g1/ask",
      { headers: { "X-Claude-Key": "sk-ant-test" } },
    ]);

    const search = stubFetch(jsonResponse(200, { line: null, events: [], game: makeGame() }));
    await api.act("g1", "search", { location: "LOC_STUDY" });
    expect(search.mock.lastCall).toMatchObject([
      "/api/games/g1/search",
      { headers: { "Content-Type": "application/json" } },
    ]);
    expect(JSON.stringify(search.mock.lastCall)).not.toContain("sk-ant-test");
  });

  it("knows when the key is missing or refused", async () => {
    stubFetch(jsonResponse(401, { detail: "add your key" }));
    const error = (await api.act("g1", "ask", { text: "Hi" }).catch((e: unknown) => e)) as ApiError;
    expect(error.needsKey).toBe(true);
    expect(error.gameLost).toBe(false);
  });

  it("turns the server's detail into the error message", async () => {
    stubFetch(jsonResponse(409, { detail: "talk to a suspect first" }));
    const error = await api.act("g1", "ask", { text: "Hello?" }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, message: "talk to a suspect first" });
    expect((error as ApiError).gameLost).toBe(false);
  });

  it("knows when a game is gone", async () => {
    stubFetch(jsonResponse(404, { detail: "no such game; it may have expired" }));
    const error = (await api.getGame("old").catch((e: unknown) => e)) as ApiError;
    expect(error.gameLost).toBe(true);
  });

  it("explains a validation error and a server that isn't running", async () => {
    stubFetch(jsonResponse(422, { detail: [{ loc: ["body", "suspect"] }] }));
    await expect(api.getCase()).rejects.toThrow("That request wasn't valid.");
    stubFetch(new TypeError("Failed to fetch"));
    await expect(api.getCase()).rejects.toMatchObject({ status: 0 });
  });
});
