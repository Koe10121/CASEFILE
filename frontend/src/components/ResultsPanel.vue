<script setup lang="ts">
import type { Result } from "../api/types";

defineProps<{ result: Result }>();

const parts = [
  { key: "culprit", label: "Culprit" },
  { key: "motive", label: "Motive" },
  { key: "method", label: "Method" },
  { key: "evidence", label: "Evidence" },
] as const;
</script>

<template>
  <section class="mx-auto max-w-2xl space-y-8 py-6">
    <header class="text-center">
      <p class="font-mono text-xs tracking-widest text-paper-300 uppercase">Case closed</p>
      <p
        class="mt-2 font-serif text-6xl"
        :class="result.culprit ? 'text-paper-100' : 'text-alarm-400'"
      >
        {{ result.total }}<span class="text-2xl text-paper-300">/100</span>
      </p>
      <p class="mt-2 text-paper-300">
        {{
          result.culprit
            ? "You named the killer."
            : "You accused the wrong person. The case is unsolved."
        }}
      </p>
    </header>

    <table class="w-full text-sm">
      <caption class="sr-only">
        Score breakdown
      </caption>
      <tbody>
        <tr v-for="p in parts" :key="p.key" class="border-b border-night-700">
          <th scope="row" class="py-2 text-left font-normal text-paper-300">{{ p.label }}</th>
          <td class="py-2 text-right font-mono">
            {{ result[p.key] }} / {{ result.out_of[p.key] }}
          </td>
        </tr>
      </tbody>
    </table>
    <p v-if="result.groups_covered.length" class="text-sm text-paper-300">
      Your evidence covered: {{ result.groups_covered.join(", ") }}.
    </p>

    <article class="rounded-lg border border-night-700 bg-night-900 p-6">
      <h2 class="font-mono text-xs tracking-widest text-brass-400 uppercase">
        What really happened
      </h2>
      <p class="mt-3 font-serif text-lg leading-relaxed whitespace-pre-line">
        {{ result.epilogue }}
      </p>
    </article>
  </section>
</template>
