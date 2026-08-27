#!/usr/bin/env node
// Whether the interface can actually be read in two languages.
//
// The type system already covers half of it: `en.ts` is typed against `es.ts`, so a key
// that exists in one and not the other is a build error and there is no such thing as a
// missing translation. What a type cannot see is a sentence that never became a key at
// all — a literal sitting in the JSX, which renders in Spanish whatever the account says.
//
// So this measures ONE thing: user-visible text that is not going through `t()`. The
// `exempt` list is the mechanism of the migration and not an excuse — a screen task starts
// by deleting its file from the list so the script goes red, and it is done when the
// script goes green again.
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, resolve, relative, sep } from "node:path";

const HERE = dirname(fileURLToPath(import.meta.url));
const SRC = resolve(HERE, "..", "src");

function walk(dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = resolve(dir, entry);
    if (statSync(full).isDirectory()) out.push(...walk(full));
    else if (/\.tsx?$/.test(entry)) out.push(full);
  }
  return out;
}

// Spanish is what the app is written in today, so its own orthography is the cheapest and
// most precise detector there is: a literal carrying an accent, an ñ, an inverted mark or
// an angular quote is prose somebody typed, never an identifier and never a class name.
const SPANISH = /[áéíóúüñÁÉÍÓÚÜÑ¿¡«»]/;

// Orthography alone has a blind spot, and `lib/status.ts` is what found it: «Sin
// construir», «Aprobado», «Borrador» carry no accent at all, so a file could pass the gate
// while every label in it was Spanish. These are the function words that cannot appear in
// an identifier, a class name or a route.
const SPANISH_WORDS =
  /\b(?:de|el|la|los|las|un|una|unos|unas|del|que|mi|mis|tu|tus|te|me|nos|muy|más|donde|dónde|quien|quién|nuevo|nueva|otro|otros|otras|y|en|con|por|para|se|su|sus|es|son|no|sin|como|cuando|porque|pero|si|lo|al|ya|hay|cada|todo|toda|todos|todas|este|esta|esto|ese|esa|otro|otra|sobre|entre|hasta|desde|solo|antes|puede|debe|hace|tiene|ser|estar|hacer|nada|algo|aun|ni|ha|han|vez|veces)\b/i;

// A key, a route and a `data-*` value can all carry an accent legitimately. What cannot is
// a sentence: two or more words with a space between them.
const SENTENCE = /\S+\s+\S+/;

// A Tailwind class list is a space-separated sentence made of words, and `divide-y` ends
// in a `y` that the word test reads as the Spanish conjunction. Rather than teach the word
// test about hyphens — which would lose «Sin construir» — a candidate whose every token
// looks like a utility class is not prose.
// The bracket form carries commas and `var(--x)`, so the tail accepts them: without it
// `bg-[color-mix(in_oklch,var(--destructive)_12%,transparent)]` reads as prose.
const CLASS_TOKEN = /^-?[a-z0-9]+(?:[:/[\]().%,-][a-zA-Z0-9.%_,[\]()/-]*)*$/;
// Every token has to look like one AND at least one has to carry the punctuation only a
// utility class has. Without the second half «en disco» reads as a class list, because two
// bare lowercase words satisfy the first — a false negative on a real wire value.
const looksLikeClasses = (value) => {
  const tokens = value.split(/\s+/).filter(Boolean);
  return tokens.every((token) => CLASS_TOKEN.test(token)) && tokens.some((t) => /[:/[-]/.test(t));
};

// The third rule, and the one that catches a single Spanish word with no accent in a data
// table: a property whose whole job is to be read by a person. `label: "Aprobado"` is
// invisible to both tests above and is exactly the shape `lib/status.ts` is made of.
const TEXT_PROPERTY =
  /\b(?:label|title|description|hint|placeholder|purpose|question|what|produces|cost|reason|summary|kind)\s*[:=]\s*(?:\{\s*)?["'`]([^"'`\n]{2,300})["'`]/g;

// What such a property may legitimately hold: a key of the catalogue, a token, a path — or
// a template that BUILDS a key, which is how `lib/explain.ts` derives 32 of them from one
// list of step ids rather than writing the same names out twice.
const TECHNICAL = /^(?:[a-z0-9_.:/-][a-zA-Z0-9_.:/-]*|[A-Z0-9_]+|--[a-z-]+|[a-z0-9_.]*\$\{\w+\}[a-z0-9_.]*)$/;

const STRING = /"([^"\\\n]{2,400})"|'([^'\\\n]{2,400})'|`([^`\\\n]{2,400})`/g;
const JSX_TEXT = />\s*([^<>{}\n][^<>{}]{2,400}?)\s*</g;

// The same JSX text, wherever prettier happened to break the line. Matching per line was
// blind three ways at once: a paragraph wrapped across lines, a sentence ENDING at an
// interpolation (`Ver los {n} sin concepto`), and one STARTING after a `}` on the same
// line (`{rows.length} concepto(s)`). One rule covers all three — a text node is what sits
// between a `>` or `}` and the next `<` or `{` — and the characters prose does not carry
// are what keep code out: an `=`, a quote or a backtick inside means this is an expression.
// A `;` does NOT: Spanish prose uses it, and excluding it hid three stage descriptions.
const JSX_BLOCK = /(?<![=-])[>}]([^<>{}='"`]{3,800}?)[<{]/g;

// The last blind spot, and the one that survives both tests above: a JSX text node holding
// ONE word. «Usuario», «Nombre», «Entrar», «Guardar» carry no accent and are not a
// sentence, so neither the orthography nor the two-word rule sees them — and a label is
// exactly where a single word lives. Everything alphabetic is suspect; the allow-list is
// the technical vocabulary that reads the same in both languages.
// The closing boundary is any `<`, not `</`: «Resultados» sat in front of a `<span>` and
// so escaped both this rule and the two-word floor above it.
const LONE_WORD = /(?<![=-])[>}]\s*([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,20})\s*</g;
const TECHNICAL_WORDS = new Set([
  "JSON", "Markdown", "Cerebras", "Ollama", "GPU", "CPU", "API", "URL", "CSV", "SSH", "VRAM",
  "Python", "Docling", "Postgres", "SQL", "HTML", "PDF", "few", "shot", "prompt", "prompts",
  "Variatio",
  "token", "tokens", "workspace", "workspaces", "kNN", "RAG", "npz", "docx", "pdf", "md",
  // A `}` closing a block, a newline, and `return <Something />` is code and reads as a
  // one-word text node. These are the keywords that can legally sit in that position.
  "return", "default", "case", "else", "new", "void", "null", "true", "false", "await",
]);

// The migration's remaining surface. Every one of these still speaks Spanish directly, and
// each is one task: delete the line, make the screen go through `t()`, watch it go green.
const EXEMPT = new Set([
  // The one file that must NOT go through `t()`. It is the boundary that catches a render
  // crash, and the i18n layer is one of the things that can crash: a translated boundary
  // would fall with what it exists to catch, leaving a blank page instead of a message.
  "components/ErrorBoundary.tsx",
]);

// The last tree still to migrate, listed as a prefix so a new file inside it does not make
// the gate go red before its screen has been touched at all.
const EXEMPT_TREES = [
  "features/guide/",
];

const exempt = (path) =>
  EXEMPT.has(path) || EXEMPT_TREES.some((prefix) => path.startsWith(prefix));

const findings = [];

for (const full of walk(SRC)) {
  const path = relative(SRC, full).split(sep).join("/");
  if (path.endsWith(".test.ts") || path.endsWith(".test.tsx")) continue;
  // The catalogue is where the Spanish lives, by definition.
  if (path.startsWith("lib/i18n/")) continue;
  if (exempt(path)) continue;

  const text = readFileSync(full, "utf8");
  // A block scan reads a comment as prose, and this repository's comments are long. The
  // per-line pass already skips them; blanking them here keeps the line numbers exact.
  const code = text
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "))
    .replace(/^(\s*)\/\/.*$/gm, (m) => m.replace(/[^\n]/g, " "));
  // A line marked `i18n-exempt` carries a protocol token, not copy: a string the server
  // also knows, matched against rather than read. Translating one breaks the match.

  text.split("\n").forEach((line, index) => {
    const trimmed = line.trim();
    if (trimmed.startsWith("//") || trimmed.startsWith("*") || trimmed.startsWith("/*")) return;
    if (line.includes("i18n-exempt")) return;

    const candidates = [];
    for (const match of line.matchAll(STRING)) {
      candidates.push(match[1] ?? match[2] ?? match[3]);
    }
    for (const match of line.matchAll(JSX_TEXT)) candidates.push(match[1]);

    for (const candidate of candidates) {
      const prose = SPANISH.test(candidate) || SPANISH_WORDS.test(candidate);
      if (!prose || !SENTENCE.test(candidate) || looksLikeClasses(candidate)) continue;
      findings.push(`${path}:${index + 1}  ${candidate.trim().slice(0, 90)}`);
      return;
    }

    for (const match of line.matchAll(TEXT_PROPERTY)) {
      const value = match[1].trim();
      if (!value || TECHNICAL.test(value)) continue;
      // `t("…")` and `t(SOME_KEY)` already went through the catalogue.
      if (/\bt\(/.test(line)) continue;
      findings.push(`${path}:${index + 1}  ${match[0].trim().slice(0, 90)}`);
    }
  });

  // A JSX text node only exists in a `.tsx` file; in a `.ts` one these two rules read type
  // parameters as prose.
  if (!path.endsWith(".tsx")) continue;

  for (const match of code.matchAll(LONE_WORD)) {
    const word = match[1];
    if (TECHNICAL_WORDS.has(word)) continue;
    const line = code.slice(0, match.index).split("\n").length;
    findings.push(`${path}:${line}  ${word}`);
  }

  for (const match of code.matchAll(JSX_BLOCK)) {
    const value = match[1].replace(/\s+/g, " ").trim();
    // Two words, not four: «Solo sin descripción» is three and shipped in Spanish through a
    // green gate. One word is LONE_WORD's job, and it has an allow-list this rule cannot use.
    if (value.split(/\s+/).length < 2) continue;
    if (!SPANISH.test(value) && !SPANISH_WORDS.test(value)) continue;
    if (looksLikeClasses(value)) continue;
    const line = code.slice(0, match.index).split("\n").length;
    findings.push(`${path}:${line}  ${value.slice(0, 90)}`);
  }
}

const migrated = walk(SRC)
  .map((full) => relative(SRC, full).split(sep).join("/"))
  .filter((path) => !exempt(path) && !path.startsWith("lib/i18n/")).length;

if (findings.length) {
  console.error(`✗ ${findings.length} texto(s) de interfaz fuera del catálogo:\n`);
  for (const finding of findings) console.error(`  ${finding}`);
  console.error(
    `\nCada uno es una cadena que se pintará en español haga lo que haga la cuenta.\n` +
      `Muévela a src/lib/i18n/es.ts y tradúcela en en.ts.`,
  );
  process.exit(1);
}

console.log(
  `✓ ${migrated} fichero(s) migrado(s) sin texto suelto; ` +
    `${EXEMPT.size + EXEMPT_TREES.length} entrada(s) todavía en la lista de pendientes.`,
);
