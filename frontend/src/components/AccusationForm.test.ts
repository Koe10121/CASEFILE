import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";

import type { Evidence } from "../api/types";
import AccusationForm from "./AccusationForm.vue";

const item = (id: string): Evidence => ({
  id,
  name: id,
  location: "LOC_STUDY",
  summary: "",
  text: null,
  reads: [],
});

function form() {
  return mount(AccusationForm, {
    props: {
      options: {
        culprits: ["S_RICHARD", "S_VICTORIA"],
        motives: [{ id: "MOT_A", label: "Money" }],
        methods: [{ id: "MTH_A", label: "The award" }],
        max_evidence: 2,
      },
      victim: "Arthur Blackwood",
      names: { S_RICHARD: "Richard Okafor", S_VICTORIA: "Victoria Shaw" },
      evidence: [item("E01"), item("E02"), item("E03")],
      busy: false,
    },
  });
}

describe("AccusationForm", () => {
  it("accuses only once every part is chosen and the player confirms", async () => {
    const wrapper = form();
    await wrapper.get('input[value="S_VICTORIA"]').setValue(true);
    await wrapper.get('input[value="MOT_A"]').setValue(true);
    await wrapper.get('input[value="MTH_A"]').setValue(true);
    await wrapper.get('input[value="E02"]').setValue(true);
    await wrapper.get("form").trigger("submit");
    expect(wrapper.emitted("accuse")).toBeUndefined(); // not confirmed yet

    const sure = wrapper.findAll("input[type=checkbox]").at(-1)!;
    await sure.setValue(true);
    await wrapper.get("form").trigger("submit");
    expect(wrapper.emitted("accuse")).toEqual([
      [{ culprit: "S_VICTORIA", motive: "MOT_A", method: "MTH_A", evidence: ["E02"] }],
    ]);
  });

  it("stops at the evidence limit", async () => {
    const wrapper = form();
    await wrapper.get('input[value="E01"]').setValue(true);
    await wrapper.get('input[value="E02"]').setValue(true);
    expect(wrapper.get('input[value="E03"]').attributes("disabled")).toBeDefined();
    expect(wrapper.text()).toContain("Evidence (2/2)");
  });
});
