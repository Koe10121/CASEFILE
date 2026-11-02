<script setup lang="ts">
import { computed, ref } from "vue";

import type { Accusation, CaseCover, Evidence } from "../api/types";

const props = defineProps<{
  options: CaseCover["accusation"];
  victim: string;
  names: Record<string, string>;
  evidence: readonly Evidence[];
  busy: boolean;
}>();

const emit = defineEmits<{ accuse: [accusation: Accusation]; cancel: [] }>();

const culprit = ref("");
const motive = ref("");
const method = ref("");
const cited = ref<string[]>([]);
const sure = ref(false);

// On Easy the server marks which held items matter, and only those are offered (D54).
const choices = computed(() => props.evidence.filter((e) => e.relevant !== false));
const narrowed = computed(() => choices.value.length < props.evidence.length);
const full = computed(() => cited.value.length >= props.options.max_evidence);
const ready = computed(
  () => !!culprit.value && !!motive.value && !!method.value && sure.value && !props.busy,
);

function submit(): void {
  if (!ready.value) return;
  emit("accuse", {
    culprit: culprit.value,
    motive: motive.value,
    method: method.value,
    evidence: [...cited.value],
  });
}
</script>

<template>
  <form class="space-y-6" @submit.prevent="submit">
    <header>
      <p class="font-mono text-xs tracking-widest text-alarm-400 uppercase">Final accusation</p>
      <h2 class="font-serif text-2xl">Who killed {{ victim }}, why, and how?</h2>
      <p class="mt-1 text-sm text-paper-300">
        You get one accusation. The case closes when you make it.
      </p>
    </header>

    <fieldset>
      <legend class="mb-2 font-mono text-xs tracking-widest text-paper-300 uppercase">
        Culprit
      </legend>
      <div class="grid gap-2 sm:grid-cols-2">
        <label
          v-for="id in options.culprits"
          :key="id"
          class="flex cursor-pointer items-center gap-2 rounded border border-night-700 px-3 py-2 has-[:checked]:border-alarm-500"
        >
          <input
            v-model="culprit"
            type="radio"
            name="culprit"
            :value="id"
            class="accent-alarm-500"
          />
          <span class="font-serif">{{ names[id] ?? id }}</span>
        </label>
      </div>
    </fieldset>

    <fieldset>
      <legend class="mb-2 font-mono text-xs tracking-widest text-paper-300 uppercase">
        Motive
      </legend>
      <div class="space-y-2">
        <label
          v-for="m in options.motives"
          :key="m.id"
          class="flex cursor-pointer items-start gap-2 rounded border border-night-700 px-3 py-2 text-sm has-[:checked]:border-alarm-500"
        >
          <input
            v-model="motive"
            type="radio"
            name="motive"
            :value="m.id"
            class="mt-1 accent-alarm-500"
          />
          <span>{{ m.label }}</span>
        </label>
      </div>
    </fieldset>

    <fieldset>
      <legend class="mb-2 font-mono text-xs tracking-widest text-paper-300 uppercase">
        Method
      </legend>
      <div class="space-y-2">
        <label
          v-for="m in options.methods"
          :key="m.id"
          class="flex cursor-pointer items-start gap-2 rounded border border-night-700 px-3 py-2 text-sm has-[:checked]:border-alarm-500"
        >
          <input
            v-model="method"
            type="radio"
            name="method"
            :value="m.id"
            class="mt-1 accent-alarm-500"
          />
          <span>{{ m.label }}</span>
        </label>
      </div>
    </fieldset>

    <fieldset>
      <legend class="mb-2 font-mono text-xs tracking-widest text-paper-300 uppercase">
        Evidence ({{ cited.length }}/{{ options.max_evidence }})
      </legend>
      <p class="mb-2 text-sm text-paper-300">
        Cite up to {{ options.max_evidence }} items that prove your case.
        <template v-if="narrowed">On Easy, only the items that matter are listed.</template>
      </p>
      <div class="space-y-1">
        <label
          v-for="e in choices"
          :key="e.id"
          class="flex items-center gap-2 rounded px-2 py-1 text-sm"
          :class="full && !cited.includes(e.id) ? 'opacity-40' : 'cursor-pointer'"
        >
          <input
            v-model="cited"
            type="checkbox"
            :value="e.id"
            :disabled="full && !cited.includes(e.id)"
            class="accent-alarm-500"
          />
          <span class="font-mono text-xs text-brass-400">{{ e.id }}</span>
          {{ e.name }}
        </label>
      </div>
    </fieldset>

    <label class="flex items-center gap-2 text-sm">
      <input v-model="sure" type="checkbox" class="accent-alarm-500" />
      I'm sure. Close the case.
    </label>

    <div class="flex gap-3">
      <button
        type="submit"
        :disabled="!ready"
        class="rounded bg-alarm-500 px-5 py-2 font-medium text-paper-100 hover:bg-alarm-400 disabled:opacity-40"
      >
        Accuse
      </button>
      <button
        type="button"
        class="rounded border border-night-700 px-5 py-2 text-paper-300 hover:border-night-500"
        @click="emit('cancel')"
      >
        Keep investigating
      </button>
    </div>
  </form>
</template>
