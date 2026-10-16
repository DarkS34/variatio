#!/usr/bin/env node
// Whether the evaluation's and the tutor's client code stays out of what every session loads.
//
// Both are optional functions the administrator opens per account (`server/features.py`), and
// an account they are closed to must fetch no module of `src/consumers/evaluation/` or
// `src/consumers/tutor/`. The
// app keeps that by importing them only through `import()` behind the account's `features`;
// one static import from core undoes it silently — the page works, it only ships code nobody
// asked for. Two rules, because each misses what the other sees:
//
//   - THE SOURCES: no file outside the two folders imports into them statically. `import type`
//     and `export type` are erased before bundling, and a dynamic `import()` is the point.
//   - THE BUNDLE: the static import closure of the entry chunk — what a browser fetches before
//     any decision — holds no module of the two folders, and neither does the closure of any
//     screen of the product loaded on demand (a dynamic entry whose module is outside them),
//     since every account opens those. Read from `dist/.vite/chunks.json`, which
//     `vite/chunk-graph.ts` writes on every `pnpm build`. The source rule cannot see a chunk
//     Rollup merges or hoists; this one sees only what the build actually did.
import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, relative, resolve } from "node:path";

import { BARE, SELF_TESTS, SRC, STATIC, blankComments, fromSrc, target, walk } from "./imports.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB = resolve(HERE, "..");
const GRAPH = resolve(WEB, "dist", ".vite", "chunks.json");

/** The folders whose code reaches a browser only when the function is open, relative to `src/`. */
// The landing is not an optional function, and it is listed for the same reason: a public
// page with a demo of the whole client, fetched by a visitor at `/` and by nobody
// who logs in.
const LAZY = ["consumers/evaluation", "consumers/tutor", "landing"];

// The folders named in a report, every one a negative: `src/consumers/evaluation/, … ni
// src/landing/`.
const NAMED = `${LAZY.slice(0, -1).map((folder) => `src/${folder}/`).join(", ")} ni src/${LAZY.at(-1)}/`;

const inLazy = (pathFromSrc) =>
  LAZY.some((folder) => pathFromSrc === folder || pathFromSrc.startsWith(`${folder}/`));

let failures = 0;

function report(ok, name, lines = []) {
  if (ok) {
    console.log(`ok     ${name}`);
    return;
  }
  failures++;
  console.log(`FALLA  ${name}`);
  for (const line of lines) console.log(`         ${line}`);
}

// 0. The scanner ----------------------------------------------------------------------------

const misread = SELF_TESTS.filter(
  ([source, seen]) => [...blankComments(source).matchAll(STATIC)].length > 0 !== seen,
);
report(
  misread.length === 0,
  `El quitacomentarios lee bien sus ${SELF_TESTS.length} casos (cadenas, plantillas, regex, JSX)`,
  misread.map(([source, seen]) => `${seen ? "oculta" : "no quita"}: ${JSON.stringify(source)}`),
);

// 1. The sources -----------------------------------------------------------------------------

const imports = [];
for (const full of walk(SRC)) {
  const path = fromSrc(full);
  if (inLazy(path)) continue;
  // Comments blanked first, keeping every newline so the line numbers stay exact: a comment
  // quoting an import is not one.
  const code = blankComments(readFileSync(full, "utf8"));
  const line = (index) => code.slice(0, index).split("\n").length;

  for (const match of code.matchAll(STATIC)) {
    if (match[2]) continue;
    const into = target(full, match[5]);
    if (into !== null && inLazy(into)) {
      imports.push(`${path}:${line(match.index)}  ${match[1]} … from "${match[5]}"`);
    }
  }
  for (const match of code.matchAll(BARE)) {
    const into = target(full, match[2]);
    if (into !== null && inLazy(into)) imports.push(`${path}:${line(match.index)}  import "${match[2]}"`);
  }
}

report(
  imports.length === 0,
  `Ningún import estático de ${NAMED} fuera de sus carpetas`,
  [
    ...imports,
    ...(imports.length
      ? ["Cárgalo con import() detrás de useFeatures(), o lleva lo compartido a una carpeta común."]
      : []),
  ],
);

// 2. The bundle ------------------------------------------------------------------------------

if (!existsSync(GRAPH)) {
  report(false, "El grafo de chunks del bundle existe", [
    `No está ${relative(WEB, GRAPH)}: ejecuta pnpm build primero.`,
  ]);
} else {
  const { chunks } = JSON.parse(readFileSync(GRAPH, "utf8"));
  const byFile = new Map(chunks.map((chunk) => [chunk.fileName, chunk]));
  const entries = chunks.filter((chunk) => chunk.isEntry);
  const lazyModule = (id) => id.startsWith("src/") && inLazy(id.slice("src/".length));

  // What a browser fetches with these chunks: them and, transitively, every chunk they
  // import statically. `dynamicImports` are left alone, which is the whole point.
  const closure = (files) => {
    const loaded = new Set();
    const queue = [...files];
    while (queue.length) {
      const file = queue.pop();
      if (loaded.has(file) || !byFile.has(file)) continue;
      loaded.add(file);
      queue.push(...byFile.get(file).imports);
    }
    return loaded;
  };
  const leaks = (loaded) =>
    [...loaded].flatMap((file) =>
      byFile
        .get(file)
        .moduleIds.filter(lazyModule)
        .map((id) => `${id}  (en ${file})`),
    );

  const loaded = closure(entries.map((chunk) => chunk.fileName));
  const leaked = leaks(loaded);

  // The product's own screens loaded on demand — every route and the panel's
  // tabs — open for every account, so what they fetch with them is fetched by everybody. A
  // chunk is one when an `import()` names a module of it outside the two folders.
  const screens = chunks.flatMap((chunk) =>
    (chunk.dynamicEntries ?? [])
      .filter((id) => id.startsWith("src/") && !lazyModule(id))
      .map((id) => ({ id, file: chunk.fileName })),
  );
  // What the entry already loads is the rule above's, and is not reported twice.
  const screenLeaks = screens.flatMap(({ id, file }) =>
    leaks([...closure([file])].filter((chunk) => !loaded.has(chunk))).map(
      (line) => `${id} → ${line}`,
    ),
  );
  // A graph that lists no module of the two folders at all measures nothing: a renamed
  // folder or a plugin that stopped recording would pass this rule for ever.
  const everywhere = chunks.flatMap((chunk) => chunk.moduleIds).filter(lazyModule).length;

  report(entries.length > 0 && everywhere > 0, "El grafo de chunks del bundle mide algo", [
    entries.length === 0
      ? `${relative(WEB, GRAPH)} no tiene ningún chunk de entrada.`
      : `${relative(WEB, GRAPH)} no lista ningún módulo de ${NAMED}.`,
    "Vuelve a ejecutar pnpm build, y si sigue, lee vite/chunk-graph.ts.",
  ]);
  report(
    leaked.length === 0,
    `Lo que carga toda sesión (${loaded.size} chunk(s) estáticos) no contiene ${NAMED}`,
    leaked,
  );
  report(
    screenLeaks.length === 0,
    `Ninguna de las ${screens.length} pantallas del producto cargadas a demanda arrastra ${NAMED}`,
    screenLeaks,
  );
}

console.log(failures === 0 ? "\nTodo pasa.\n" : `\n${failures} regla(s) fallan.\n`);
process.exit(failures === 0 ? 0 : 1);
