#!/usr/bin/env node
// Structural invariants of the interface. It does not measure taste: it measures the four
// things that decay on their own the moment somebody adds a screen — the default text
// size, form labels, hand-rolled tables and retired tokens.
//
// The `exempt` list on each rule is the mechanism of the migration, not an excuse: a
// screen task starts by DELETING its file from the list so the script goes red, and it is
// done when the script goes green again. When all four lists are empty the migration is
// over, and that is a checkable statement rather than a to-do item somebody ticked.
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

const FILES = walk(SRC).map((full) => ({
  path: relative(SRC, full).split(sep).join("/"),
  text: readFileSync(full, "utf8"),
}));

const RULES = [
  {
    // Two problems, one rule. The first: 247 uses of text-xs against 125 of text-sm, so
    // the whole app lived at 12 px and `micro` had to stop being a general-purpose size.
    // The second: Tailwind's own scale is still present — nothing removed it — so a size
    // can be spelled twice. text-sm and text-body are the same 0.875rem today, which is
    // not a bug on screen but a bug waiting: move the step and 95 call sites do not
    // follow it. The six steps of the design scale are the only vocabulary.
    name: "Ningún tamaño de la escala cruda de Tailwind",
    re: /\btext-(?:xs|sm|base|lg|xl|2xl|3xl|4xl)\b/g,
    exempt: [],
  },
  {
    name: "Ningún control de formulario sin etiqueta asociada",
    // A text placed above a control is not a label: without htmlFor you cannot click it to
    // focus the field, and a screen reader announces the control unnamed.
    //
    // Two shapes satisfy this and neither is preferred: <Field>, which also ties the
    // description and the error in, or a plain <Label htmlFor> matching the control's id.
    // Requiring Field alone was wrong — it flagged the account and auth screens, which were
    // already binding every one of their controls correctly, and "rewrite working code to
    // use my component" is not an accessibility fix.
    //
    // Deliberately coarse: `requires` clears the whole file once either shape appears. A
    // per-control check would need a parser, and the point is to stop a NEW screen being
    // born without labels, not to audit each call site.
    re: /<(?:Input|Textarea|Select)\b(?![^>]*\baria-label\b)/g,
    requires: /\bField\b|htmlFor=/,
    exempt: [
      "components/ConceptPicker.tsx",
      "components/ConceptSelector/index.tsx",
    ],
  },
  {
    name: "Ninguna <table> cruda fuera de ui/table.tsx",
    re: /<table\b/g,
    exempt: [
      // The first two are PERMANENT and do not belong to the migration: ui/table.tsx is
      // the primitive itself, and Markdown.tsx renders a markdown table into HTML — that
      // is content the model wrote, not one of the app's own data tables, so wrapping it
      // in the primitive would be applying a layout decision to somebody else's document.
      "components/ui/table.tsx",
      "components/Markdown.tsx",
    ],
  },
  {
    name: "Ningún token retirado (--success / --warning / --info)",
    re: /var\(--(?:success|warning|info)\)/g,
    exempt: [],
  },
];

// A BUDGET, not an exemption list, and it exists because the four rules above share a
// blind spot: they would all pass if `text-xs` were replaced by `text-micro` one for one.
// The app would still live in a single size, just under a different name, and nothing
// would say so — this was the one check the plan admitted no script could make.
//
// It can, as long as what is counted is the size that is supposed to be RARE. `micro` has
// one declared job: eyebrows, rail labels, table headers and badges. Roughly one or two
// per screen. The ceiling is set well above that and far below the 247 uses `text-xs` had,
// so hitting it does not mean "one too many" — it means micro has quietly become the new
// default and the question of §2.2 is open again.
const BUDGET = { name: "text-micro sigue siendo un tamaño raro", re: /\btext-micro\b/g, max: 90 };

let failures = 0;

for (const rule of RULES) {
  const hits = [];
  for (const file of FILES) {
    if (rule.exempt.includes(file.path)) continue;
    // A rule with `requires` only complains when the pattern appears AND the piece that
    // legitimises it is absent from the file.
    if (rule.requires && rule.requires.test(file.text)) continue;
    const found = file.text.match(rule.re);
    if (found) hits.push(`${file.path} (${found.length})`);
  }
  if (hits.length === 0) {
    console.log(`ok     ${rule.name}`);
  } else {
    failures++;
    console.log(`FALLA  ${rule.name}`);
    for (const hit of hits) console.log(`         ${hit}`);
  }
}

const used = FILES.reduce((sum, file) => sum + (file.text.match(BUDGET.re)?.length ?? 0), 0);
if (used <= BUDGET.max) {
  console.log(`ok     ${BUDGET.name} (${used}/${BUDGET.max})`);
} else {
  failures++;
  console.log(`FALLA  ${BUDGET.name} (${used}/${BUDGET.max})`);
  console.log("         micro es para eyebrows, etiquetas de raíl, cabeceras y distintivos.");
  console.log("         Si se ha pasado del techo, probablemente ha sustituido a text-xs uno");
  console.log("         a uno y la aplicación vuelve a vivir en un solo tamaño.");
}

console.log(failures === 0 ? "\nTodo pasa.\n" : `\n${failures} regla(s) fallan.\n`);
process.exit(failures === 0 ? 0 : 1);
