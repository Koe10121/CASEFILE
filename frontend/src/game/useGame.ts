import { computed, ref, shallowRef } from "vue";

import { ApiError, api } from "../api/client";
import type { ActionBodies, CaseCover, Game, GameEvent, Verb } from "../api/types";

/**
 * One game, as the server reports it. The browser keeps no rules of its own: after every
 * action it replaces its copy of the game with the one the server sent back (D43).
 */
export function useGame(id: string) {
  const cover = shallowRef<CaseCover | null>(null);
  const game = shallowRef<Game | null>(null);
  const busy = ref(false);
  const error = ref<string | null>(null);
  const lost = ref(false);
  /** What the last action caused, newest first, for the "what just happened" feed. */
  const feed = ref<GameEvent[]>([]);
  /** The transcript entry that just arrived, which the interview types out. */
  const fresh = ref<{ suspect: string; index: number } | null>(null);

  const suspect = computed(() => {
    const current = game.value?.current_suspect;
    return current ? (cover.value?.people.find((p) => p.id === current) ?? null) : null;
  });

  async function guarded(work: () => Promise<void>): Promise<void> {
    if (busy.value) return; // the server would refuse an overlapping move anyway (D46)
    busy.value = true;
    error.value = null;
    try {
      await work();
    } catch (e) {
      if (!(e instanceof ApiError)) throw e;
      error.value = e.message;
      lost.value = e.gameLost;
    } finally {
      busy.value = false;
    }
  }

  function load(): Promise<void> {
    return guarded(async () => {
      [cover.value, game.value] = await Promise.all([api.getCase(), api.getGame(id)]);
    });
  }

  function act<V extends Verb>(verb: V, body: ActionBodies[V]): Promise<void> {
    return guarded(async () => {
      const result = await api.act(id, verb, body);
      game.value = result.game;
      if (result.events.length) feed.value = [...result.events].reverse().concat(feed.value);
      const line = result.line;
      if (line) {
        const exchanges = result.game.interviews[line.suspect] ?? [];
        fresh.value = { suspect: line.suspect, index: exchanges.length - 1 };
      }
    });
  }

  return { cover, game, busy, error, lost, feed, fresh, suspect, load, act };
}

export type GameStore = ReturnType<typeof useGame>;
