#!/usr/bin/env node
// Whether the client's imports go one way: app → features → components → state → lib.
//
// `App.tsx`, `AppShell.tsx` and `main.tsx` compose; a folder of `features/`, `consumers/` or
// `landing/` is one screen or function; `components/` is what several of them share; `state/`
// holds the data hooks and stores; `lib/` is pure helpers. An import may go down that list or
// stay inside its own layer, and a screen's folder may not import another screen's folder:
// what two of them share belongs a layer down. Static imports, type imports and `import()` all
// count, read by the same scanner as `check:lazy` (`imports.mjs`).
//
// `ALLOWED` lists the imports of today that go against it, file to file. It may only shrink:
// a new import against the direction fails, and so does an entry that no longer exists, so
// that whoever removes an exception removes its line too.
import { readFileSync } from "node:fs";

import { BARE, SELF_TESTS, SRC, STATIC, blankComments, fromSrc, target, walk } from "./imports.mjs";

const DYNAMIC = /\bimport\(\s*(["'])([^"']+)\1\s*\)/g;

const RANK = { app: 4, feature: 3, components: 2, state: 1, lib: 0 };

const ALLOWED = new Set([
  "components/ConceptSelector/GraphMode.tsx -> features/kg/GraphCanvas",
  "components/ConceptSelector/GraphMode.tsx -> features/kg/graph/model",
  "components/StageGate.tsx -> consumers/evaluation/StageReviewSlot",
  "consumers/evaluation/AdminSetsPanel.tsx -> consumers/generation/commission",
  "consumers/evaluation/AdminSetsPanel.tsx -> consumers/generation/GenerateForm",
  "consumers/evaluation/commission.test.ts -> consumers/generation/commission",
  "consumers/evaluation/commission.ts -> consumers/generation/commission",
  "consumers/evaluation/ComparisonGrid.tsx -> consumers/generation/ResultCard",
  "consumers/evaluation/EvaluationScreen.tsx -> consumers/generation/commission",
  "consumers/evaluation/EvaluationScreen.tsx -> consumers/generation/GenerateForm",
  "consumers/evaluation/EvaluationScreen.tsx -> consumers/generation/screening",
  "consumers/evaluation/ProposalDialog.tsx -> consumers/generation/ResultCard",
  "consumers/evaluation/RevealPanel.tsx -> consumers/generation/ResultCard",
  "consumers/generation/DecisionField.tsx -> features/profile/FieldEditor",
  "consumers/generation/GenerateForm.tsx -> features/profile/FieldEditor",
  "consumers/generation/GenerateScreen.tsx -> features/bank/Promote",
  "consumers/generation/GenerationsPanel.tsx -> features/bank/Promote",
  "features/account/AccountScreen.tsx -> consumers/generation/GenerationsPanel",
  "features/account/AccountScreen.tsx -> features/workspaces/PeopleWhoLoseAccess",
  "features/admin/AdminScreen.tsx -> consumers/evaluation/AdminEvaluationTab",
  "features/admin/AdminScreen.tsx -> consumers/evaluation/types",
  "features/admin/SettingFields.tsx -> consumers/generation/effort",
  "features/admin/SettingFields.tsx -> consumers/generation/models",
  "features/admin/WorkspaceGenerations.tsx -> consumers/generation/GenerationsPanel",
  "features/admin/WorkspacesTab.tsx -> consumers/tutor/AdminConversations",
  "features/admin/WorkspacesTab.tsx -> features/workspaces/PeopleWhoLoseAccess",
  "features/auth/AuthGate.tsx -> features/maintenance/MaintenanceScreen",
  "features/auth/AuthGate.tsx -> landing/DemoPage",
  "features/auth/AuthGate.tsx -> landing/LandingScreen",
  "features/bank/AddExercise.tsx -> consumers/generation/ResultCard",
  "features/bank/BankReader.tsx -> consumers/generation/draft",
  "features/bank/BankReader.tsx -> consumers/generation/GenerationsPanel",
  "features/bank/BankReader.tsx -> consumers/generation/ResultCard",
  "features/bank/BankScreen.tsx -> consumers/generation/GenerationsPanel",
  "features/bank/BankStep.tsx -> features/profile/ProfileEditor",
  "features/bank/exercise.ts -> consumers/generation/commission",
  "features/bank/GeneratedList.tsx -> consumers/generation/draft",
  "features/bank/GeneratedList.tsx -> consumers/generation/ResultCard",
  "features/class/ProgressSection.tsx -> consumers/generation/prerequisites",
  "features/maintenance/MaintenanceScreen.tsx -> features/auth/LoginScreen",
  "landing/demo/world.test.ts -> features/raw/progress",
  "landing/LandingScreen.tsx -> features/auth/AuthGate",
  "lib/api.ts -> state/workspace",
  "lib/i18n/index.ts -> consumers/evaluation/i18n/es",
  "lib/i18n/index.ts -> consumers/tutor/i18n/es",
  "lib/i18n/index.ts -> landing/i18n/es",
  "lib/types/bank.ts -> features/profile/drift",
  "state/queries/jobs.ts -> components/ui/toast",
]);

/** The layer of a path relative to `src/`, and the folder it counts as; null outside them. */
function place(path) {
  if (/^(App|AppShell|main)\.tsx?$/.test(path)) return { layer: "app", unit: "app" };
  const [top, sub] = path.split("/");
  if (top === "features" || top === "consumers") return { layer: "feature", unit: `${top}/${sub}` };
  if (top === "landing") return { layer: "feature", unit: "landing" };
  if (top === "components" || top === "state" || top === "lib") return { layer: top, unit: top };
  return null;
}

const misread = SELF_TESTS.filter(
  ([source, seen]) => [...blankComments(source).matchAll(STATIC)].length > 0 !== seen,
);
if (misread.length) {
  console.log("FALLA  El quitacomentarios lee mal alguno de sus casos (imports.mjs).");
  process.exit(1);
}

const found = new Map(); // "from -> to" → the first line it was seen on
const unplaced = [];
for (const full of walk(SRC)) {
  const from = fromSrc(full);
  const source = place(from);
  if (source === null) {
    unplaced.push(from);
    continue;
  }
  const code = blankComments(readFileSync(full, "utf8"));
  const line = (index) => code.slice(0, index).split("\n").length;
  const specifiers = [
    ...[...code.matchAll(STATIC)].map((m) => [m[5], m.index]),
    ...[...code.matchAll(BARE)].map((m) => [m[2], m.index]),
    ...[...code.matchAll(DYNAMIC)].map((m) => [m[2], m.index]),
  ];
  for (const [specifier, index] of specifiers) {
    const into = target(full, specifier);
    const destination = into === null ? null : place(into);
    if (destination === null) continue;
    const up = RANK[destination.layer] > RANK[source.layer];
    const across =
      source.layer === "feature" && destination.layer === "feature" && source.unit !== destination.unit;
    if (!up && !across) continue;
    const pair = `${from} -> ${into.replace(/\.(tsx?|js)$/, "")}`;
    if (!found.has(pair)) found.set(pair, `${from}:${line(index)}`);
  }
}

const added = [...found].filter(([pair]) => !ALLOWED.has(pair));
const gone = [...ALLOWED].filter((pair) => !found.has(pair));
let failed = false;

if (unplaced.length) {
  failed = true;
  console.log("FALLA  Ficheros fuera de las capas (App/AppShell/main, features, consumers, landing, components, state, lib):");
  for (const path of unplaced) console.log(`         ${path}`);
}
if (added.length) {
  failed = true;
  console.log("FALLA  Importaciones nuevas contra la dirección app → features → components → state → lib:");
  for (const [pair, where] of added) console.log(`         ${where}  ${pair}`);
  console.log("         Lleva lo compartido a la capa de abajo (components/, state/ o lib/).");
}
if (gone.length) {
  failed = true;
  console.log("FALLA  Excepciones de ALLOWED que ya no existen; bórralas de scripts/check-layers.mjs:");
  for (const pair of gone) console.log(`         ${pair}`);
}
if (failed) process.exit(1);
console.log(`✓ Las importaciones van en una dirección; ${ALLOWED.size} excepciones con nombre.`);
