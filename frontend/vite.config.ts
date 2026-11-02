/// <reference types="vitest/config" />
import tailwindcss from "@tailwindcss/vite";
import vue from "@vitejs/plugin-vue";
import { defineConfig } from "vite";

// In development the browser talks only to Vite, which forwards /api to the backend.
// Same origin in dev and in production, so the API needs no CORS (D47).
export default defineConfig({
  plugins: [vue(), tailwindcss()],
  server: {
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  test: {
    environment: "jsdom",
  },
});
