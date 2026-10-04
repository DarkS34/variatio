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
// It also checks where each key may be read. The strings only an optional function reads
// live in that function's folder (`src/<function>/i18n/`) and arrive with its code, but the
// `Key` type is every catalogue's keys together, so `tsc` cannot see a tutor key read from
// core — where it renders as its own name until the tutor is loaded, whether written whole
// or built from a prefix. Nor can it see a key in a table typed `string`, which exists in no
// catalogue at all, or a module of a function loaded from core without registering that
// function's catalogue first.
//
// And the two things the guide puts beyond a text scan: that its two prose trees
// answer for the same set of sections, and that every section the registry ANNOUNCES has a
// body, in the file the registry reads it from. The second is not a refinement of the
// first — two trees that agree on not having a section satisfy it perfectly, which is how a
// blank page shipped green.
import { existsSync, readFileSync, readdirSync, statSync } from "node:fs";
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
// `BODIES` in the two languages has to hold the same slugs. The sections of an optional
// function live in that function's folder (`evaluation/guide/`, `tutor/guide/`), one file
// per language, so the guide fetches them only for an account the function is open to.
const EXEMPT_TREES = [
  "features/guide/es/",
  "features/guide/en/",
  "evaluation/guide/",
  "tutor/guide/",
];

const exempt = (path) =>
  EXEMPT.has(path) || EXEMPT_TREES.some((prefix) => path.startsWith(prefix));

// The core's catalogue and each optional function's: `lib/i18n/`, `evaluation/i18n/`,
// `tutor/i18n/`. Every file in them is the catalogue's own machinery or its strings.
const inCatalogue = (path) => /^(?:lib|[\w-]+)\/i18n\//.test(path);

const findings = [];

for (const full of walk(SRC)) {
  const path = relative(SRC, full).split(sep).join("/");
  if (path.endsWith(".test.ts") || path.endsWith(".test.tsx")) continue;
  // The catalogue is where the Spanish lives, by definition.
  if (inCatalogue(path)) continue;
  if (exempt(path)) continue;

  const text = readFileSync(full, "utf8");
  const code = text
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "))
    .replace(/^(\s*)\/\/.*$/gm, (m) => m.replace(/[^\n]/g, " "));
  // A line marked `i18n-exempt` carries a protocol token, not copy: a string the server
  // also knows, matched against rather than read. Translating one breaks the match.

  // EVERY pass reads `code` and never `text`: a comment quoting a label is not a label, and
  // the only reliable way to tell them apart is to blank the comments first. Skipping a line
  // that STARTS with a comment marker is not enough — the body of a `{/* … */}` block does
  // not, so a quoted sentence inside one was read as an untranslated string. The blanking
  // replaces every character but the newline, so the line numbers stay exact.
  code.split("\n").forEach((line, index) => {
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
  .filter((path) => !exempt(path) && !inCatalogue(path)).length;

if (findings.length) {
  console.error(`✗ ${findings.length} texto(s) de interfaz fuera del catálogo:\n`);
  for (const finding of findings) console.error(`  ${finding}`);
  console.error(
    `\nCada uno es una cadena que se pintará en español haga lo que haga la cuenta.\n` +
      `Muévela a src/lib/i18n/es.ts (o, si solo la lee una función opcional, a\n` +
      `src/<función>/i18n/es.ts) y tradúcela en el en.ts de al lado.`,
  );
  process.exit(1);
}

// WHERE EACH KEY MAY BE READ ---------------------------------------------------------------
//
// A catalogue is every `i18n/es.ts` under `src/`: `lib/i18n/` is the core's, and
// `<function>/i18n/` belongs to the function whose folder holds it. Its keys are read off
// the source the same way the catalogue writes them, one `"key":` per line.
const catalogues = walk(SRC)
  .map((full) => relative(SRC, full).split(sep).join("/"))
  .filter((path) => /(?:^|\/)i18n\/es\.ts$/.test(path))
  .map((path) => {
    const home = path.split("/")[0];
    return {
      path,
      feature: home === "lib" ? null : home,
      keys: [...readFileSync(resolve(SRC, path), "utf8").matchAll(/^ {2}"([^"]+)":/gm)].map(
        (match) => match[1],
      ),
    };
  });
const catalogueOf = new Map();
const twiceDeclared = [];
for (const catalogue of catalogues) {
  for (const key of catalogue.keys) {
    if (!catalogueOf.has(key)) catalogueOf.set(key, catalogue);
    else twiceDeclared.push(`${key} — en ${catalogueOf.get(key).path} y en ${catalogue.path}`);
  }
}
// The first segment of every key: `tutor`, `eval`, `admin`…
const namespaces = new Set([...catalogueOf.keys()].map((key) => key.split(".")[0]));

// Comments blanked first, newlines kept, so a comment quoting a key is not a read of it.
// The `[^:]` keeps a URL's `//` from blanking the rest of its line.
const blankComments = (text) =>
  text
    .replace(/\/\*[\s\S]*?\*\//g, (m) => m.replace(/[^\n]/g, " "))
    .replace(/(^|[^:])\/\/.*$/gm, (m, lead) => lead + m.slice(lead.length).replace(/./g, " "));

// A function's key is a quoted string equal to it, wherever it sits: a `t()` call, a table
// of keys, a prop. The lookahead lets two quoted strings share a quote.
const QUOTED = /(?=(["'`])([\w.-]+)\1)/g;
// A family of keys built at run time — `step.${id}`, or `"step." + id` — named by the
// namespaced head it starts with. `QUOTED` cannot see one, and neither can `tsc`, since the
// `as Key` that a built key needs accepts every catalogue's keys alike.
const FAMILY = /`([\w-]+\.[\w.-]*)\$\{|(["'])([\w-]+\.[\w.-]*)\2\s*\+/g;
// What can only be a key: the argument of `t()` or `plural()`, or a property named `…Key`.
const ASKED = /(?:\b(?:t|plural)\(\s*|\b\w*(Key)\s*:\s*)(["'`])([\w.-]+)\2/g;

const misread = [];
const unknown = [];
const unregistered = [];
const sources = walk(SRC)
  .map((full) => ({ full, path: relative(SRC, full).split(sep).join("/") }))
  .filter(({ path }) => !inCatalogue(path) && !/\.test\.tsx?$/.test(path));
// The function whose folder holds a path, among those with a catalogue; null for core.
const featureOf = (path) =>
  catalogues.find(({ feature }) => feature && path.startsWith(`${feature}/`))?.feature ?? null;
// Where an import specifier lands, relative to `src/`, or null for a package.
const landing = (file, specifier) => {
  if (specifier.startsWith("@/")) return specifier.slice(2);
  if (!specifier.startsWith(".")) return null;
  return relative(SRC, resolve(dirname(file), specifier)).split(sep).join("/");
};

for (const { full, path } of sources) {
  const code = blankComments(readFileSync(full, "utf8"));
  const line = (index) => code.slice(0, index).split("\n").length;
  const own = featureOf(path);

  for (const match of code.matchAll(QUOTED)) {
    const home = catalogueOf.get(match[2]);
    if (home?.feature && home.feature !== own) {
      misread.push(`${path}:${line(match.index)}  ${match[2]} — es de src/${home.feature}/`);
    }
  }
  for (const match of code.matchAll(FAMILY)) {
    const head = match[1] ?? match[3];
    const home = [...catalogueOf].find(
      ([key, catalogue]) => key.startsWith(head) && catalogue.feature && catalogue.feature !== own,
    )?.[1];
    if (home) {
      misread.push(`${path}:${line(match.index)}  ${head}… — construye claves de src/${home.feature}/`);
    }
  }
  for (const match of code.matchAll(ASKED)) {
    const [, property, , key] = match;
    // A `…Key` property outside every namespace a catalogue has is some other kind of key —
    // a storage slot, a setting — and not a misspelt one.
    if (property && !namespaces.has(key.split(".")[0])) continue;
    if (!catalogueOf.has(key)) unknown.push(`${path}:${line(match.index)}  ${key}`);
  }

  // A module of a function that core loads on demand registers the function's catalogue
  // before anything of it renders: its FIRST import is `import "./i18n"` (or `"../i18n"`).
  // An `import type` does not count, since it is gone before anything runs.
  if (own !== null) continue;
  for (const match of code.matchAll(/\bimport\(\s*["']([^"']+)["']\s*\)/g)) {
    const into = landing(full, match[1]);
    const feature = into === null ? null : featureOf(into);
    if (feature === null) continue;
    const target = [".ts", ".tsx", "/index.ts", "/index.tsx"]
      .map((extension) => resolve(SRC, into + extension))
      .find((file) => existsSync(file));
    if (target === undefined) continue;
    const imports = blankComments(readFileSync(target, "utf8"));
    const first = /^[ \t]*import\b(?!\s*\()(?!\s+type\b)[^\n]*/m.exec(imports);
    const bare = first && /^\s*import\s*["']([^"']+)["']/.exec(first[0]);
    if (!bare || landing(target, bare[1]) !== `${feature}/i18n`) {
      unregistered.push(`${path}:${line(match.index)}  import("${match[1]}")`);
    }
  }
}

if (twiceDeclared.length) {
  console.error("✗ Una clave está declarada en dos catálogos:\n");
  for (const entry of twiceDeclared) console.error(`  ${entry}`);
  console.error("\nAl registrarse se mezclan en la misma tabla, y gana la que llegue la última.");
  process.exit(1);
}

if (misread.length) {
  console.error(
    `✗ ${misread.length} clave(s) de una función opcional leídas fuera de su carpeta:\n`,
  );
  for (const entry of misread) console.error(`  ${entry}`);
  console.error(
    `\nFuera de su carpeta, el catálogo de la función no está cargado y se pinta el nombre de la\n` +
      `clave. Si la lee también el núcleo, devuélvela a src/lib/i18n/es.ts y en.ts.`,
  );
  process.exit(1);
}

if (unknown.length) {
  console.error(`✗ ${unknown.length} clave(s) que no están en ningún catálogo:\n`);
  for (const entry of unknown) console.error(`  ${entry}`);
  console.error(
    `\nSe leen en t(), en plural() o en una propiedad …Key, y se pintarían como su nombre.`,
  );
  process.exit(1);
}

if (unregistered.length) {
  console.error(
    `✗ ${unregistered.length} módulo(s) de una función cargados sin registrar antes su catálogo:\n`,
  );
  for (const entry of unregistered) console.error(`  ${entry}`);
  console.error(
    `\nAñade import "./i18n" (o "../i18n") como primer import del módulo que se carga,\n` +
      `para que sus cadenas estén antes de que se pinte.`,
  );
  process.exit(1);
}

// The guide is prose per language rather than keys, so nothing above can see it. What can
// be checked is that the two languages answer for the same sections: a section written in
// one and not the other renders nothing at all for half the readers.
//
// A language's bodies are the `BODIES` maps of every home it has: the guide's own tree
// (`features/guide/<lang>/sections.tsx`) and one file per optional function
// (`<function>/guide/<lang>.tsx`). Found by walking, so a new home is read without being
// listed here; a slug answered by two homes of one language is a failure of its own, since
// the registry would only ever read one of them.
const GUIDE_HOME = /(?:^|\/)guide\/(es|en)(?:\/sections)?\.tsx$/;
const homes = walk(SRC)
  .map((full) => relative(SRC, full).split(sep).join("/"))
  .filter((path) => GUIDE_HOME.test(path));
const twice = [];
// The body of a file's `BODIES` map and nothing else: a two-space `name: Value,` line
// elsewhere in the file — a destructured prop such as `icon: Icon,` — is not a section.
const BODIES_MAP = /^export const BODIES\b[\s\S]*?=\s*\{\n([\s\S]*?)^\};/m;
// Slug → the file of this language whose `BODIES` answers for it.
const bodiesOf = (language) => {
  const slugs = new Map();
  for (const file of homes.filter((path) => GUIDE_HOME.exec(path)[1] === language)) {
    const map = BODIES_MAP.exec(readFileSync(resolve(SRC, file), "utf8"))?.[1] ?? "";
    for (const match of map.matchAll(/^\s{2}(\w+):\s*\w+,$/gm)) {
      if (slugs.has(match[1])) twice.push(`${match[1]} — en ${slugs.get(match[1])} y en ${file}`);
      else slugs.set(match[1], file);
    }
  }
  return slugs;
};
const esBodies = bodiesOf("es");
const enBodies = bodiesOf("en");
const esSlugs = new Set(esBodies.keys());
const enSlugs = new Set(enBodies.keys());
const onlyEs = [...esSlugs].filter((slug) => !enSlugs.has(slug));
const onlyEn = [...enSlugs].filter((slug) => !esSlugs.has(slug));

if (twice.length) {
  console.error("✗ Una sección de la guía tiene cuerpo en dos sitios del mismo idioma:\n");
  for (const line of twice) console.error(`  ${line}`);
  process.exit(1);
}

if (onlyEs.length || onlyEn.length) {
  console.error("✗ Las dos versiones de la guía no cubren las mismas secciones:\n");
  for (const slug of onlyEs) console.error(`  ${slug} — solo en español`);
  for (const slug of onlyEn) console.error(`  ${slug} — solo en inglés`);
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
// El registro es la fuente: el cuerpo se busca a partir de él y no al revés. Una sección
// sin cuerpo en uno solo de los dos idiomas ya la ha parado la comprobación de arriba.
const REGISTRY = readFileSync(resolve(SRC, "features/guide/sections.tsx"), "utf8");
// Each entry of `GUIDE_SECTIONS` with the function it names, if any: one object literal,
// none of whose fields holds a brace.
const registry = [...REGISTRY.matchAll(/\{[^{}]*?\bslug:\s*"([\w-]+)"[^{}]*\}/g)].map((match) => ({
  slug: match[1],
  feature: /\bfeature:\s*"(\w+)"/.exec(match[0])?.[1] ?? null,
}));
const registrySlugs = registry.map((entry) => entry.slug);
const bodyless = registrySlugs.filter((slug) => !esSlugs.has(slug) && !enSlugs.has(slug));

if (bodyless.length) {
  console.error("✗ La guía anuncia secciones que no tienen texto en ningún idioma:\n");
  for (const slug of bodyless) console.error(`  ${slug} — está en GUIDE_SECTIONS, no en BODIES`);
  console.error(
    `\nCada una es una entrada del índice que abre una página en blanco.\n` +
      `Escribe su componente en src/features/guide/es/sections.tsx y en en/sections.tsx\n` +
      `(o, si explica una función opcional, en src/<función>/guide/es.tsx y en.tsx),\n` +
      `y añádelo al mapa BODIES de los dos.`,
  );
  process.exit(1);
}

// HAVING A BODY IS NOT ENOUGH: IT HAS TO BE WHERE THE REGISTRY LOOKS. `useGuideBody` reads a
// section from ONE place, `TREES[section.feature ?? "guide"]`: the guide's own tree, or the
// file of the function the section names. A body moved back into the common guide while
// the registry still says `feature`, or a section given a `feature` whose body stayed where
// it was, passes the three checks above and opens a blank page.
//
// A function's home is `<function>/guide/<lang>.tsx`, and the registry must import it under
// that name: checked too, so the convention does not live in this file alone.
const homeOf = (feature, language) =>
  feature === null ? `features/guide/${language}/sections.tsx` : `${feature}/guide/${language}.tsx`;
const misplaced = [];
for (const feature of new Set(registry.map((entry) => entry.feature).filter(Boolean))) {
  for (const language of ["es", "en"]) {
    if (!REGISTRY.includes(`import("@/${feature}/guide/${language}")`)) {
      misplaced.push(`${feature} — TREES no importa @/${feature}/guide/${language}`);
    }
  }
}
for (const { slug, feature } of registry) {
  for (const [language, bodies] of [["es", esBodies], ["en", enBodies]]) {
    const file = bodies.get(slug);
    const home = homeOf(feature, language);
    if (file !== undefined && file !== home) {
      misplaced.push(`${slug} — su cuerpo está en ${file}, y el registro lo lee de ${home}`);
    }
  }
}

if (misplaced.length) {
  console.error("✗ La guía tiene cuerpos donde el registro no los busca:\n");
  for (const line of misplaced) console.error(`  ${line}`);
  console.error(
    `\nCada una es una página en blanco. Una sección sin \`feature\` va en\n` +
      `src/features/guide/<idioma>/sections.tsx; una con \`feature: "x"\`, en src/x/guide/<idioma>.tsx.`,
  );
  process.exit(1);
}

console.log(
  `✓ ${migrated} fichero(s) sin texto de interfaz fuera del catálogo; ` +
    `${catalogueOf.size} claves en ${catalogues.length} catálogos, ` +
    `cada una leída donde se carga; ` +
    `${esSlugs.size} secciones de guía en los dos idiomas, ` +
    `las ${registrySlugs.length} del registro con cuerpo; ` +
    `${EXEMPT.size + EXEMPT_TREES.length} exclusión(es) deliberada(s).`,
);
