import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const API = process.env.VITE_API_TARGET ?? "http://127.0.0.1:8000";

// Proxying in dev means the app always talks to same-origin relative URLs, so the
// exact same code works when FastAPI serves the built bundle. No CORS, no env juggling.
export default defineConfig({
  plugins: [react(), tailwindcss()],
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
        },
      },
    },
  },
});
