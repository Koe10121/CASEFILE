<script setup lang="ts">
import type { Location, Suspect } from "../api/types";

defineProps<{
  suspects: readonly Suspect[];
  locations: readonly Location[];
  current: string | null;
  busy: boolean;
  over: boolean;
}>();

const emit = defineEmits<{ talk: [suspect: string]; search: [location: string] }>();
</script>

<template>
  <nav class="space-y-8" aria-label="Investigation">
    <section>
      <h2 class="font-mono text-xs tracking-widest text-paper-300 uppercase">Suspects</h2>
      <ul class="mt-2 space-y-1">
        <li v-for="s in suspects" :key="s.id">
          <button
            type="button"
            class="flex w-full items-center justify-between rounded px-3 py-2 text-left transition-colors disabled:opacity-50"
            :class="
              s.id === current ? 'bg-night-800 text-paper-100' : 'text-paper-300 hover:bg-night-900'
            "
            :aria-current="s.id === current ? 'true' : undefined"
            :disabled="busy || over"
            @click="emit('talk', s.id)"
          >
            <span class="font-serif">{{ s.name }}</span>
            <span v-if="!s.interviewed" class="font-mono text-[10px] text-brass-400 uppercase"
              >new</span
            >
          </button>
        </li>
      </ul>
    </section>

    <section>
      <h2 class="font-mono text-xs tracking-widest text-paper-300 uppercase">Places to search</h2>
      <ul class="mt-2 space-y-1">
        <li v-for="loc in locations" :key="loc.id">
          <button
            type="button"
            class="w-full rounded px-3 py-2 text-left text-sm transition-colors enabled:hover:bg-night-900 disabled:cursor-not-allowed"
            :class="loc.accessible ? 'text-paper-300' : 'text-night-500'"
            :title="loc.accessible ? loc.description : 'Locked for now'"
            :disabled="busy || over || !loc.accessible || loc.searched"
            @click="emit('search', loc.id)"
          >
            <span>{{ loc.name }}</span>
            <span v-if="loc.searched" class="ml-2 font-mono text-[10px] text-night-500 uppercase"
              >searched</span
            >
            <span v-else-if="!loc.accessible" class="ml-2 font-mono text-[10px] uppercase"
              >locked</span
            >
          </button>
        </li>
      </ul>
    </section>
  </nav>
</template>
