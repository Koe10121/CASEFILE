<script setup lang="ts">
import { computed } from "vue";

import type { GameEvent } from "../api/types";

const props = defineProps<{ events: readonly GameEvent[] }>();
const items = computed(() => props.events.slice(0, 12).map(describe));

function describe(e: GameEvent): { mark: string; text: string; tone: string } {
  switch (e.type) {
    case "fact_learned":
      return { mark: "+", text: e.statement, tone: "text-paper-100" };
    case "evidence_found":
      return { mark: "◆", text: `Found ${e.evidence}: ${e.name}`, tone: "text-brass-400" };
    case "location_searched":
      return { mark: "·", text: `Searched ${e.name}`, tone: "text-paper-300" };
    case "lie_on_record":
      return { mark: "~", text: `On record: “${e.claim}”`, tone: "text-paper-300" };
    case "lie_caught":
      return { mark: "!", text: `Caught with ${e.evidence}: “${e.claim}”`, tone: "text-alarm-400" };
    case "accusation_scored":
      return { mark: "■", text: `Accusation scored: ${e.total}/100`, tone: "text-brass-400" };
  }
}
</script>

<template>
  <section>
    <h2 class="sr-only">What just happened</h2>
    <p v-if="!events.length" class="text-sm text-night-500">
      What your questions, searches and evidence turn up appears here.
    </p>
    <ol v-else class="space-y-2" aria-live="polite">
      <li v-for="(item, i) in items" :key="i" class="flex gap-2 text-sm" :class="item.tone">
        <span aria-hidden="true" class="w-3 shrink-0 font-mono">{{ item.mark }}</span>
        <span>{{ item.text }}</span>
      </li>
    </ol>
  </section>
</template>
