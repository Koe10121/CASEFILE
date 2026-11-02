<script setup lang="ts">
import { computed, ref } from "vue";

import { forgetPlayerKey, playerKey, savePlayerKey } from "../game/playerKey";

// On a server where Claude plays the suspects on the player's own key (D58).
const props = defineProps<{ refused?: boolean }>();
const emit = defineEmits<{ saved: [] }>();

const saved = ref(playerKey() !== null);
// A refused key opens the box straight away: the player has to change it anyway.
const editing = ref(!saved.value || props.refused);
const draft = ref("");
const remember = ref(false);
const looksWrong = computed(
  () => draft.value.trim() !== "" && !draft.value.trim().startsWith("sk-ant-"),
);

function save(): void {
  if (!draft.value.trim()) return;
  savePlayerKey(draft.value, remember.value);
  draft.value = "";
  saved.value = true;
  editing.value = false;
  emit("saved");
}

function forget(): void {
  forgetPlayerKey();
  saved.value = false;
  editing.value = true;
}
</script>

<template>
  <section class="rounded-lg border border-brass-400/40 bg-night-900 p-5">
    <h2 class="font-mono text-xs tracking-widest text-brass-400 uppercase">Your Claude API key</h2>
    <p v-if="refused" class="mt-2 text-sm text-alarm-400">
      The suspects need a working key. Check it, or paste a new one.
    </p>
    <p class="mt-2 text-sm leading-relaxed text-paper-300">
      Here Claude plays the suspects, paid for with your own Anthropic API key. Get one at
      <a
        href="https://console.anthropic.com/settings/keys"
        target="_blank"
        rel="noopener noreferrer"
        class="text-brass-400 underline"
        >console.anthropic.com</a
      >, and set a spend limit there. The key stays in this browser and goes to the game server only
      with each question, which uses it for that one reply and never saves it. Each game has a cap
      on how much it can spend.
    </p>

    <form v-if="editing" class="mt-4 space-y-3" @submit.prevent="save">
      <label class="block text-sm" for="claude-key">API key</label>
      <input
        id="claude-key"
        v-model="draft"
        type="password"
        autocomplete="off"
        spellcheck="false"
        placeholder="sk-ant-…"
        class="w-full rounded border border-night-700 bg-night-950 px-3 py-2 font-mono text-sm placeholder:text-night-500 focus:border-brass-400 focus:outline-none"
      />
      <p v-if="looksWrong" class="text-xs text-alarm-400">
        Anthropic keys start with <code>sk-ant-</code>.
      </p>
      <div class="flex flex-wrap items-center justify-between gap-3">
        <label class="flex items-center gap-2 text-sm text-paper-300">
          <input v-model="remember" type="checkbox" class="accent-brass-400" />
          Remember on this device
        </label>
        <button
          type="submit"
          :disabled="!draft.trim()"
          class="rounded border border-brass-400 px-4 py-1.5 text-sm text-brass-400 disabled:opacity-40"
        >
          Use this key
        </button>
      </div>
    </form>
    <p v-else class="mt-4 flex flex-wrap items-center gap-3 text-sm">
      <span class="text-paper-100">Key saved in this browser.</span>
      <button type="button" class="text-brass-400 underline" @click="editing = true">
        Change it
      </button>
      <button type="button" class="text-paper-300 underline" @click="forget">Forget it</button>
    </p>
  </section>
</template>
