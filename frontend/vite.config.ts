import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

// `npm run dev` serves the app on :5173 and forwards the API and room sockets
// to the Python server on :8000. `npm run build` writes dist/, which the
// Python app serves in every other setup.
export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
