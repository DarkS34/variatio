// The import reader the client's checks share (`check-lazy.mjs`, `check-layers.mjs`).
//
// It finds every static import and re-export of a source file with its comments blanked
// first, by a scanner that knows strings, templates, regex literals and JSX text, and it
// checks itself on every run (`SELF_TESTS`): a reader that misread a string would hide an
// import for ever, and nothing else would notice.
import { readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, relative, resolve, sep } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
export const SRC = resolve(HERE, "..", "src");

export function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = resolve(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

export const fromSrc = (full) => relative(SRC, full).split(sep).join("/");

// A static import or re-export, over as many lines as its braces take: `import`/`export`
// at the start of a line, NOT followed by `(` — that is `import()` — and a `from "…"` before
// any semicolon or quote. The class excluding `;`, quotes and backticks is what keeps a match
// from running across code: an `export function` reaches one long before any `from`.
export const STATIC = /^[ \t]*(import|export)\b(?!\s*\()(\s+type\b)?([^;'"`]*?)\bfrom\s*(["'])([^"']+)\4/gm;
// `import "…";`, for its side effects alone.
export const BARE = /^[ \t]*import\s*(["'])([^"']+)\1/gm;

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
export function blankComments(source) {
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
export const SELF_TESTS = [
  ['const glob = "src/*";\nimport { X } from "@/consumers/tutor/X";\nconst end = "*/";', true],
  ["const s = 'a/*b';\nimport { X } from \"@/consumers/tutor/X\";\nconst t = '*/';", true],
  ["const t = `a ${'/*'} b`;\nimport { X } from \"@/consumers/tutor/X\";\nconst u = `*/`;", true],
  [
    "const r = text.replace(/\\/\\*/g, '');\nimport { X } from \"@/consumers/tutor/X\";\n// */",
    true,
  ],
  ["const r = /[/*]/;\nimport { X } from \"@/consumers/tutor/X\";\nconst k = 1; /* */", true],
  ["<p>don't /* here</p>\nimport { X } from \"@/consumers/tutor/X\";\n<p>*/</p>", true],
  ["<p>don't won't /* x</p>\nimport { X } from \"@/consumers/tutor/X\";\n<p>*/</p>", true],
  ["<div>\n  {/*\nimport { X } from \"@/consumers/tutor/X\";\n  */}\n</div>", false],
  ["const half = a / b; /* import { X } from \"@/consumers/tutor/X\"; */", false],
  ["/*\nimport { X } from \"@/consumers/tutor/X\";\n*/", false],
  ['// import { X } from "@/consumers/tutor/X";', false],
  ['const url = "http://x"; // import { X } from "@/consumers/tutor/X";', false],
];

/** Where a specifier lands, relative to `src/`, or null for a package. */
export function target(file, specifier) {
  if (specifier.startsWith("@/")) return specifier.slice(2);
  if (specifier.startsWith(".")) return fromSrc(resolve(dirname(file), specifier));
  return null;
}
