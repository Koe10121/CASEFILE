<script setup lang="ts">
import { computed } from "vue";

import type { Expression } from "../api/types";

const props = defineProps<{
  id: string;
  name: string;
  expression: Expression;
  /** The faces the server has for this person; often none yet (D55). */
  faces: readonly Expression[];
  size?: "sm" | "lg";
}>();

const shown = computed<Expression | null>(() => {
  if (props.faces.includes(props.expression)) return props.expression;
  return props.faces.includes("neutral") ? "neutral" : null;
});
const src = computed(() =>
  shown.value
    ? `/api/portraits/${encodeURIComponent(props.id)}/${encodeURIComponent(shown.value)}`
    : null,
);
const initials = computed(() =>
  props.name
    .split(" ")
    .map((w) => w[0] ?? "")
    .join("")
    .slice(0, 2),
);
const box = computed(() => (props.size === "sm" ? "h-20 w-15" : "h-32 w-24 sm:h-40 sm:w-30"));
</script>

<template>
  <div class="shrink-0 overflow-hidden rounded border border-night-700 bg-night-950" :class="box">
    <img
      v-if="src"
      :key="src"
      :src="src"
      :alt="`${name}, ${shown}`"
      class="h-full w-full object-cover transition-opacity duration-300"
    />
    <div
      v-else
      class="flex h-full w-full items-center justify-center font-serif text-2xl text-night-500"
      aria-hidden="true"
    >
      {{ initials }}
    </div>
  </div>
</template>
