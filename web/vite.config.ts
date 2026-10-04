import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

import { chunkGraph } from "./vite/chunk-graph";
import { mermaidSubset } from "./vite/mermaid-subset";

const API = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";

// Proxying in dev means the app always talks to same-origin relative URLs, so the
// exact same code works when FastAPI serves the built bundle. No CORS, no env juggling.
export default defineConfig({
  plugins: [react(), tailwindcss(), mermaidSubset(), chunkGraph()],
  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": { target: API, changeOrigin: true },
      "/ws": { target: API.replace(/^http/, "ws"), ws: true },
    },
  },
  build: {
    rollupOptions: {
      output: {
        // WHAT THIS BUYS IS CACHING AND PARALLELISM, NOT FEWER BYTES, and saying so is the
        // point of the comment: the same bundle comes out in three files instead of one.
        // Today a single byte of application code invalidates 194 kB of React for every
        // returning reader, and the vendor chunks get their own `modulepreload`, so they
        // download beside the entry rather than after it. What actually removes bytes is
        // the catalogue split in `lib/i18n`.
        //
        // The FUNCTION form, and not the object form: `scheduler` is a transitive
        // dependency of react-dom that pnpm's strict layout does not hoist, so naming it
        // as an entry fails the build with «Could not resolve entry module "scheduler"».
        // The three go in ONE chunk deliberately — splitting them invites module
        // init-order problems around the React singleton for no gain.
        manualChunks(id: string) {
          if (!id.includes("node_modules")) return;
          if (/[\\/]node_modules[\\/](\.pnpm[\\/])?(react|react-dom|scheduler)[@\\/]/.test(id))
            return "react";
          if (id.includes("@tanstack")) return "query";
          // The typesetter is 82 kB gzipped and changes about once a year, while
          // `ResultCard` — the only thing that reaches it — changes with every pass over
          // the generate screen. In one chunk each of those passes re-downloaded KaTeX.
          // It is off the critical path either way: `Markdown` is imported from nowhere
          // but the item cards, which live behind lazy routes.
          if (id.includes("katex")) return "katex";
        },
        // An optional function's catalogue (`src/<function>/i18n/`) is a chunk of its own,
        // shared by the function's lazy modules, and Rollup would name it after its
        // `index.ts` — as it names the entry, so `dist/assets/index-*.js` would stop meaning
        // the entry chunk the catalogue split is measured by.
        //
        // Only a chunk made of that folder alone takes the name: were Rollup to inline the
        // catalogue into the one screen that imports it, the chunk is the screen's.
        chunkFileNames(chunk) {
          const ids = chunk.moduleIds.filter((id) => !id.startsWith("\0"));
          const home = ids
            .map((id) => /[\\/]src[\\/](?!lib[\\/])(\w+)[\\/]i18n[\\/]index\.ts$/.exec(id)?.[1])
            .find(Boolean);
          const alone = ids.every((id) => id.split(/[\\/]/).slice(-3, -1).join("/") === `${home}/i18n`);
          return home && alone ? `assets/${home}-i18n-[hash].js` : "assets/[name]-[hash].js";
        },
      },
    },
  },
});
