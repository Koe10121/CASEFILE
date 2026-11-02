<script setup lang="ts">
import { computed } from "vue";

import type { Help, NotebookEntry, Statement } from "../api/types";
import { formatTime } from "../game/notebook";

const props = defineProps<{
  statements: readonly Statement[];
  notebook: readonly NotebookEntry[];
  mode: Help["contradictions"];
  names: Record<string, string>;
}>();

const bySuspect = computed(() => {
  const groups = new Map<string, Statement[]>();
  for (const s of props.statements) groups.set(s.suspect, [...(groups.get(s.suspect) ?? []), s]);
  return [...groups.entries()];
});

/** Side by side (normal): what you know about this person, next to what they claimed. */
function factsAbout(suspect: string): NotebookEntry[] {
  return props.notebook.filter((e) => e.subjects.includes(suspect));
}
</script>

<template>
  <section>
    <h2 class="sr-only">Statements</h2>
    <p v-if="!statements.length" class="text-sm text-night-500">
      What suspects claim goes on record here. Show them evidence that disproves a claim to catch
      the lie.
    </p>
    <div v-for="[suspect, claims] in bySuspect" :key="suspect" class="mb-6">
      <h3 class="mb-2 font-serif text-paper-300">{{ names[suspect] ?? suspect }}</h3>
      <ul class="space-y-2">
        <li
          v-for="s in claims"
          :key="s.lie"
          class="rounded border px-3 py-2 text-sm"
          :class="
            s.caught
              ? 'border-alarm-500/40 text-paper-300'
              : s.flagged
                ? 'border-brass-400 text-paper-100'
                : 'border-night-700 text-paper-100'
          "
        >
          <span :class="s.caught ? 'line-through decoration-alarm-500' : ''">“{{ s.claim }}”</span>
          <span v-if="s.caught" class="mt-1 block font-mono text-[11px] text-alarm-400 uppercase">
            Disproved
          </span>
          <span
            v-else-if="s.flagged"
            class="mt-1 block font-mono text-[11px] text-brass-400 uppercase"
          >
            Something you hold contradicts this
          </span>
        </li>
      </ul>
      <details v-if="mode === 'side_by_side' && factsAbout(suspect).length" class="mt-2 text-sm">
        <summary class="cursor-pointer text-xs text-paper-300">
          What you know about {{ names[suspect] ?? suspect }} ({{ factsAbout(suspect).length }})
        </summary>
        <ul class="mt-2 space-y-1 border-l border-night-700 pl-3 text-paper-300">
          <li v-for="e in factsAbout(suspect)" :key="e.fact">
            <span v-if="e.time" class="mr-1 font-mono text-xs text-brass-400">{{
              formatTime(e)
            }}</span>
            {{ e.statement }}
          </li>
        </ul>
      </details>
    </div>
  </section>
</template>
