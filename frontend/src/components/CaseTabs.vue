<script setup lang="ts">
import { ref } from "vue";

import type { Evidence, GameEvent, Help, NotebookEntry, Statement } from "../api/types";
import EventFeed from "./EventFeed.vue";
import EvidenceList from "./EvidenceList.vue";
import NotebookPanel from "./NotebookPanel.vue";
import StatementsPanel from "./StatementsPanel.vue";

const props = defineProps<{
  feed: readonly GameEvent[];
  notebook: readonly NotebookEntry[];
  statements: readonly Statement[];
  evidence: readonly Evidence[];
  help: Help;
  names: Record<string, string>;
}>();

type Tab = "feed" | "notebook" | "statements" | "evidence";
const tab = ref<Tab>("feed");

const tabs: { id: Tab; label: string; count: () => number | null }[] = [
  { id: "feed", label: "Latest", count: () => null },
  { id: "notebook", label: "Notebook", count: () => props.notebook.length },
  { id: "statements", label: "Statements", count: () => props.statements.length },
  { id: "evidence", label: "Evidence", count: () => props.evidence.length },
];

function onKey(event: KeyboardEvent, index: number): void {
  const step = event.key === "ArrowRight" ? 1 : event.key === "ArrowLeft" ? -1 : 0;
  if (!step) return;
  const next = tabs[(index + step + tabs.length) % tabs.length]!;
  tab.value = next.id;
  document.getElementById(`tab-${next.id}`)?.focus();
}
</script>

<template>
  <div>
    <div role="tablist" aria-label="Case file" class="flex gap-1 border-b border-night-700">
      <button
        v-for="(t, i) in tabs"
        :id="`tab-${t.id}`"
        :key="t.id"
        type="button"
        role="tab"
        :aria-selected="tab === t.id"
        :aria-controls="`panel-${t.id}`"
        :tabindex="tab === t.id ? 0 : -1"
        class="-mb-px border-b-2 px-2 py-2 text-xs tracking-wider uppercase transition-colors"
        :class="
          tab === t.id
            ? 'border-brass-400 text-paper-100'
            : 'border-transparent text-paper-300 hover:text-paper-100'
        "
        @click="tab = t.id"
        @keydown="onKey($event, i)"
      >
        {{ t.label }}
        <span v-if="t.count() !== null" class="font-mono text-night-500">{{ t.count() }}</span>
      </button>
    </div>
    <div :id="`panel-${tab}`" role="tabpanel" :aria-labelledby="`tab-${tab}`" class="pt-4">
      <EventFeed v-if="tab === 'feed'" :events="feed" />
      <NotebookPanel
        v-else-if="tab === 'notebook'"
        :entries="notebook"
        :mode="help.notebook"
        :names="names"
      />
      <StatementsPanel
        v-else-if="tab === 'statements'"
        :statements="statements"
        :notebook="notebook"
        :mode="help.contradictions"
        :names="names"
      />
      <EvidenceList v-else :evidence="evidence" />
    </div>
  </div>
</template>
