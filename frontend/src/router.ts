import { createRouter, createWebHistory } from "vue-router";

import CoverView from "./views/CoverView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "cover", component: CoverView },
    // The game ID is in the URL, so a reload resumes the same game from the server.
    {
      path: "/game/:id",
      name: "game",
      component: () => import("./views/GameView.vue"),
      props: true,
    },
    { path: "/:rest(.*)*", redirect: "/" },
  ],
});
