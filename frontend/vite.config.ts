import { readFileSync } from "node:fs";
import { svelte } from "@sveltejs/vite-plugin-svelte";
import { defineConfig } from "vite";

// The app's version comes from pyproject.toml, its one source (design.md, "Versions and releases").
const pyproject = readFileSync(new URL("../pyproject.toml", import.meta.url), "utf8");
const version = /^version\s*=\s*"([^"]+)"/m.exec(pyproject)?.[1];
if (!version) throw new Error("No version in pyproject.toml");

// `npm run dev` serves the app on :5173 and forwards the API and room sockets
// to the Python server on :8000. `npm run build` writes dist/, which the
// Python app serves in every other setup.
export default defineConfig({
  plugins: [svelte()],
  define: { __APP_VERSION__: JSON.stringify(version) },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
      "/ws": { target: "ws://localhost:8000", ws: true },
    },
  },
});
