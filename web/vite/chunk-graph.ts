import { relative, sep } from "node:path";

import type { Plugin, Rollup } from "vite";

/**
 * Write down which modules each chunk of the build holds, and how the chunks import each other.
 *
 * The evaluation's and the tutor's client code must reach a browser only when the function is
 * open to the account, which means only through a dynamic `import()`. A static import from
 * core pulls the module into the chunks every session loads, and nothing on screen says so:
 * the page works, it only downloads code it will never run. `scripts/check-lazy.mjs` reads
 * this file and walks the STATIC import closure of the entry chunk, which is exactly what a
 * browser fetches before anything is decided.
 *
 * The file is `dist/.vite/chunks.json`, beside where Vite puts its own manifest. Module ids
 * are relative to `web/` with `/` separators; virtual modules and `node_modules` are left
 * out, since the check is about this app's own folders and the dependencies are most of the
 * module count.
 *
 * It applies to `vite build` only: the dev server has no chunks.
 */

/** Where the graph is written, relative to the build's output directory. */
export const CHUNK_GRAPH = ".vite/chunks.json";

/** One chunk of the build, as `check-lazy` reads it. */
export interface ChunkRecord {
  fileName: string;
  isEntry: boolean;
  isDynamicEntry: boolean;
  /**
   * The modules of this chunk that some `import()` names: what a dynamic entry stands for.
   * Read off the module graph and not off `facadeModuleId`, which Rollup leaves null for a
   * dynamic entry whose chunk other chunks also import.
   */
  dynamicEntries: string[];
  /** Chunks this one imports statically: fetched with it. */
  imports: string[];
  /** Chunks this one may import later, through `import()`. */
  dynamicImports: string[];
  moduleIds: string[];
}

/** A module id as the check reads it, or null for one it has no business with. */
function moduleId(root: string, id: string): string | null {
  if (id.startsWith("\0") || id.includes(`${sep}node_modules${sep}`) || id.includes("/node_modules/")) {
    return null;
  }
  const path = id.split("?")[0];
  return relative(root, path).split(sep).join("/");
}

/** Describe one output chunk as `check-lazy` reads it. */
function record(
  root: string,
  chunk: Rollup.OutputChunk,
  info: (id: string) => Rollup.ModuleInfo | null,
): ChunkRecord {
  return {
    fileName: chunk.fileName,
    isEntry: chunk.isEntry,
    isDynamicEntry: chunk.isDynamicEntry,
    dynamicEntries: chunk.moduleIds.flatMap((id) =>
      (info(id)?.dynamicImporters.length ?? 0) > 0 ? (moduleId(root, id) ?? []) : [],
    ),
    imports: chunk.imports,
    dynamicImports: chunk.dynamicImports,
    moduleIds: chunk.moduleIds.flatMap((id) => moduleId(root, id) ?? []),
  };
}

/** Build the plugin that writes `CHUNK_GRAPH` beside the bundle. */
export function chunkGraph(): Plugin {
  let root = process.cwd();

  return {
    name: "variatio:chunk-graph",
    apply: "build",

    configResolved(config) {
      root = config.root;
    },

    generateBundle(_options, bundle) {
      const info = (id: string) => this.getModuleInfo(id);
      const chunks = Object.values(bundle).flatMap((output) =>
        output.type === "chunk" ? [record(root, output, info)] : [],
      );
      this.emitFile({
        type: "asset",
        fileName: CHUNK_GRAPH,
        source: `${JSON.stringify({ chunks }, null, 2)}\n`,
      });
    },
  };
}
