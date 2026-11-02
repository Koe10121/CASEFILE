<script setup lang="ts">
import { ref } from "vue";

import { checkOllama, ollamaUrl, originsCommand, saveOllamaUrl } from "../game/ownOllama";

// For a game played by the Ollama on the player's own computer (D60).
const props = defineProps<{ model: string }>();

const url = ref(ollamaUrl());
const checking = ref(false);
const result = ref<{ ok: boolean; text: string } | null>(null);

async function check(): Promise<void> {
  saveOllamaUrl(url.value);
  checking.value = true;
  try {
    const problem = await checkOllama(props.model);
    result.value = problem
      ? { ok: false, text: problem }
      : { ok: true, text: `Ollama is ready with ${props.model}.` };
  } finally {
    checking.value = false;
  }
}
</script>

<template>
  <section class="rounded-lg border border-brass-400/40 bg-night-900 p-5 text-sm">
    <h2 class="font-mono text-xs tracking-widest text-brass-400 uppercase">Your Ollama</h2>
    <p class="mt-2 leading-relaxed text-paper-300">
      The suspects run on your own graphics card, through this page, so it costs nothing. A curious
      player could read the suspects' secret notes in the browser's developer tools, so don't look
      if you want the case unspoiled. Once on this computer:
    </p>
    <ol class="mt-3 list-decimal space-y-2 pl-5 text-paper-300">
      <li>
        Install Ollama from
        <a
          href="https://ollama.com"
          target="_blank"
          rel="noopener noreferrer"
          class="text-brass-400 underline"
          >ollama.com</a
        >, then in Command Prompt run <code class="text-paper-100">ollama pull {{ model }}</code>
      </li>
      <li>
        Let this site talk to it:
        <code class="break-all text-paper-100">{{ originsCommand() }}</code>
      </li>
      <li>
        Quit Ollama from the tray and start it again. If the browser asks to reach devices on your
        network, allow it.
      </li>
    </ol>
    <div class="mt-4 flex flex-wrap items-center gap-2">
      <label class="sr-only" for="ollama-url">Ollama address</label>
      <input
        id="ollama-url"
        v-model="url"
        spellcheck="false"
        class="min-w-0 flex-1 rounded border border-night-700 bg-night-950 px-3 py-1.5 font-mono text-sm focus:border-brass-400 focus:outline-none"
      />
      <button
        type="button"
        :disabled="checking"
        class="rounded border border-brass-400 px-4 py-1.5 text-brass-400 disabled:opacity-40"
        @click="check"
      >
        {{ checking ? "Checking…" : "Check Ollama" }}
      </button>
    </div>
    <p
      v-if="result"
      class="mt-3"
      :class="result.ok ? 'text-paper-100' : 'text-alarm-400'"
      role="status"
    >
      {{ result.text }}
    </p>
  </section>
</template>
