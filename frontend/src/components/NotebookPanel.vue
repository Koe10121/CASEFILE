<script setup lang="ts">
import { computed } from "vue";

import type { Help, NotebookEntry } from "../api/types";
import { arrangeNotebook, formatTime } from "../game/notebook";

const props = defineProps<{
  entries: readonly NotebookEntry[];
  mode: Help["notebook"];
  names: Record<string, string>;
}>();

const groups = computed(() => arrangeNotebook(props.entries, props.mode, Object.keys(props.names)));
</script>

<template>
  <section>
    <h2 class="sr-only">Notebook</h2>
    <p v-if="!entries.length" class="text-sm text-night-500">
      Facts you establish appear here, in the case file's own words.
    </p>
    <div v-for="group in groups" :key="group.key" class="mb-5">
      <h3 v-if="mode !== 'flat'" class="mb-2 font-serif text-paper-300">
        {{ group.key ? (names[group.key] ?? group.key) : "The house" }}
      </h3>
      <ol class="space-y-2">
        <li v-for="e in group.entries" :key="e.fact" class="text-sm leading-relaxed">
          <span v-if="e.time" class="mr-1 font-mono text-xs text-brass-400">{{
            formatTime(e)
          }}</span>
          {{ e.statement }}
          <span class="block text-xs text-night-500">from {{ e.source_name }}</span>
        </li>
      </ol>
    </div>
  </section>
</template>
