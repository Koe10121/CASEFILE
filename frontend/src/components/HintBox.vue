<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue";

import type { Hints } from "../api/types";

const props = defineProps<{ hints: Hints; busy: boolean; over: boolean }>();
const emit = defineEmits<{ hint: [] }>();

// Easy unlocks a hint after a few minutes without progress; tick so the button wakes up.
const now = ref(Date.now() / 1000);
const timer = setInterval(() => (now.value = Date.now() / 1000), 15_000);
onBeforeUnmount(() => clearInterval(timer));
watch(
  () => props.hints.ready_at,
  () => (now.value = Date.now() / 1000),
);

const wait = computed(() =>
  props.hints.ready_at === null ? 0 : Math.ceil((props.hints.ready_at - now.value) / 60),
);
const canAsk = computed(
  () => !props.busy && !props.over && props.hints.left !== 0 && wait.value <= 0,
);
const status = computed(() => {
  if (props.hints.left === 0) return "No hints left";
  if (wait.value > 0) return `Next hint in about ${wait.value} min`;
  if (props.hints.left !== null) return `${props.hints.left} left`;
  return "A hint is ready";
});
</script>

<template>
  <section class="rounded-lg border border-night-700 p-3">
    <div class="flex items-center justify-between gap-2">
      <h2 class="font-mono text-xs tracking-widest text-paper-300 uppercase">Hints</h2>
      <p class="font-mono text-[11px] text-night-500">{{ status }}</p>
    </div>
    <ol v-if="hints.given.length" class="mt-2 space-y-1.5">
      <li v-for="(h, i) in hints.given" :key="i" class="font-serif text-sm text-brass-400 italic">
        {{ h }}
      </li>
    </ol>
    <button
      type="button"
      class="mt-3 w-full rounded border border-brass-400 px-3 py-1.5 text-sm text-brass-400 disabled:opacity-40"
      :disabled="!canAsk"
      @click="emit('hint')"
    >
      I'm stuck: give me a hint
    </button>
  </section>
</template>
