<script setup lang="ts">
import type { Evidence } from "../api/types";

defineProps<{ evidence: readonly Evidence[] }>();
</script>

<template>
  <section>
    <h2 class="sr-only">Evidence</h2>
    <ul class="space-y-2">
      <li v-for="e in evidence" :key="e.id">
        <details class="group rounded border border-night-700 bg-night-900 open:border-night-500">
          <summary class="cursor-pointer list-none px-3 py-2 text-sm">
            <span class="font-mono text-xs text-brass-400">{{ e.id }}</span>
            {{ e.name }}
          </summary>
          <div class="space-y-2 px-3 pb-3 text-sm leading-relaxed text-paper-300">
            <p>{{ e.summary }}</p>
            <blockquote
              v-if="e.text"
              class="border-l-2 border-paper-300/40 pl-3 font-serif whitespace-pre-line text-paper-100"
            >
              {{ e.text }}
            </blockquote>
            <p v-for="(read, i) in e.reads" :key="i" class="text-paper-100">
              <span class="font-mono text-[11px] text-brass-400 uppercase">On a closer look</span>
              {{ read }}
            </p>
          </div>
        </details>
      </li>
    </ul>
  </section>
</template>
