<script setup lang="ts">
import { computed, onMounted, ref, shallowRef } from "vue";
import { useRouter } from "vue-router";

import { ApiError, api } from "../api/client";
import type { CaseCover, Difficulty, PlayedBy } from "../api/types";
import OllamaSetup from "../components/OllamaSetup.vue";
import PlayerKeyForm from "../components/PlayerKeyForm.vue";
import SuspectPortrait from "../components/SuspectPortrait.vue";
import { lastGame, rememberGame } from "../game/lastGame";
import { playerKey } from "../game/playerKey";

const router = useRouter();
const cover = shallowRef<CaseCover | null>(null);
const error = ref<string | null>(null);
const starting = ref(false);
const difficulty = ref<Difficulty>("normal");
const identityId = ref("");
const identity = computed(() => {
  const identities = cover.value?.detective.identities ?? [];
  return identities.find((i) => i.id === identityId.value) ?? identities[0] ?? null;
});
const previous = lastGame();
const hasKey = ref(playerKey() !== null);
// On the public server the player picks who plays the suspects (D58-D60): free scripted
// suspects (the default until a key is saved), the Ollama on their own computer, or
// Claude on their own key.
const playedBy = ref<PlayedBy>(hasKey.value ? "server" : "scripted");
const choosing = computed(() => cover.value?.player_keys === true);
const needsKey = computed(() => choosing.value && playedBy.value === "server" && !hasKey.value);
const suspectChoices: { id: PlayedBy; label: string; note: string }[] = [
  {
    id: "scripted",
    label: "Scripted suspects, free",
    note: "No setup, no cost. The suspects answer from a fixed script.",
  },
  {
    id: "your_ollama",
    label: "Your Ollama, free",
    note: "AI suspects on your own graphics card. Needs Ollama on this computer.",
  },
  {
    id: "server",
    label: "Claude, on your own key",
    note: "The best AI suspects. You pay Anthropic for your questions.",
  },
];

const choiceNames: Record<PlayedBy, string> = {
  scripted: "scripted suspects (no AI)",
  your_ollama: "the Ollama on your computer",
  server: "Claude, on your key",
};

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
    identityId.value = cover.value.detective.identities[0]?.id ?? "";
  } catch (e) {
    if (!(e instanceof ApiError)) throw e;
    error.value = e.message;
  }
});

async function start(): Promise<void> {
  starting.value = true;
  error.value = null;
  try {
    const game = await api.newGame(
      difficulty.value,
      identityId.value,
      choosing.value ? playedBy.value : "server",
    );
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

      <section v-if="identity" class="mt-10 rounded-lg border border-night-700 bg-night-900 p-5">
        <p class="font-mono text-xs tracking-widest text-brass-400 uppercase">
          You are {{ cover.detective.callsign }}
        </p>
        <p class="mt-1 font-serif text-xl">
          {{ identity.name }}
          <span class="text-sm text-paper-300">({{ identity.pronouns }})</span>
        </p>
        <p class="mt-2 text-sm leading-relaxed text-paper-300">{{ identity.bio }}</p>
        <fieldset v-if="cover.detective.identities.length > 1" class="mt-4">
          <legend class="mb-2 text-xs text-paper-300">Play as</legend>
          <div class="flex flex-wrap gap-2">
            <label
              v-for="i in cover.detective.identities"
              :key="i.id"
              class="cursor-pointer rounded border px-3 py-1.5 text-sm transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-brass-400"
              :class="
                identityId === i.id
                  ? 'border-brass-400 bg-brass-400/10 text-paper-100'
                  : 'border-night-700 text-paper-300 hover:border-night-500'
              "
            >
              <input
                v-model="identityId"
                type="radio"
                name="identity"
                :value="i.id"
                class="sr-only"
              />
              {{ i.label }}
            </label>
          </div>
        </fieldset>
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
            <div class="flex gap-3">
              <SuspectPortrait
                :id="person.id"
                :name="person.name"
                expression="neutral"
                :faces="cover.portraits[person.id] ?? []"
                size="sm"
              />
              <div>
                <p class="font-serif text-lg">
                  {{ person.name }}<span class="text-sm text-paper-300">, {{ person.age }}</span>
                </p>
                <p
                  v-if="person.role === 'victim'"
                  class="font-mono text-xs text-alarm-400 uppercase"
                >
                  Victim
                </p>
                <p class="mt-1 text-sm leading-relaxed text-paper-300">{{ person.bio }}</p>
              </div>
            </div>
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

      <fieldset v-if="cover.player_keys" class="mt-10">
        <legend class="font-mono text-xs tracking-widest text-paper-300 uppercase">Suspects</legend>
        <div class="mt-3 grid gap-2 sm:grid-cols-3">
          <label
            v-for="c in suspectChoices"
            :key="c.id"
            class="cursor-pointer rounded border px-4 py-3 text-sm transition-colors has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-brass-400"
            :class="
              playedBy === c.id
                ? 'border-brass-400 bg-brass-400/10 text-paper-100'
                : 'border-night-700 text-paper-300 hover:border-night-500'
            "
          >
            <input v-model="playedBy" type="radio" name="suspects" :value="c.id" class="sr-only" />
            <span class="block font-medium">{{ c.label }}</span>
            <span class="mt-1 block text-xs text-paper-300">{{ c.note }}</span>
          </label>
        </div>
      </fieldset>

      <PlayerKeyForm v-if="choosing && playedBy === 'server'" class="mt-6" @saved="hasKey = true" />
      <OllamaSetup
        v-if="choosing && playedBy === 'your_ollama'"
        class="mt-6"
        :model="cover.ollama_model"
      />

      <div class="mt-10 flex flex-wrap items-center gap-3">
        <button
          type="button"
          class="rounded bg-alarm-500 px-6 py-3 font-medium text-paper-100 transition-colors hover:bg-alarm-400 disabled:opacity-60"
          :disabled="starting || needsKey"
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
        Suspects played by
        {{ choosing ? choiceNames[playedBy] : (players[cover.ai] ?? cover.ai) }}.
      </p>
    </template>
  </main>
</template>
