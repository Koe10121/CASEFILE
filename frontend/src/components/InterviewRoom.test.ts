import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import InterviewRoom from "./InterviewRoom.vue";

function room(overrides: Record<string, unknown> = {}) {
  return mount(InterviewRoom, {
    props: {
      name: "Richard Okafor",
      exchanges: [{ detective: "", suspect: "I was in the billiard room.", demeanor: "hostile" }],
      freshIndex: null,
      evidence: [
        {
          id: "E04",
          name: "Study door lock log",
          location: "LOC_STUDY",
          summary: "",
          text: null,
          reads: [],
        },
      ],
      busy: false,
      maxChars: 20,
      over: false,
      ...overrides,
    },
  });
}

describe("InterviewRoom", () => {
  it("asks with Enter, and Shift+Enter starts a new line", async () => {
    const wrapper = room();
    const box = wrapper.get("textarea");
    await box.setValue("  Where were you?  ");
    await box.trigger("keydown", { key: "Enter", shiftKey: true });
    expect(wrapper.emitted("ask")).toBeUndefined();
    await box.trigger("keydown", { key: "Enter" });
    expect(wrapper.emitted("ask")).toEqual([["Where were you?"]]);
    expect((box.element as HTMLTextAreaElement).value).toBe("");
  });

  it("counts down to the server's limit", async () => {
    const wrapper = room();
    await wrapper.get("textarea").setValue("x".repeat(15));
    expect(wrapper.text()).toContain("5");
  });

  it("shows the chosen evidence", async () => {
    const wrapper = room();
    await wrapper.get("select").setValue("E04");
    await wrapper.findAll("form")[1]!.trigger("submit");
    expect(wrapper.emitted("show")).toEqual([["E04"]]);
  });

  it("asks nothing while waiting for an answer or after the accusation", async () => {
    for (const props of [{ busy: true }, { over: true }]) {
      const wrapper = room(props);
      await wrapper.get("textarea").setValue("Anything else?");
      await wrapper.get("form").trigger("submit");
      expect(wrapper.emitted("ask")).toBeUndefined();
    }
  });

  it("prints the whole line for screen readers, even while it types", () => {
    const wrapper = room({ freshIndex: 0 });
    expect(wrapper.get(".sr-only").text()).toBe("I was in the billiard room.");
  });
});
