<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import type { Accusation } from "../api/types";
import AccusationForm from "../components/AccusationForm.vue";
import CaseSidebar from "../components/CaseSidebar.vue";
import CaseTabs from "../components/CaseTabs.vue";
import HintBox from "../components/HintBox.vue";
import InterviewRoom from "../components/InterviewRoom.vue";
import ResultsPanel from "../components/ResultsPanel.vue";
import { questionsLeft } from "../game/budget";
import { forgetGame } from "../game/lastGame";
import { useGame } from "../game/useGame";

const props = defineProps<{ id: string }>();
const { cover, game, busy, error, lost, feed, fresh, shrugged, suspect, load, act } = useGame(
  props.id,
);
const accusing = ref(false);
const left = computed(() => (game.value ? questionsLeft(game.value) : null));

onMounted(load);

const names = computed(() =>
  Object.fromEntries((cover.value?.people ?? []).map((p) => [p.id, p.name])),
);
const victim = computed(
  () => cover.value?.people.find((p) => p.role === "victim")?.name ?? "the victim",
);
const exchanges = computed(() => {
  const id = game.value?.current_suspect;
  return id ? (game.value?.interviews[id] ?? []) : [];
});
const freshIndex = computed(() =>
  fresh.value && fresh.value.suspect === game.value?.current_suspect ? fresh.value.index : null,
);

async function accuse(accusation: Accusation): Promise<void> {
  await act("accuse", { accusation });
}

// The accusation is final: once the server says the game is over, show the result.
watch(
  () => game.value?.over,
  (over) => {
    if (over) {
      accusing.value = false;
      forgetGame();
    }
  },
);
</script>

<template>
  <div class="mx-auto flex min-h-dvh max-w-7xl flex-col px-4 py-4">
    <header
      class="flex flex-wrap items-center justify-between gap-3 border-b border-night-700 pb-3"
    >
      <div>
        <RouterLink to="/" class="font-serif text-lg hover:text-brass-400">
          {{ cover?.title ?? "CASEFILE" }}
        </RouterLink>
        <p v-if="game && cover" class="font-mono text-xs text-night-500">
          {{ game.detective.name }} · {{ cover.detective.callsign }}
        </p>
      </div>
      <div class="flex items-center gap-4">
        <p
          v-if="left !== null"
          class="font-mono text-xs"
          :class="left < 15 ? 'text-alarm-400' : 'text-night-500'"
          title="Each game has a cap on AI work. It's a safety limit, not a cost: on a local model it is free."
        >
          About {{ left }} questions left
        </p>
        <button
          v-if="game && !game.over && !accusing"
          type="button"
          class="rounded border border-alarm-500 px-4 py-1.5 text-sm text-alarm-400 hover:bg-alarm-500/10"
          @click="accusing = true"
        >
          Make your accusation
        </button>
      </div>
    </header>

    <div v-if="lost" class="mx-auto mt-20 max-w-md text-center">
      <p class="font-serif text-2xl">This case file is gone.</p>
      <p class="mt-2 text-sm text-paper-300">
        Saved games are kept for 30 days after they were last played, and only on the server that
        started them.
      </p>
      <RouterLink
        to="/"
        class="mt-6 inline-block rounded bg-alarm-500 px-5 py-2 text-paper-100"
        @click="forgetGame"
      >
        Start again
      </RouterLink>
    </div>

    <template v-else-if="game && cover">
      <p
        v-if="error"
        role="alert"
        class="mt-3 rounded border border-alarm-500/50 bg-alarm-500/10 px-4 py-2 text-sm"
      >
        {{ error }}
      </p>

      <template v-if="game.result">
        <ResultsPanel :result="game.result" />
        <RouterLink
          to="/"
          class="mx-auto mb-10 rounded border border-night-700 px-5 py-2 text-paper-300 hover:border-night-500"
        >
          Back to the case file
        </RouterLink>
      </template>

      <div v-else class="mt-4 grid flex-1 gap-6 lg:grid-cols-[14rem_1fr_22rem]">
        <!-- On a phone the interview comes first; the lists follow it. -->
        <div class="order-2 space-y-6 lg:order-none">
          <CaseSidebar
            :suspects="game.suspects"
            :locations="game.locations"
            :current="game.current_suspect"
            :busy="busy"
            :over="game.over"
            @talk="(s) => act('talk', { suspect: s })"
            @search="(l) => act('search', { location: l })"
          />
          <HintBox
            v-if="game.help.hints !== 'none'"
            :hints="game.hints"
            :busy="busy"
            :over="game.over"
            @hint="act('hint', {})"
          />
        </div>

        <section
          v-if="accusing"
          class="order-1 rounded-lg border border-alarm-500/40 bg-night-900 p-5 lg:order-none"
        >
          <AccusationForm
            :options="cover.accusation"
            :victim="victim"
            :names="names"
            :evidence="game.evidence"
            :busy="busy"
            @accuse="accuse"
            @cancel="accusing = false"
          />
        </section>
        <InterviewRoom
          v-else-if="suspect"
          class="order-1 h-[70dvh] lg:order-none lg:h-[calc(100dvh-7rem)]"
          :name="suspect.name"
          :exchanges="exchanges"
          :fresh-index="freshIndex"
          :evidence="game.evidence"
          :busy="busy"
          :max-chars="cover.max_question_chars"
          :over="game.over"
          :shrugged="shrugged"
          @ask="(text) => act('ask', { text })"
          @show="(e) => act('show', { evidence: e })"
        />
        <section
          v-else
          class="order-1 flex items-center justify-center rounded-lg border border-dashed border-night-700 p-10 text-center lg:order-none"
        >
          <p class="max-w-sm font-serif text-lg text-paper-300">
            Choose someone to interview, or search the house. Everyone here is lying about
            something.
          </p>
        </section>

        <CaseTabs
          class="order-3 lg:order-none"
          :feed="feed"
          :notebook="game.notebook"
          :statements="game.statements"
          :evidence="game.evidence"
          :help="game.help"
          :names="names"
        />
      </div>
    </template>

    <p v-else-if="error" role="alert" class="mt-20 text-center text-sm">{{ error }}</p>
    <p v-else class="mt-20 text-center font-mono text-xs text-night-500">Opening the file…</p>
  </div>
</template>
