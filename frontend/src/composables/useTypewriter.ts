import { onScopeDispose, ref, watch, type Ref } from "vue";

/**
 * Reveal a finished line a few characters at a time. The suspect's whole line has
 * already passed the guard on the server; this is presentation only (D45).
 * Respects reduced motion, and `finish()` shows the rest at once.
 */
export function useTypewriter(text: Ref<string>, enabled: Ref<boolean>, msPerChar = 18) {
  const shown = ref(enabled.value ? "" : text.value);
  const typing = ref(false);
  let timer: ReturnType<typeof setInterval> | undefined;

  const reduced =
    typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true;

  function stop(): void {
    if (timer !== undefined) clearInterval(timer);
    timer = undefined;
    typing.value = false;
  }

  function finish(): void {
    stop();
    shown.value = text.value;
  }

  function start(): void {
    stop();
    if (!enabled.value || reduced) {
      shown.value = text.value;
      return;
    }
    shown.value = "";
    typing.value = true;
    let i = 0;
    timer = setInterval(() => {
      i += 2;
      shown.value = text.value.slice(0, i);
      if (i >= text.value.length) finish();
    }, msPerChar * 2);
  }

  watch([text, enabled], start, { immediate: true });
  onScopeDispose(stop);

  return { shown, typing, finish };
}
