import { createRequire } from "node:module";

import type { Plugin } from "vite";

import { DRAWN_DIAGRAMS } from "../src/lib/diagram";

/**
 * Leave out of the bundle every Mermaid diagram and layout engine this app cannot reach.
 *
 * Mermaid 12 registers 38 diagram types and 9 layout algorithms, each behind a lazy
 * `import()`, so Rollup emits a chunk per type whether or not anything can ask for it. That
 * is not a download — nobody fetches a chunk nothing imports — but it IS built and deployed,
 * and measured on this tree it was most of `dist/`: `lib/diagram.ts` names the EIGHT kinds
 * the transcription prompt asks for and `Diagram.tsx` pins the layout, so the other 30 —
 * `cynefin`, `wardley`, `usecase`, `architecture` and the rest — together with the 1.5 MB ELK
 * engine could only ever be dead weight.
 *
 * Two transforms, and both FAIL THE BUILD rather than degrade in silence if Mermaid's shape
 * moves — its chunk names carry its own content hashes, so nothing here may hard-code one:
 *
 *   - In the entry, each unsupported type's `loader` loses its `import()`. The ids are
 *     Mermaid's public names and come from `DRAWN_DIAGRAMS`, so the gate and the bundle
 *     cannot drift: a kind added to that table is one row, and the build follows.
 *   - In the chunk that registers the layout engines, every engine BUT DAGRE is unregistered,
 *     which is one rule rather than three surgeries: `Diagram.tsx` pins `layout: "dagre"`, so
 *     nothing can select another, and Mermaid's `getRegisteredLayoutAlgorithm` falls back to
 *     dagre for a diagram that asks for one anyway — the worst case is a diagram laid out by
 *     dagre and a console warning, never one that fails to draw. Mermaid does the same thing
 *     itself for its «tiny build», commented in that very function as «elkjs is ~1.6 MB of
 *     source, so it is excluded». It drops ELK (1.5 MB), cose-bilkent and the swimlane
 *     layout; `mindmap` is unaffected, laying out through the configured algorithm like a
 *     flowchart, and only `architecture` still pulls cytoscape.
 *
 * It applies to `vite build` only: in dev Vite pre-bundles mermaid with esbuild and these
 * hooks never see it, which is right — what this removes is the build's cost, not the
 * developer's.
 */

/** A diagram's id, as `mermaid.core.mjs` declares it before its detector and its loader. */
const ID = /var id(\d*) = "([^"]+)";/g;

const LAZY_IMPORT = /import\("\.\/chunks\/mermaid\.core\/[^"]+"\)/;

/** Where Mermaid registers its layout engines, and the only one this app can select. */
const LAYOUT_CALL = "registerLayoutLoaders([";
const DAGRE_ENTRY = /\{\s*name: "dagre",\s*loader:[^{}]*\}/;

/** Mermaid 12 lazy-loads 38; well under this means its registry is not what we parse. */
const MIN_REGISTERED = 25;

type Loader = { ident: string; start: number; end: number };

function isEntry(id: string): boolean {
  return id.replace(/\\/g, "/").endsWith("/mermaid/dist/mermaid.core.mjs");
}

function isChunk(id: string): boolean {
  return id.replace(/\\/g, "/").includes("/mermaid/dist/chunks/");
}

/** Where `loader<suffix>`'s lazy import sits, relative to `code`, or null when it has none. */
function loaderImport(code: string, suffix: string): { start: number; end: number } | null {
  const declared = code.indexOf(`var loader${suffix} = `);
  if (declared < 0) return null;
  // The body is a two-line arrow function. A window, because the first lazy import AFTER it
  // in the file belongs to the next diagram, and taking that one would drop the wrong type.
  const found = LAZY_IMPORT.exec(code.slice(declared, declared + 500));
  return found ? { start: declared + found.index, end: declared + found.index + found[0].length } : null;
}

/** Every lazily loaded diagram of the entry, in the order it declares them. */
function lazyLoaders(code: string): Loader[] {
  const out: Loader[] = [];
  for (const match of code.matchAll(ID)) {
    const [, suffix, ident] = match;
    const where = loaderImport(code.slice(match.index), suffix);
    if (where) out.push({ ident, start: match.index + where.start, end: match.index + where.end });
  }
  return out;
}

/** The entry with the `import()` of every diagram outside `keep` replaced by a rejection. */
function withoutUnreachableDiagrams(code: string, keep: Set<string>): { code: string; dropped: Loader[]; total: number } {
  const lazy = lazyLoaders(code);
  if (lazy.length < MIN_REGISTERED) {
    throw new Error(
      `mermaid-subset: found ${lazy.length} lazy diagram loaders in mermaid.core.mjs, expected ` +
        `at least ${MIN_REGISTERED}. Mermaid's registry changed shape — read vite/mermaid-subset.ts.`,
    );
  }

  const registered = new Set(lazy.map(({ ident }) => ident));
  const unknown = [...keep].filter((ident) => !registered.has(ident));
  if (unknown.length) {
    throw new Error(
      `mermaid-subset: lib/diagram.ts names diagram type(s) mermaid does not register: ` +
        `${unknown.join(", ")}. Mermaid renamed or removed them.`,
    );
  }

  const dropped = lazy.filter(({ ident }) => !keep.has(ident));
  let out = code;
  // From the end of the file backwards, so every earlier offset stays valid.
  for (const { ident, start, end } of [...dropped].reverse()) {
    const reason = JSON.stringify(`mermaid: diagrams of type «${ident}» are not bundled in this app`);
    out = `${out.slice(0, start)}Promise.reject(new Error(${reason}))${out.slice(end)}`;
  }
  return { code: out, dropped, total: lazy.length };
}

/** The end of the array literal opening at `open`, by counting brackets. */
function arrayEnd(code: string, open: number): number {
  let depth = 0;
  for (let at = open; at < code.length; at += 1) {
    if (code[at] === "[") depth += 1;
    else if (code[at] === "]" && (depth -= 1) === 0) return at;
  }
  return -1;
}

/** The layout-engine chunk with every engine but dagre unregistered. */
function withoutOtherLayouts(code: string): string {
  const times = code.split(LAYOUT_CALL).length - 1;
  const call = code.indexOf(LAYOUT_CALL);
  const open = call + LAYOUT_CALL.length - 1;
  const close = call < 0 ? -1 : arrayEnd(code, open);
  const dagre = close < 0 ? null : DAGRE_ENTRY.exec(code.slice(open, close));
  if (times !== 1 || !dagre) {
    throw new Error(
      `mermaid-subset: expected one «${LAYOUT_CALL}» holding a dagre entry in the chunk that ` +
        `registers the layout engines; found ${times} call(s)${dagre ? "" : " and no dagre entry"}. ` +
        `Read vite/mermaid-subset.ts.`,
    );
  }
  return `${code.slice(0, open + 1)}${dagre[0]}${code.slice(close)}`;
}

export function mermaidSubset(): Plugin {
  const keep = new Set(DRAWN_DIAGRAMS);

  return {
    name: "variatio:mermaid-subset",
    apply: "build",

    buildStart() {
      // An entry that no longer resolves is a rename, and every transform below would then
      // quietly do nothing at all.
      createRequire(import.meta.url).resolve("mermaid");
    },

    transform(code, id) {
      if (isEntry(id)) {
        const { code: out, dropped, total } = withoutUnreachableDiagrams(code, keep);
        this.info(
          `left out ${dropped.length} of ${total} mermaid diagram types: ` +
            dropped.map(({ ident }) => ident).join(", "),
        );
        return { code: out, map: null };
      }
      if (isChunk(id) && code.includes("elkLayoutLoaders")) {
        this.info("left out every mermaid layout engine but dagre (elk, cose-bilkent, swimlane)");
        return { code: withoutOtherLayouts(code), map: null };
      }
      return null;
    },
  };
}
