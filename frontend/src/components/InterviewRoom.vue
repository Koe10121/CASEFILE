<script setup lang="ts">
import { computed, nextTick, ref, watch } from "vue";

import type { Evidence, Exchange, Expression } from "../api/types";
import SuspectPortrait from "./SuspectPortrait.vue";
import TypedLine from "./TypedLine.vue";

const props = defineProps<{
  id: string;
  name: string;
  faces: readonly Expression[];
  exchanges: readonly Exchange[];
  freshIndex: number | null;
  evidence: readonly Evidence[];
  busy: boolean;
  maxChars: number;
  over: boolean;
  shrugged: boolean;
}>();

const emit = defineEmits<{ ask: [text: string]; show: [evidence: string] }>();

const question = ref("");
const chosen = ref("");
const log = ref<HTMLElement | null>(null);
// The portrait follows the suspect's latest line.
const expression = computed<Expression>(() => props.exchanges.at(-1)?.expression ?? "neutral");
const remaining = computed(() => props.maxChars - question.value.length);
const canAsk = computed(
  () => !props.busy && !props.over && question.value.trim().length > 0 && remaining.value >= 0,
);

function ask(): void {
  if (!canAsk.value) return;
  emit("ask", question.value.trim());
  question.value = "";
}

function show(): void {
  if (!chosen.value || props.busy || props.over) return;
  emit("show", chosen.value);
}

function onKey(event: KeyboardEvent): void {
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    ask();
  }
}

// Keep the newest line in view.
watch(
  () => props.exchanges.length,
  async () => {
    await nextTick();
    log.value?.scrollTo({ top: log.value.scrollHeight, behavior: "smooth" });
  },
);
</script>

<template>
  <section class="flex min-h-0 flex-col rounded-lg border border-night-700 bg-night-900">
    <header class="flex items-end gap-4 border-b border-night-700 px-5 py-3">
      <SuspectPortrait :id="id" :name="name" :expression="expression" :faces="faces" />
      <div>
        <p class="font-mono text-xs tracking-widest text-paper-300 uppercase">Interview</p>
        <h2 class="font-serif text-2xl">{{ name }}</h2>
      </div>
    </header>

    <ol ref="log" class="flex-1 space-y-5 overflow-y-auto px-5 py-4" aria-live="polite">
      <li v-for="(x, i) in exchanges" :key="i" class="space-y-2">
        <p v-if="x.shown" class="ml-auto max-w-[85%] text-right text-sm text-brass-400 italic">
          You show {{ x.shown }}.
        </p>
        <p v-else-if="x.detective" class="ml-auto max-w-[85%] text-right text-sm text-paper-300">
          <span class="sr-only">You: </span>{{ x.detective }}
        </p>
        <div class="max-w-[90%]">
          <p class="font-mono text-[11px] tracking-wider text-brass-400 uppercase">
            {{ x.demeanor.replaceAll("_", " ") }}
          </p>
          <p class="font-serif text-lg leading-relaxed">
            “<TypedLine :text="x.suspect" :animate="i === freshIndex" />”
          </p>
        </div>
      </li>
      <li v-if="shrugged && !busy" class="text-sm text-paper-300 italic">
        {{ name }} looks at it, and says nothing new.
      </li>
      <li v-if="busy" class="font-mono text-xs text-night-500">{{ name }} is thinking…</li>
    </ol>

    <div class="space-y-3 border-t border-night-700 p-4">
      <form class="flex gap-2" @submit.prevent="ask">
        <label class="sr-only" for="question">Your question</label>
        <textarea
          id="question"
          v-model="question"
          rows="2"
          :maxlength="maxChars"
          :disabled="over"
          placeholder="Ask a question…"
          class="flex-1 resize-none rounded border border-night-700 bg-night-950 px-3 py-2 text-sm placeholder:text-night-500 focus:border-brass-400 focus:outline-none"
          @keydown="onKey"
        ></textarea>
        <button
          type="submit"
          :disabled="!canAsk"
          class="self-end rounded bg-paper-100 px-4 py-2 text-sm font-medium text-night-950 disabled:opacity-40"
        >
          Ask
        </button>
      </form>
      <div class="flex flex-wrap items-center justify-between gap-2">
        <form v-if="evidence.length" class="flex gap-2" @submit.prevent="show">
          <label class="sr-only" for="show-evidence">Evidence to show</label>
          <select
            id="show-evidence"
            v-model="chosen"
            class="max-w-56 rounded border border-night-700 bg-night-950 px-2 py-1.5 text-sm"
          >
            <option value="" disabled>Show evidence…</option>
            <option v-for="e in evidence" :key="e.id" :value="e.id">
              {{ e.id }} · {{ e.name }}
            </option>
          </select>
          <button
            type="submit"
            :disabled="!chosen || busy || over"
            class="rounded border border-brass-400 px-3 py-1.5 text-sm text-brass-400 disabled:opacity-40"
          >
            Show
          </button>
        </form>
        <p
          class="ml-auto font-mono text-xs"
          :class="remaining < 50 ? 'text-alarm-400' : 'text-night-500'"
        >
          {{ remaining }}
        </p>
      </div>
    </div>
  </section>
</template>
