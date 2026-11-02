<script setup lang="ts">
import { onMounted, ref, shallowRef } from "vue";
import { useRouter } from "vue-router";

import { ApiError, api } from "../api/client";
import type { CaseCover, Difficulty } from "../api/types";
import { lastGame, rememberGame } from "../game/lastGame";

const router = useRouter();
const cover = shallowRef<CaseCover | null>(null);
const error = ref<string | null>(null);
const starting = ref(false);
const difficulty = ref<Difficulty>("normal");
const previous = lastGame();

const difficulties: { id: Difficulty; label: string }[] = [
  { id: "easy", label: "Easy" },
  { id: "normal", label: "Normal" },
  { id: "hard", label: "Hard" },
];

const players: Record<string, string> = {
  mock: "scripted suspects (no AI)",
  ollama: "a local model (Ollama)",
  claude: "Claude",
};

onMounted(async () => {
  try {
    cover.value = await api.getCase();
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    error.value = e.message;
  }
});

async function start(): Promise<void> {
  starting.value = true;
  error.value = null;
  try {
    const game = await api.newGame(difficulty.value);
    rememberGame(game.id);
    await router.push({ name: "game", params: { id: game.id } });
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    error.value = e.message;
  } finally {
    starting.value = false;
  }
}
</script>

<template>
  <main class="mx-auto max-w-3xl px-4 py-12 sm:py-20">
    <p class="font-mono text-xs tracking-[0.3em] text-alarm-400 uppercase">Casefile #001</p>

    <p v-if="error" role="alert" class="mt-6 rounded border border-alarm-500/50 p-4 text-sm">
      {{ error }}
    </p>

    <template v-if="cover">
      <h1 class="mt-3 font-serif text-4xl leading-tight sm:text-5xl">{{ cover.title }}</h1>
      <p class="mt-2 text-sm text-paper-300">
        {{ cover.place }} ·
        {{ new Date(cover.date).toLocaleDateString("en-GB", { dateStyle: "full" }) }}
      </p>
      <p class="mt-8 font-serif text-lg leading-relaxed whitespace-pre-line">{{ cover.intro }}</p>

      <section class="mt-10 rounded-lg border border-night-700 bg-night-900 p-5">
        <p class="font-mono text-xs tracking-widest text-brass-400 uppercase">
          You are {{ cover.detective.callsign }}
        </p>
        <p class="mt-1 font-serif text-xl">{{ cover.detective.name }}</p>
        <p class="mt-2 text-sm leading-relaxed text-paper-300">{{ cover.detective.bio }}</p>
      </section>

      <section class="mt-10">
        <h2 class="font-mono text-xs tracking-widest text-paper-300 uppercase">In the house</h2>
        <ul class="mt-3 grid gap-3 sm:grid-cols-2">
          <li
            v-for="person in cover.people"
            :key="person.id"
            class="rounded-lg border border-night-700 p-4"
            :class="person.role === 'victim' ? 'border-alarm-500/40' : ''"
          >
            <p class="font-serif text-lg">
              {{ person.name }}<span class="text-sm text-paper-300">, {{ person.age }}</span>
            </p>
            <p v-if="person.role === 'victim'" class="font-mono text-xs text-alarm-400 uppercase">
              Victim
            </p>
            <p class="mt-1 text-sm leading-relaxed text-paper-300">{{ person.bio }}</p>
          </li>
        </ul>
      </section>

      <fieldset class="mt-10">
        <legend class="font-mono text-xs tracking-widest text-paper-300 uppercase">
          Difficulty
        </legend>
        <p class="mt-1 text-sm text-paper-300">
          Changes how much help you get. The truth is the same.
        </p>
        <div class="mt-3 flex gap-2">
          <label
            v-for="d in difficulties"
            :key="d.id"
            class="cursor-pointer rounded border px-4 py-2 text-sm transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-brass-400"
            :class="
              difficulty === d.id
                ? 'border-brass-400 bg-brass-400/10 text-paper-100'
                : 'border-night-700 text-paper-300 hover:border-night-500'
            "
          >
            <input
              v-model="difficulty"
              type="radio"
              name="difficulty"
              :value="d.id"
              class="sr-only"
            />
            {{ d.label }}
          </label>
        </div>
      </fieldset>

      <div class="mt-10 flex flex-wrap items-center gap-3">
        <button
          type="button"
          class="rounded bg-alarm-500 px-6 py-3 font-medium text-paper-100 transition-colors hover:bg-alarm-400 disabled:opacity-60"
          :disabled="starting"
          @click="start"
        >
          {{ starting ? "Opening the file…" : "Take the case" }}
        </button>
        <RouterLink
          v-if="previous"
          :to="{ name: 'game', params: { id: previous } }"
          class="rounded border border-night-700 px-6 py-3 text-paper-300 hover:border-night-500"
        >
          Continue your investigation
        </RouterLink>
      </div>
      <p class="mt-4 text-xs text-night-500">
        Suspects played by {{ players[cover.ai] ?? cover.ai }}.
      </p>
    </template>
  </main>
</template>
