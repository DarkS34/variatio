#!/usr/bin/env node
// Whether the interface can actually be read in two languages.
//
// The type system already covers half of it: `en.ts` is typed against `es.ts`, so a key
// that exists in one and not the other is a build error and there is no such thing as a
// missing translation. What a type cannot see is a sentence that never became a key at
// all — a literal sitting in the JSX, which renders in Spanish whatever the account says.
//
// So this measures ONE thing: user-visible text that is not going through `t()`. The
// `exempt` list WAS the mechanism of the migration — a screen task started by deleting its
// file from the list so the script went red, and it was done when the script went green
// again. The migration is over, and the three entries left are not leftovers: each is a
// file that must NOT go through the catalogue, and says why in its own comment.
//
// It also checks the two things the guide puts beyond a text scan: that its two prose trees
// answer for the same set of sections, and that every section the registry ANNOUNCES has a
// body somewhere. The second is not a refinement of the first — two trees that agree on not
// having a section satisfy it perfectly, which is how a blank page shipped green.
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

// A phrase that LOOKS like prose whatever language it is in: it opens with a capital and
// every word is alphabetic. It is the third test `JSX_BLOCK` applies, and it exists
// because a Spanish phrase of two content words — «Guardar cambios» — carries neither an
// accent nor a function word, so the two tests above are both blind to it.
//
// The capital is doing the work: identifiers, routes and wire values are lower-case or
// SCREAMING_CASE, and a sentence a person reads starts with a capital in both languages.
// Requiring every word to be alphabetic keeps out anything with a number, a dot or a
// bracket in it, which is where rendered data lives.
const PROSE_SHAPE = /^[A-ZÁÉÍÓÚÜÑ][a-záéíóúüñ]+(?:\s+[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+)+$/;

// What `PROSE_SHAPE` would otherwise flag: product and technology names that read the
// same in both catalogues, so translating them would be wrong rather than missing.
const TECHNICAL_PHRASES = new Set([
  "Claude Code",
  "Hugging Face",
  "Think Python",
]);

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
// so escaped both this rule and the two-word floor above it. It is also any `{`, because
// «Página {page.index}» is a text node that ENDS at the interpolation — one word before a
// `{` is neither a sentence for `JSX_BLOCK` nor a `<` for this rule, and it shipped.
const LONE_WORD = /(?<![=-])[>}]\s*([A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,20})\s*[<{]/g;
const TECHNICAL_WORDS = new Set([
  "JSON", "Markdown", "Cerebras", "Ollama", "GPU", "CPU", "API", "URL", "CSV", "SSH", "VRAM",
  "Python", "Docling", "Postgres", "SQL", "HTML", "PDF", "few", "shot", "prompt", "prompts",
  "Variatio",
  "token", "tokens", "workspace", "workspaces", "kNN", "RAG", "npz", "docx", "pdf", "md",
  // A `}` closing a block, a newline, and `return <Something />` is code and reads as a
  // one-word text node. These are the keywords that can legally sit in that position —
  // the second row is what a `}` followed by `{` produces once the rule above accepts an
  // interpolation as a closing boundary.
  "return", "default", "case", "else", "new", "void", "null", "true", "false", "await",
  "try", "catch", "finally", "do", "while", "switch", "export", "const", "let", "var",
  "function", "class", "interface", "type", "enum", "import", "from", "extends", "async",
  "static", "get", "set", "throw", "delete", "typeof", "instanceof", "this", "super",
]);

// The migration's remaining surface. Every one of these still speaks Spanish directly, and
// each is one task: delete the line, make the screen go through `t()`, watch it go green.
const EXEMPT = new Set([
  // The one file that must NOT go through `t()`. It is the boundary that catches a render
  // crash, and the i18n layer is one of the things that can crash: a translated boundary
  // would fall with what it exists to catch, leaving a blank page instead of a message.
  "components/ErrorBoundary.tsx",
]);

// THE GUIDE'S BODIES ARE A TREE PER LANGUAGE, NOT A CATALOGUE ENTRY PER PARAGRAPH — see
// `features/guide/sections.tsx` for why. So `guide/es/` really is written in Spanish and
// `guide/en/` really is written in English, and both are correct: what makes that checkable
// is not this script but that `useGuideBody` picks one by the reader's language, and that
// `BODIES` in the two files has to hold the same slugs.
const EXEMPT_TREES = [
  "features/guide/es/",
  "features/guide/en/",
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
      // The two-word floor is what keeps a route and a `data-*` value out, and it does not
      // apply to a literal carrying Spanish ORTHOGRAPHY: «caché», «vacío», «Currículo»,
      // «Ejecución» are one word each and every one of them shipped as a label. An accent
      // in a quoted string is prose whatever its length.
      const floor = SPANISH.test(candidate) ? true : SENTENCE.test(candidate);
      if (!prose || !floor || looksLikeClasses(candidate)) continue;
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
    // THE THIRD BLIND SPOT, AND THE ONE THAT SHIPPED FOUR STRINGS (found 2026-08-31 with a
    // browser open on the built bundle). The two tests above are orthography OR a function
    // word from a closed list — and a Spanish phrase made of two CONTENT words carries
    // neither. «Guardar cambios», «Variantes guardadas» and «Volver a entrar» all passed a
    // green gate, the last one on the password-recovery screen.
    //
    // So a sentence that opens with a capitalised word is copy whatever it is made of. The
    // capital is what keeps identifiers and wire values out — those are lower-case or
    // SCREAMING — and `PROSE_SHAPE` additionally demands that every word be alphabetic,
    // which excludes «C001 Escribe…» style renderings of data.
    const prose = SPANISH.test(value) || SPANISH_WORDS.test(value) || PROSE_SHAPE.test(value);
    if (!prose) continue;
    if (looksLikeClasses(value)) continue;
    if (TECHNICAL_PHRASES.has(value)) continue;
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

// The guide is prose per language rather than keys, so nothing above can see it. What can
// be checked is that the two trees answer for the same sections: a section written in one
// and not the other renders nothing at all for half the readers.
const slugsOf = (file) =>
  new Set(
    [...readFileSync(resolve(SRC, file), "utf8").matchAll(/^\s{2}(\w+):\s*\w+,$/gm)].map(
      (match) => match[1],
    ),
  );
const esSlugs = slugsOf("features/guide/es/sections.tsx");
const enSlugs = slugsOf("features/guide/en/sections.tsx");
const onlyEs = [...esSlugs].filter((slug) => !enSlugs.has(slug));
const onlyEn = [...enSlugs].filter((slug) => !esSlugs.has(slug));

if (onlyEs.length || onlyEn.length) {
  console.error("✗ Las dos versiones de la guía no cubren las mismas secciones:\n");
  for (const slug of onlyEs) console.error(`  ${slug} — solo en es/`);
  for (const slug of onlyEn) console.error(`  ${slug} — solo en en/`);
  process.exit(1);
}

// COMPARAR LOS DOS ÁRBOLES ENTRE SÍ NO BASTA, Y ESTE ES EL AGUJERO POR EL QUE SE COLÓ UNA
// PÁGINA EN BLANCO EN PRODUCCIÓN. `GUIDE_SECTIONS` es lo que dibuja el índice, la búsqueda y
// el enlace «Siguiente», y una entrada suya sin cuerpo en NINGUNO de los dos árboles pasaba
// la comprobación de arriba sin despeinarse: los dos árboles coincidían perfectamente en no
// tenerla. El resultado es una entrada de navegación que existe, un `GuideLink` que apunta a
// ella, y una ruta que renderiza `null` — que es exactamente lo que este proyecto se niega a
// hacer en cualquier otra pantalla.
//
// El registro es la fuente: el cuerpo se busca a partir de él y no al revés.
const registrySlugs = [
  ...readFileSync(resolve(SRC, "features/guide/sections.tsx"), "utf8").matchAll(
    /\bslug:\s*"([\w-]+)"/g,
  ),
].map((match) => match[1]);
const bodyless = registrySlugs.filter((slug) => !esSlugs.has(slug) && !enSlugs.has(slug));

if (bodyless.length) {
  console.error("✗ La guía anuncia secciones que no tienen texto en ningún idioma:\n");
  for (const slug of bodyless) console.error(`  ${slug} — está en GUIDE_SECTIONS, no en BODIES`);
  console.error(
    `\nCada una es una entrada del índice que abre una página en blanco.\n` +
      `Escribe su componente en src/features/guide/es/sections.tsx y en en/sections.tsx,\n` +
      `y añádelo al mapa BODIES de los dos.`,
  );
  process.exit(1);
}

console.log(
  `✓ ${migrated} fichero(s) sin texto de interfaz fuera del catálogo; ` +
    `${esSlugs.size} secciones de guía en los dos idiomas, ` +
    `las ${registrySlugs.length} del registro con cuerpo; ` +
    `${EXEMPT.size + EXEMPT_TREES.length} exclusión(es) deliberada(s).`,
);
