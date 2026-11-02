import { mount } from "@vue/test-utils";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Hints } from "../api/types";
import HintBox from "./HintBox.vue";

function box(hints: Hints) {
  return mount(HintBox, { props: { hints, busy: false, over: false } });
}

afterEach(() => {
  vi.useRealTimers();
});

describe("HintBox", () => {
  it("asks for a hint and lists the ones given", async () => {
    const wrapper = box({ given: ["Doors keep better time."], left: 2, ready_at: null });
    expect(wrapper.text()).toContain("Doors keep better time.");
    expect(wrapper.text()).toContain("2 left");
    await wrapper.get("button").trigger("click");
    expect(wrapper.emitted("hint")).toHaveLength(1);
  });

  it("waits on Easy until the next hint unlocks", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(1_000_000_000));
    const wrapper = box({ given: [], left: null, ready_at: 1_000_000 + 150 });
    expect(wrapper.text()).toContain("Next hint in about 3 min");
    expect(wrapper.get("button").attributes("disabled")).toBeDefined();
  });

  it("says when none are left", () => {
    const wrapper = box({ given: [], left: 0, ready_at: null });
    expect(wrapper.text()).toContain("No hints left");
    expect(wrapper.get("button").attributes("disabled")).toBeDefined();
  });
});
