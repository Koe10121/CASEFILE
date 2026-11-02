<script setup lang="ts">
import { toRef } from "vue";

import { useTypewriter } from "../composables/useTypewriter";

const props = defineProps<{ text: string; animate: boolean }>();
const { shown, typing, finish } = useTypewriter(toRef(props, "text"), toRef(props, "animate"));
</script>

<template>
  <!-- Screen readers get the whole line at once; the typing is visual only. -->
  <span class="sr-only">{{ text }}</span>
  <span aria-hidden="true" :class="typing ? 'cursor-pointer' : ''" @click="finish">
    {{ shown }}<span v-if="typing" class="animate-pulse text-paper-300">▍</span>
  </span>
</template>
