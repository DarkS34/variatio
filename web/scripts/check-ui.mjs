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
    name: "El tamaño por defecto no es text-xs",
    // 247 uses of text-xs against 125 of text-sm: the whole app lived at 12 px. `micro`
    // stops being a general-purpose size and gets a single declared use.
    re: /\btext-xs\b/g,
    exempt: [
      "components/ActivityFeed.tsx",
      "components/AppShell.tsx",
      "components/BuildProgress.tsx",
      "components/CodeBlock.tsx",
      "components/ConceptPicker.tsx",
      "components/ConceptSelector/BoardMode.tsx",
      "components/ConceptSelector/GraphMode.tsx",
      "components/ConceptSelector/SelectionTray.tsx",
      "components/ConceptSelector/index.tsx",
      "components/LogViewer.tsx",
      "components/Markdown.tsx",
      "components/RawImport.tsx",
      "components/RunDrawer.tsx",
      "components/RunTimeline.tsx",
      "components/StageGate.tsx",
      "components/TechnicalDetails.tsx",
      "components/TokenStream.tsx",
      "components/ui/badge.tsx",
      "components/ui/button.tsx",
      "components/ui/chips.tsx",
      "components/ui/hint.tsx",
      "components/ui/input.tsx",
      "features/account/AccountScreen.tsx",
      "features/admin/AdminScreen.tsx",
      "features/admin/charts.tsx",
      "features/auth/AcceptInvite.tsx",
      "features/auth/AccountMenu.tsx",
      "features/auth/AuthGate.tsx",
      "features/auth/ResetPassword.tsx",
      "features/bank/BankLive.tsx",
      "features/bank/BankScreen.tsx",
      "features/evaluation/ComparisonGrid.tsx",
      "features/evaluation/EvaluationScreen.tsx",
      "features/evaluation/FairnessTable.tsx",
      "features/evaluation/RevealPanel.tsx",
      "features/evaluation/RubricForm.tsx",
      "features/evaluation/SessionsTable.tsx",
      "features/generations/GenerationsPanel.tsx",
      "features/kg/CurriculumTab.tsx",
      "features/kg/DescriptionReview.tsx",
      "features/kg/GraphCanvas.tsx",
      "features/kg/KgScreen.tsx",
      "features/pipeline/Dashboard.tsx",
      "features/profile/FieldEditor.tsx",
      "features/profile/ProfileEditor.tsx",
      "features/run/DecisionField.tsx",
      "features/run/FewShotPanel.tsx",
      "features/run/FormStep.tsx",
      "features/run/GenerateForm.tsx",
      "features/run/ResultCard.tsx",
      "features/run/RunPanel.tsx",
      "features/workspaces/WorkspaceSwitcher.tsx",
    ],
  },
  {
    name: "Ningún control de formulario sin etiqueta asociada",
    // A text placed above a control is not a label: without htmlFor you cannot click it to
    // focus the field, and a screen reader announces the control unnamed. What is checked
    // is that the control goes through <Field>, which is what ties the three together.
    //
    // Deliberately coarse: `requires` clears the whole file once Field appears in it. A
    // per-control check would need a parser, and the point here is to stop a NEW screen
    // being born without labels, not to audit each call site.
    re: /<(?:Input|Textarea|Select)\b(?![^>]*\baria-label\b)/g,
    requires: /\bField\b/,
    exempt: [
      "components/ConceptPicker.tsx",
      "components/ConceptSelector/index.tsx",
      "components/LogViewer.tsx",
      "features/account/AccountScreen.tsx",
      "features/admin/AdminScreen.tsx",
      "features/auth/AcceptInvite.tsx",
      "features/auth/AuthGate.tsx",
      "features/auth/LoginScreen.tsx",
      "features/auth/ResetPassword.tsx",
      "features/evaluation/ComparisonGrid.tsx",
      "features/evaluation/RubricForm.tsx",
      "features/generations/GenerationsPanel.tsx",
      "features/kg/DescriptionReview.tsx",
      "features/kg/KgScreen.tsx",
      "features/profile/FieldEditor.tsx",
      "features/profile/ProfileEditor.tsx",
      "features/run/DecisionField.tsx",
      "features/run/GenerateForm.tsx",
      "features/workspaces/WorkspaceSwitcher.tsx",
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
      "features/admin/AdminScreen.tsx",
      "features/bank/BankScreen.tsx",
      "features/evaluation/FairnessTable.tsx",
      "features/evaluation/SessionsTable.tsx",
      "features/kg/KgScreen.tsx",
    ],
  },
  {
    name: "Ningún token retirado (--success / --warning / --info)",
    re: /var\(--(?:success|warning|info)\)/g,
    exempt: [
      "components/ActivityFeed.tsx",
      "components/AppShell.tsx",
      "components/BuildProgress.tsx",
      "components/CodeBlock.tsx",
      "components/ConceptPicker.tsx",
      "components/ConceptSelector/BoardMode.tsx",
      "components/LogViewer.tsx",
      "components/RawImport.tsx",
      "components/RunTimeline.tsx",
      "components/TechnicalDetails.tsx",
      "components/TokenStream.tsx",
      "components/ui/badge.tsx",
      "components/ui/chips.tsx",
      "components/ui/misc.tsx",
      "features/account/AccountScreen.tsx",
      "features/admin/AdminScreen.tsx",
      "features/bank/BankScreen.tsx",
      "features/evaluation/FairnessTable.tsx",
      "features/evaluation/RevealPanel.tsx",
      "features/evaluation/RubricForm.tsx",
      "features/kg/DescriptionReview.tsx",
      "features/kg/GraphCanvas.tsx",
      "features/kg/KgScreen.tsx",
      "features/pipeline/Dashboard.tsx",
      "features/profile/FieldEditor.tsx",
      "features/profile/ProfileEditor.tsx",
      "features/run/FewShotPanel.tsx",
      "features/run/GenerateForm.tsx",
      "lib/format.ts",
    ],
  },
];

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

console.log(failures === 0 ? "\nTodo pasa.\n" : `\n${failures} regla(s) fallan.\n`);
process.exit(failures === 0 ? 0 : 1);
