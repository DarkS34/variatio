#!/usr/bin/env node
// Whether the evaluation's and the tutor's client code stays out of what every session loads.
//
// Both are optional functions the administrator opens per account (`server/features.py`), and
// an account they are closed to must fetch no module of `src/evaluation/` or `src/tutor/`. The
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
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, relative, resolve, sep } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB = resolve(HERE, "..");
const SRC = resolve(WEB, "src");
const GRAPH = resolve(WEB, "dist", ".vite", "chunks.json");

/** The folders whose code reaches a browser only when the function is open, relative to `src/`. */
const LAZY = ["evaluation", "tutor"];

const inLazy = (pathFromSrc) =>
  LAZY.some((folder) => pathFromSrc === folder || pathFromSrc.startsWith(`${folder}/`));

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = resolve(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

const fromSrc = (full) => relative(SRC, full).split(sep).join("/");

// A static import or re-export, over as many lines as its braces take: `import`/`export`
// at the start of a line, NOT followed by `(` — that is `import()` — and a `from "…"` before
// any semicolon or quote. The class excluding `;`, quotes and backticks is what keeps a match
// from running across code: an `export function` reaches one long before any `from`.
const STATIC = /^[ \t]*(import|export)\b(?!\s*\()(\s+type\b)?([^;'"`]*?)\bfrom\s*(["'])([^"']+)\4/gm;
// `import "…";`, for its side effects alone.
const BARE = /^[ \t]*import\s*(["'])([^"']+)\1/gm;

/**
 * The source with every comment blanked to spaces, newlines kept.
 *
 * A scanner and not two regexes, because a comment marker means one only in code: a `/*`
 * inside a string, a template or a regex literal blanked everything up to the next `*\/`,
 * and a static import in between went unseen. Strings and templates are walked whole (a
 * template's `${…}` back in code), a regex literal is told from a division by what precedes
 * the slash, and a quote or a regex left open at the end of a line closes there — JSX text
 * («don't») is no string, and treating it as one must not swallow the next line. A block
 * comment that runs past its line is blanked whole only when its `/*` opens the line or a
 * JSX `{/*`: two apostrophes of JSX text read as a string can leave a `/*` of that text
 * looking like code, and only a comment past its line can hide an import, which must open
 * a line. Anywhere else such a comment is blanked to its line's end. When the scanner is
 * wrong it is wrong towards leaving text in: a comment kept is at worst an import reported,
 * never one hidden.
 */
function blankComments(source) {
  const out = source.split("");
  const blank = (from, to) => {
    for (let i = from; i < to; i++) if (out[i] !== "\n") out[i] = " ";
  };
  // After one of these, a slash starts a regex literal; after anything else, it divides.
  const BEFORE_REGEX = /[(,=:[!&|?{};+\-*%~^<>]$|(?:^|[^\w$])(?:return|typeof|case|in|of|delete|void|new|throw|yield|await|else|do)$/;
  // One `{` depth per `${` open in a template, so its `}` goes back to the template.
  const templates = [];
  let i = 0;
  let last = 0; // index just past the last character of code that was not blank

  while (i < source.length) {
    const c = source[i];
    const next = source[i + 1];

    if (c === "/" && next === "/") {
      const end = source.indexOf("\n", i);
      const stop = end < 0 ? source.length : end;
      blank(i, stop);
      i = stop;
      continue;
    }
    if (c === "/" && next === "*") {
      const end = source.indexOf("*/", i + 2);
      const stop = end < 0 ? source.length : end + 2;
      const lineEnd = source.indexOf("\n", i);
      const opensLine = /^[ \t]*\{?$/.test(source.slice(source.lastIndexOf("\n", i - 1) + 1, i));
      blank(i, lineEnd < 0 || stop <= lineEnd || opensLine ? stop : lineEnd);
      i = stop;
      continue;
    }
    if (c === "'" || c === '"') {
      i = skipQuoted(source, i, c);
      last = i;
      continue;
    }
    if (c === "`") {
      i = skipTemplate(source, i + 1, templates);
      last = i;
      continue;
    }
    if (c === "{" && templates.length) {
      templates[templates.length - 1]++;
    } else if (c === "}" && templates.length) {
      if (templates[templates.length - 1] === 0) {
        templates.pop();
        i = skipTemplate(source, i + 1, templates);
        last = i;
        continue;
      }
      templates[templates.length - 1]--;
    } else if (c === "/" && BEFORE_REGEX.test(source.slice(Math.max(0, last - 8), last).trimEnd() || "(")) {
      i = skipRegex(source, i);
      last = i;
      continue;
    }
    i++;
    if (!/\s/.test(c)) last = i;
  }
  return out.join("");
}

/** The index just past a quoted string opened at `start`, or its line's end if left open. */
function skipQuoted(source, start, quote) {
  for (let i = start + 1; i < source.length; i++) {
    if (source[i] === "\\") i++;
    else if (source[i] === quote) return i + 1;
    else if (source[i] === "\n") return i;
  }
  return source.length;
}

/**
 * The index just past a template's text from `start`: past its closing backtick, or past a
 * `${`, whose depth is pushed so the scanner returns here at its `}`.
 */
function skipTemplate(source, start, templates) {
  for (let i = start; i < source.length; i++) {
    if (source[i] === "\\") i++;
    else if (source[i] === "`") return i + 1;
    else if (source[i] === "$" && source[i + 1] === "{") {
      templates.push(0);
      return i + 2;
    }
  }
  return source.length;
}

/** The index just past a regex literal opened at `start`, or its line's end if left open. */
function skipRegex(source, start) {
  let inClass = false;
  for (let i = start + 1; i < source.length; i++) {
    const c = source[i];
    if (c === "\\") i++;
    else if (c === "\n") return i;
    else if (c === "[") inClass = true;
    else if (c === "]") inClass = false;
    else if (c === "/" && !inClass) {
      let end = i + 1;
      while (/[a-z]/i.test(source[end] ?? "")) end++;
      return end;
    }
  }
  return source.length;
}

// What the scanner must get right, checked on every run: a check that hides an import
// because it misread a string passes for ever, and nothing else would notice.
const SELF_TESTS = [
  ['const glob = "src/*";\nimport { X } from "@/tutor/X";\nconst end = "*/";', true],
  ["const s = 'a/*b';\nimport { X } from \"@/tutor/X\";\nconst t = '*/';", true],
  ["const t = `a ${'/*'} b`;\nimport { X } from \"@/tutor/X\";\nconst u = `*/`;", true],
  ["const r = text.replace(/\\/\\*/g, '');\nimport { X } from \"@/tutor/X\";\n// */", true],
  ["const r = /[/*]/;\nimport { X } from \"@/tutor/X\";\nconst k = 1; /* */", true],
  ["<p>don't /* here</p>\nimport { X } from \"@/tutor/X\";\n<p>*/</p>", true],
  ["<p>don't won't /* x</p>\nimport { X } from \"@/tutor/X\";\n<p>*/</p>", true],
  ["<div>\n  {/*\nimport { X } from \"@/tutor/X\";\n  */}\n</div>", false],
  ["const half = a / b; /* import { X } from \"@/tutor/X\"; */", false],
  ["/*\nimport { X } from \"@/tutor/X\";\n*/", false],
  ['// import { X } from "@/tutor/X";', false],
  ['const url = "http://x"; // import { X } from "@/tutor/X";', false],
];

/** Where a specifier lands, relative to `src/`, or null for a package. */
function target(file, specifier) {
  if (specifier.startsWith("@/")) return specifier.slice(2);
  if (specifier.startsWith(".")) return fromSrc(resolve(dirname(file), specifier));
  return null;
}

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
  "Ningún import estático de src/evaluation/ ni de src/tutor/ fuera de sus carpetas",
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

  // The product's own screens loaded on demand — every route, the guide's trees, the panel's
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
      : `${relative(WEB, GRAPH)} no lista ningún módulo de src/evaluation/ ni de src/tutor/.`,
    "Vuelve a ejecutar pnpm build, y si sigue, lee vite/chunk-graph.ts.",
  ]);
  report(
    leaked.length === 0,
    `Lo que carga toda sesión (${loaded.size} chunk(s) estáticos) no contiene src/evaluation/ ni src/tutor/`,
    leaked,
  );
  report(
    screenLeaks.length === 0,
    `Ninguna de las ${screens.length} pantallas del producto cargadas a demanda arrastra src/evaluation/ ni src/tutor/`,
    screenLeaks,
  );
}

console.log(failures === 0 ? "\nTodo pasa.\n" : `\n${failures} regla(s) fallan.\n`);
process.exit(failures === 0 ? 0 : 1);
