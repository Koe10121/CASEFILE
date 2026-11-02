<script setup lang="ts">
import { computed, onMounted } from "vue";

import CaseSidebar from "../components/CaseSidebar.vue";
import EventFeed from "../components/EventFeed.vue";
import EvidenceList from "../components/EvidenceList.vue";
import InterviewRoom from "../components/InterviewRoom.vue";
import { forgetGame } from "../game/lastGame";
import { useGame } from "../game/useGame";

const props = defineProps<{ id: string }>();
const { cover, game, busy, error, lost, feed, fresh, suspect, load, act } = useGame(props.id);

onMounted(load);

const exchanges = computed(() => {
  const id = game.value?.current_suspect;
  return id ? (game.value?.interviews[id] ?? []) : [];
});
const freshIndex = computed(() =>
  fresh.value && fresh.value.suspect === game.value?.current_suspect ? fresh.value.index : null,
);

function startOver(): void {
  forgetGame();
}
</script>

<template>
  <div class="mx-auto flex min-h-dvh max-w-7xl flex-col px-4 py-4">
    <header class="flex items-baseline justify-between gap-4 border-b border-night-700 pb-3">
      <RouterLink to="/" class="font-serif text-lg hover:text-brass-400">
        {{ cover?.title ?? "CASEFILE" }}
      </RouterLink>
      <p v-if="game?.tokens.budget" class="font-mono text-xs text-night-500">
        {{ Math.round((100 * game.tokens.used) / game.tokens.budget) }}% of this game's AI budget
        used
      </p>
    </header>

    <div v-if="lost" class="mx-auto mt-20 max-w-md text-center">
      <p class="font-serif text-2xl">This case file is gone.</p>
      <p class="mt-2 text-sm text-paper-300">
        The server forgets games when it restarts or after two hours idle. Saving games is coming.
      </p>
      <RouterLink
        to="/"
        class="mt-6 inline-block rounded bg-alarm-500 px-5 py-2 text-paper-100"
        @click="startOver"
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

      <div class="mt-4 grid flex-1 gap-6 lg:grid-cols-[14rem_1fr_20rem]">
        <!-- On a phone the interview comes first; the lists follow it. -->
        <CaseSidebar
          class="order-2 lg:order-none"
          :suspects="game.suspects"
          :locations="game.locations"
          :current="game.current_suspect"
          :busy="busy"
          :over="game.over"
          @talk="(s) => act('talk', { suspect: s })"
          @search="(l) => act('search', { location: l })"
        />

        <InterviewRoom
          v-if="suspect"
          class="order-1 h-[70dvh] lg:order-none lg:h-[calc(100dvh-7rem)]"
          :name="suspect.name"
          :exchanges="exchanges"
          :fresh-index="freshIndex"
          :evidence="game.evidence"
          :busy="busy"
          :max-chars="cover.max_question_chars"
          :over="game.over"
          @ask="(text) => act('ask', { text })"
          @show="(e) => act('show', { evidence: e })"
        />
        <section
          v-else
          class="order-1 flex items-center lg:order-none justify-center rounded-lg border border-dashed border-night-700 p-10 text-center"
        >
          <p class="max-w-sm font-serif text-lg text-paper-300">
            Choose someone to interview, or search the house. Everyone here is lying about
            something.
          </p>
        </section>

        <aside class="order-3 space-y-8 lg:order-none">
          <EventFeed :events="feed" />
          <EvidenceList :evidence="game.evidence" />
        </aside>
      </div>
    </template>

    <p v-else-if="error" role="alert" class="mt-20 text-center text-sm">{{ error }}</p>
    <p v-else class="mt-20 text-center font-mono text-xs text-night-500">Opening the file…</p>
  </div>
</template>
