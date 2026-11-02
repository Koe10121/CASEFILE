import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, ref } from "vue";

import { useTypewriter } from "./useTypewriter";

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

function typewriter(text: string, enabled: boolean) {
  const scope = effectScope();
  const tw = scope.run(() => useTypewriter(ref(text), ref(enabled), 10))!;
  return { ...tw, stop: () => scope.stop() };
}

describe("useTypewriter", () => {
  it("reveals the line a little at a time, then all of it", () => {
    const tw = typewriter("Not now.", true);
    expect(tw.shown.value).toBe("");
    expect(tw.typing.value).toBe(true);
    vi.advanceTimersByTime(20);
    expect(tw.shown.value).toBe("No");
    vi.advanceTimersByTime(1000);
    expect(tw.shown.value).toBe("Not now.");
    expect(tw.typing.value).toBe(false);
  });

  it("shows old lines at once", () => {
    expect(typewriter("Already said.", false).shown.value).toBe("Already said.");
  });

  it("can be skipped", async () => {
    const tw = typewriter("A long answer.", true);
    tw.finish();
    await nextTick();
    expect(tw.shown.value).toBe("A long answer.");
    expect(tw.typing.value).toBe(false);
  });

  it("stops its timer with its component", () => {
    const tw = typewriter("Gone.", true);
    tw.stop();
    expect(vi.getTimerCount()).toBe(0);
  });
});
