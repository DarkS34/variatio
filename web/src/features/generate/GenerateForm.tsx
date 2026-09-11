import {
  Ban,
  Brain,
  Check,
  ChevronRight,
  Cpu,
  ListChecks,
  Minus,
  PenLine,
  Play,
  Plus,
  Scale,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { ConceptSelector } from "@/components/ConceptSelector";
import { Badge } from "@/components/ui/badge";
import { ConceptChip } from "@/components/ui/concept-chip";
import { InfoHint } from "@/components/ui/hint";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Alert, Spinner, Switch } from "@/components/ui/misc";
import { hasExemplars } from "@/lib/concepts";
import { assumedKnown, notYetTaught } from "@/lib/curriculum";
import { domainColours } from "@/lib/domains";
import {
  defaultTypeKey,
  difficultyFieldOf,
  difficultyLevelsOf,
  otherDecidedFields,
  typeKeys,
} from "@/lib/profile";
import { readableValue } from "@/lib/text";
import type {
  ExemplarsProfile,
  GraphView,
  ItemTypeSpec,
  KgConcept,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { baseType } from "@/features/profile/FieldEditor";
import { useHealth, useScope } from "@/state/queries";
import { useT, type Translate } from "@/lib/i18n";

import type { FormState } from "./commission";
import { DecisionField, describeDecision } from "./DecisionField";
import { DifficultyChoice } from "./DifficultyChoice";
import {
  EFFORT_LABELS,
  clampEffort,
  effortAdjustable,
  effortPolicy,
  effortWarning,
  fixedEffort,
} from "./effort";
import { EffortSlider } from "./EffortSlider";
import { CHOICE_CARD, FormStep } from "./FormStep";
import { ModelChoice } from "./ModelChoice";
import { modelLabel } from "./models";
import { adjacency, covered, posteriors, priors } from "./prerequisites";
import { CancelButton } from "@/components/CancelButton";
import type { RunView } from "@/state/runStore";

const MAX_ITEMS = 20;
// One identity for "the payload has not arrived", so the effect below is not re-run by a
// fresh `[]` on every render.
const NONE: string[] = [];
/** Mirrors config.GENERATION_INSTRUCTIONS_MAX_CHARS. */
const MAX_INSTRUCTIONS = 600;
/** A problem that blocks the launch and is explained elsewhere. See `problems`. */
const SILENT_OUTSIDE = "\u0000outside";

/** The modality actually in force: what the form shows and what the run will produce. */
export function activeTypeKey(
  state: FormState,
  profile: ExemplarsProfile | null,
): string | null {
  const keys = typeKeys(profile);
  if (state.itemType && keys.includes(state.itemType)) return state.itemType;
  return keys.length === 1 ? defaultTypeKey(profile) : null;
}

export function activeTypeSpec(
  state: FormState,
  profile: ExemplarsProfile | null,
): ItemTypeSpec | null {
  const key = activeTypeKey(state, profile);
  return key && profile ? profile.item_types[key] : null;
}

// The curriculum in force, in words, for the form step and for the line that replaces the
// whole form once collapsed. One derivation: two of them drift apart exactly where it
// matters, reading "currículo de 0" over a request carrying `[]`, which is no restriction.
// `presetSize` is null where the workspace's own has not been read.
function curriculumLabel(
  state: FormState,
  presetSize: number | null,
  { t }: Translate,
): string {
  if (state.usePresetCurriculum) {
    if (presetSize === null) return t("form.curriculum.workspace");
    return presetSize > 0
      ? t("form.curriculum.workspaceN", { n: presetSize })
      : t("form.curriculum.none");
  }
  return state.curriculum.length > 0
    ? t("form.curriculum.ofN", { n: state.curriculum.length })
    : t("form.curriculum.none");
}

export function summarize(
  state: FormState,
  profile: ExemplarsProfile | null,
  tr: Translate,
): string {
  const { t, plural } = tr;
  const spec = activeTypeSpec(state, profile);
  const parts = [plural("form.items", state.n)];
  if (spec && typeKeys(profile).length > 1) parts.push(spec.label || activeTypeKey(state, profile)!);
  parts.push(state.concepts.join(" · ") || t("form.summary.noConcepts"));
  // The difficulty leads the pinned fields, because it is the one every modality carries.
  const difficulty = difficultyFieldOf(spec);
  for (const field of difficulty ? [difficulty, ...otherDecidedFields(spec)] : otherDecidedFields(spec)) {
    const value = state.decisions[field];
    if (value !== undefined && value !== null && value !== "") parts.push(String(value));
  }
  const label = curriculumLabel(state, null, tr);
  parts.push(label.charAt(0).toLowerCase() + label.slice(1));
  if (state.instructions.trim()) parts.push(t("form.summary.withInstructions"));
  if (!state.think) parts.push(t("form.summary.noReasoning"));
  else if (state.effort !== "low")
    parts.push(
      t("form.summary.reasoning", { level: t(EFFORT_LABELS[state.effort]).toLowerCase() }),
    );
  return parts.join(" · ");
}

// The two lists the graph derives, read as a contrast: what the item may lean on, and what
// it may not name at all. Same shape, opposite tone.
function ConceptTrack({
  tone,
  icon,
  label,
  concepts,
}: {
  tone: "given" | "forbidden";
  icon: ReactNode;
  label: string;
  concepts: string[];
}) {
  if (concepts.length === 0) return null;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <span
        className={cn(
          "inline-flex items-center gap-1 text-micro font-condensed uppercase",
          // The strikethrough carries "forbidden"; the colour carries the POSITION, which
          // is the palette's own frontier.
          tone === "given" ? "text-settled" : "text-muted-foreground",
        )}
      >
        {icon}
        {label}
      </span>
      {concepts.map((name) => (
        <span
          key={name}
          className={cn(
            "rounded-full border px-2 py-0.5 text-small",
            tone === "given"
              ? "border-[color-mix(in_oklch,var(--settled)_35%,transparent)] text-settled"
              : "border-border text-muted-foreground line-through decoration-muted-foreground/50",
          )}
        >
          {name}
        </span>
      ))}
    </div>
  );
}

// What the full-screen selector left behind: the overlay closes and its tray goes with it,
// so without this the answer to the question would be a number.
function ChosenConcepts({
  names,
  colourFor,
  onRemove,
  empty,
  centred = false,
}: {
  names: string[];
  colourFor: (name: string) => string | undefined;
  onRemove: (name: string) => void;
  empty: string;
  /** Under a centred button, so that the chosen names sit under the control that chose them. */
  centred?: boolean;
}) {
  const { t } = useT();
  if (names.length === 0)
    return (
      <p className={cn("text-body text-muted-foreground", centred && "text-center")}>{empty}</p>
    );
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", centred && "justify-center")}>
      {names.map((name) => (
        <ConceptChip
          key={name}
          colour={colourFor(name)}
          onRemove={() => onRemove(name)}
          removeLabel={t("form.removeConcept", { name })}
        >
          {name}
        </ConceptChip>
      ))}
    </div>
  );
}

export function Count({
  value,
  onChange,
  max = MAX_ITEMS,
}: {
  value: number;
  onChange: (next: number) => void;
  max?: number;
}) {
  const { t } = useT();
  // A stepper rather than a number box: an emptied box yields NaN, which compares false
  // against every bound and travels to the server as null.
  const clamp = (next: number) => onChange(Math.min(max, Math.max(1, next)));
  return (
    <div className="flex items-center gap-1 rounded-lg border border-border p-1">
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={t("form.oneFewer")}
        onClick={() => clamp(value - 1)}
        disabled={value <= 1}
      >
        <Minus />
      </Button>
      <span className="w-8 text-center text-body font-medium nums">{value}</span>
      <Button
        variant="ghost"
        size="icon-sm"
        aria-label={t("form.oneMore")}
        onClick={() => clamp(value + 1)}
        disabled={value >= max}
      >
        <Plus />
      </Button>
    </div>
  );
}

export function GenerateForm({
  state,
  onChange,
  profile,
  concepts,
  graph,
  disabled,
  running,
  pending,
  error,
  blockedInstructions,
  onLaunch,
  run = null,
  variant = "generate",
  footnote,
  launchLabel,
  workspace,
}: {
  state: FormState;
  onChange: (next: FormState) => void;
  profile: ExemplarsProfile | null;
  concepts: KgConcept[];
  graph: GraphView | undefined;
  disabled: boolean;
  running: boolean;
  pending: boolean;
  error: string | null;
  blockedInstructions: string | null;
  onLaunch: () => void;
  /** The job this form is watching, so the stop it offers can say it was heard. */
  run?: RunView | null;
  /** "evaluation" drops the item counter: one item per arm is what makes the session
   *  the statistical unit. Everything else is shared, which is precisely what
   *  guarantees the commission is the same one on both screens. */
  variant?: "generate" | "evaluation";
  footnote?: ReactNode;
  /** Overrides the launch button's text. The panel commissions a BATCH of comparisons,
   *  which "Comparar tres propuestas" would misreport as one. */
  launchLabel?: string;
  /** Which instance this commission is FOR, when it is not the one the tab is in. The
   *  concepts, the profile and the graph arrive as props, but two things the form reads
   *  for itself — the preset curriculum and the free text's scope — would otherwise come
   *  from the tab's workspace and describe a syllabus the run will never see. */
  workspace?: string | null;
}) {
  const tr = useT();
  const { t, plural } = tr;
  const [open, setOpen] = useState<string | null | undefined>(undefined);
  // What the full-screen selector is choosing: the targets, the ad-hoc curriculum, or
  // nothing. One state, because only one overlay can be open.
  const [picking, setPicking] = useState<"concepts" | "curriculum" | null>(null);
  const patch = (fields: Partial<FormState>) => onChange({ ...state, ...fields });

  const types = typeKeys(profile);
  const typeKey = activeTypeKey(state, profile);
  const typeSpec = activeTypeSpec(state, profile);
  const decided = otherDecidedFields(typeSpec);
  // The one field every modality carries, and the only one whose options come with a
  // written criterion. It is asked in a step of its own — see `DifficultyChoice`.
  const difficultyField = difficultyFieldOf(typeSpec);
  const difficultyLevels = difficultyLevelsOf(typeSpec);
  const asksDifficulty = Boolean(difficultyField) && difficultyLevels.length > 0;
  // What every exemplar count on this screen is about. With one modality declared there is
  // nothing to narrow: the total already counts exactly what the few-shot may draw from.
  const exemplarType = types.length > 1 ? typeKey : null;
  const typeLabel = typeSpec?.label || typeKey || "";
  // The resolved key, not `state.itemType`: null there means the profile's first modality,
  // and that is the state the form starts in, so the raw value would leave the query off
  // in the commonest case of all.
  const scope = useScope(typeKey, workspace);
  const graphAdjacency = useMemo(() => adjacency(graph), [graph]);
  const chosen = state.concepts.length > 0;

  // Which model writes it is the COMMISSION's; the installation decides everything around
  // the choice in "Configuración → Modelos generadores". Offering exactly one makes the
  // chooser disappear, so an installation that wants to decide still does.
  //
  // Read BEFORE the effort, because the effort depends on it: which levels a family
  // implements, and which are worth a warning, are the model's. Every read is defensive —
  // an older API sends no `offered` and no `fixed_effort`, and the screen degrades to "the
  // installation decides" with the full scale rather than to blank.
  const health = useHealth();
  const offered = health.data?.models.offered ?? NONE;
  const remoteModels = health.data?.models.remote ?? NONE;
  const missingModels = health.data?.models.missing ?? NONE;
  const fixedModels = health.data?.models.fixed_effort ?? NONE;
  const fixedLevels = health.data?.models.fixed_effort_levels;
  // The first offered one is what the server resolves an absent `model` to, so it is what
  // the screen names while nobody has chosen.
  const generationModel =
    state.model && offered.includes(state.model) ? state.model : offered[0];
  const policy = effortPolicy(generationModel);
  // Whether the slider is offered for THIS model: a measurement the installation records
  // in `generation.fixed_effort`.
  const adjustable = effortAdjustable(generationModel, fixedModels);
  // And with which level a locked one is called: the installation's declaration, or the
  // engine's own default, which travels as a bare `true` and never as a level this form
  // picked. Hiding the slider is not enough — its value would still be sent.
  const locked = adjustable ? null : fixedEffort(generationModel, fixedLevels, policy);
  const effort = adjustable ? clampEffort(state.effort, policy) : (locked ?? "low");
  const warning = adjustable ? effortWarning(effort, policy) : null;

  // A value the form can no longer show must not be what the request carries: the panel
  // edits the offered list while this form sits open.
  useEffect(() => {
    if (state.model && offered.length > 0 && !offered.includes(state.model)) {
      patch({ model: null });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.model, offered]);

  // The curriculum that will be in force, resolved exactly as the server resolves it. An
  // empty list is NOT a restriction there and is truthy here, so it is collapsed to null
  // once rather than at each of the three places that read it.
  //
  // What is ticked is CLOSED DOWNWARDS: covering "if" covers what "if" rests on.
  // `server/curriculum.resolve` closes the same list before the generator reads it, so what
  // this form counts is what runs. `state.curriculum` keeps only the picks, which is what
  // lets the selector MARK the rest instead of drawing it as chosen.
  const coveredCurriculum = useMemo(
    () => covered(graphAdjacency, state.curriculum),
    [graphAdjacency, state.curriculum],
  );
  const activeCurriculum = useMemo(() => {
    const list = state.usePresetCurriculum ? [] : coveredCurriculum;
    return list.length > 0 ? list : null;
  }, [state.usePresetCurriculum, coveredCurriculum]);
  // Whether anything bounds this commission: the list holds something, or an older run
  // is being described that ran against the workspace's own.
  const restricting = state.usePresetCurriculum || state.curriculum.length > 0;

  const priorClosure = useMemo(
    () => (graphAdjacency && chosen ? priors(graphAdjacency, state.concepts) : []),
    [graphAdjacency, state.concepts, chosen],
  );
  const posteriorClosure = useMemo(
    () => (graphAdjacency && chosen ? posteriors(graphAdjacency, state.concepts) : []),
    [graphAdjacency, state.concepts, chosen],
  );

  // The MARK is the bare closure and says where a concept sits relative to the targets: a
  // statement about the graph, not about coverage. It is not a LOCK — a prerequisite chosen
  // as a target is an ordinary commission, `KnowledgeGraph._closure` subtracting the targets
  // from what it returns.
  const implied = useMemo(() => new Set(priorClosure), [priorClosure]);
  // The same mark on the curriculum selector: what the ticked coverage rests on. Here the
  // mark also COUNTS — see `coveredCurriculum` — where on the targets it only reports.
  const impliedCurriculum = useMemo(
    () => new Set(graphAdjacency ? priors(graphAdjacency, state.curriculum) : []),
    [graphAdjacency, state.curriculum],
  );

  const given = useMemo(
    () => assumedKnown(priorClosure, activeCurriculum),
    [priorClosure, activeCurriculum],
  );
  const forbidden = useMemo(
    () => notYetTaught(posteriorClosure, activeCurriculum),
    [posteriorClosure, activeCurriculum],
  );

  const byName = useMemo(
    () => new Map(concepts.map((concept) => [concept.name, concept])),
    [concepts],
  );
  const colours = useMemo(() => domainColours(concepts), [concepts]);
  const colourFor = (name: string) => colours.get(byName.get(name)?.domain ?? "");

  const zeroShot = useMemo(
    () =>
      state.concepts.filter(
        (name) => !byName.has(name) || !hasExemplars(byName.get(name)!, exemplarType),
      ),
    [state.concepts, byName, exemplarType],
  );

  // The bank is searched with the whole set at once, so one concept with exemplars is
  // enough to keep the batch out of zero-shot: the warning is about the empty set, not
  // about each name that happens to have none.
  const wholeBatchZeroShot = chosen && zeroShot.length === state.concepts.length;

  // The steps actually on screen, in order, and the one place that order is written down.
  // Derived rather than constant: with a single modality declared there is nothing to ask
  // first, and the last two appear only once something has been chosen.
  // The numbered steps ARE the commission, and nothing optional is one of them.
  const steps = [
    types.length > 1 ? "itemType" : null,
    "concepts",
    chosen && asksDifficulty ? "difficulty" : null,
    chosen && decided.length > 0 ? "decisions" : null,
  ].filter((id): id is string => id !== null);

  const openStep = open === undefined ? steps[0] : open;
  const step = (id: string) => ({
    open: openStep === id,
    onOpen: () => setOpen(openStep === id ? null : id),
  });

  // Answering a step opens the next one, and only a gesture that leaves NOTHING else to
  // decide in that step may call it: collapsing a question somebody is still in the middle
  // of is worse than the click it saves. Marking the curriculum is not such a gesture.
  const advance = (from: string) => setOpen(steps[steps.indexOf(from) + 1] ?? null);

  // Changing modality changes which concepts have exemplars at all, so what was chosen
  // under the previous one has to pass the same filter the selector applies.
  const chooseType = (key: string) => {
    const kept = state.concepts.filter((name) => {
      const concept = byName.get(name);
      return Boolean(concept && hasExemplars(concept, key));
    });
    patch({ itemType: key, decisions: {}, concepts: kept });
    advance("itemType");
  };

  // Concepts the curriculum leaves out. The selector's `restrictTo` keeps this from arising
  // the normal way round, so what reaches here is narrowing the curriculum after choosing,
  // or a commission restored from an older row. A correction and not a wall: the launch
  // button refuses, and dropping them is one click.
  const outsideCurriculum = useMemo(() => {
    if (!activeCurriculum) return [];
    const inside = new Set(activeCurriculum);
    return state.concepts.filter((c) => !inside.has(c));
  }, [activeCurriculum, state.concepts]);

  // The same question asked of a selection that has NOT been committed to `state` yet,
  // which is what the selector's confirm has to decide on.
  const hasOutside = (names: string[]) =>
    Boolean(activeCurriculum) && names.some((c) => !new Set(activeCurriculum!).has(c));

  // Same rules the generator enforces server-side; failing here is just faster.
  const problems = useMemo(() => {
    const found: string[] = [];
    if (types.length > 1 && !typeKey) found.push(t("form.problem.itemType"));
    if (state.concepts.length === 0) found.push(t("form.problem.concepts"));
    // Listed so the button refuses, but never printed: the notice in the concepts step
    // says the same thing and offers the two ways out, so repeating it beside the button
    // is one error drawn twice on one screen.
    if (outsideCurriculum.length > 0) found.push(SILENT_OUTSIDE);
    if (state.instructions.trim().length > MAX_INSTRUCTIONS)
      found.push(t("form.problem.tooLong", { max: MAX_INSTRUCTIONS }));
    return found;
  }, [types.length, typeKey, state.concepts, outsideCurriculum, state.instructions, t]);

  const decisionSummary = decided
    .map((field) => describeDecision(field, state.decisions[field], t))
    .join(" · ");

  // The box counts what is COVERED — the picks closed downwards — because that is what the
  // button beside it counts and what will run.
  const curriculumSummary =
    restricting && !state.usePresetCurriculum
      ? t("form.curriculum.ofN", { n: coveredCurriculum.length })
      : curriculumLabel(state, null, tr);

  // What "Ajustes" says while shut: anything set is named, because a disclosure that hides
  // a decision without saying so is where a decision goes to be forgotten.
  const settingsSummary = state.instructions.trim()
    ? t("form.settings.withInstructions")
    : t("form.settings.none");

  let index = 0;

  // The form is a surface of its own, so what you answer is separated from the header, the
  // alerts and the results by more than vertical space. One step of tint works in both
  // themes — `--muted` is below `--background` in light and above it in dark.
  //
  // The width lives here and NOT on the screens' own column: the reading width of a
  // question with three options is not that of a statement with a block of code in it.
  return (
    <div
      className={cn(
        "mx-auto w-full max-w-3xl space-y-1 border border-border bg-muted/60 p-3",
        disabled && "pointer-events-none opacity-50",
      )}
    >
      {types.length > 1 ? (
        <FormStep
          index={++index}
          title={t("form.type.title")}
          hint={t("form.type.hint")}
          answered={Boolean(typeKey)}
          summary={typeSpec?.label || typeKey || t("form.type.none")}
          {...step("itemType")}
        >
          <div className="grid gap-2 sm:grid-cols-2">
            {types.map((key) => {
              const spec = profile!.item_types[key];
              const active = key === typeKey;
              return (
                <button
                  key={key}
                  type="button"
                  onClick={() => chooseType(key)}
                  className={cn(
                    CHOICE_CARD,
                    active
                      ? "border-primary bg-primary/5"
                      : "border-border hover:bg-accent/40",
                  )}
                >
                  <span className="flex items-center gap-1.5">
                    {active ? <Check className="size-3.5 text-primary" /> : null}
                    <span className="text-body font-medium">{spec.label || key}</span>
                  </span>
                  <span className="mt-0.5 block font-mono text-[12px] text-muted-foreground">
                    {key}
                  </span>
                  {/* CLIPPED AT THREE LINES, with the browser's own ellipsis. A
                      modality's description is written by the consolidator and runs to
                      several hundred characters — measured over the reference profiles,
                      329 to 781 — so three whole cards read at full length filled the
                      window before the question below them was even in view. What three
                      lines hold is what tells one modality from another: the deliverable,
                      which every one of those descriptions names in its first clause. The
                      whole text is read and corrected in step 2, «Tipos de ejercicio»,
                      which is where a modality is defined; here it is a label.

                      Never `block` beside `line-clamp-3`: the clamp works by setting
                      `display: -webkit-box`, and `block` wins in the cascade, so the
                      clamp is off and silent. */}
                  {spec.description ? (
                    <span className="mt-1 line-clamp-3 text-small text-muted-foreground">
                      {spec.description}
                    </span>
                  ) : null}
                </button>
              );
            })}
          </div>
        </FormStep>
      ) : null}

      <FormStep
        index={++index}
        title={t("form.practise.title")}
        hint={t("form.practise.hint")}
        answered={chosen}
        summary={[
          state.concepts.join(" · ") || t("form.practise.none"),
          restricting ? curriculumSummary : null,
        ]
          .filter(Boolean)
          .join(" · ")}
        {...step("concepts")}
      >
        {/* How far the class has got comes BEFORE choosing the targets and in the same
            step: it is the first half of one question — the ground first, then the target
            inside it — and folded into a later section it was normally never found.

            A box of its own and not a loose row: what separates it from the big button
            below is that it BOUNDS rather than chooses, and without a border the two read
            as two controls of one rank.

            There is no switch — the curriculum is in force when it holds concepts. A switch
            allows two states that say nothing ("restricted" with nothing ticked, and a
            ticked list turned off) and both send `[]`. Removing the last pill is what lifts
            the restriction. */}
        <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-3">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <span className="text-micro font-condensed uppercase text-muted-foreground">
              {t("form.taught.name")}
            </span>
            <span className="text-body font-medium">{t("form.taught.title")}</span>
            <span
              className={cn(
                "ml-auto text-small",
                restricting ? "font-medium text-primary" : "text-muted-foreground",
              )}
            >
              {curriculumSummary}
            </span>
          </div>
          <p className="text-small text-muted-foreground">{t("form.taught.hint")}</p>
          <div className="flex flex-wrap items-center gap-2">
            <Button size="sm" variant="outline" onClick={() => setPicking("curriculum")}>
              <ListChecks />
              {t("form.taught.pick", { n: coveredCurriculum.length })}
            </Button>
            {restricting ? (
              <Button
                size="sm"
                variant="ghost"
                onClick={() => patch({ curriculum: [], usePresetCurriculum: false })}
              >
                {t("form.outside.lift")}
              </Button>
            ) : null}
          </div>
          {state.curriculum.length > 0 ? (
            <ChosenConcepts
              names={state.curriculum}
              colourFor={colourFor}
              onRemove={(name) =>
                patch({ curriculum: state.curriculum.filter((c) => c !== name) })
              }
              empty=""
            />
          ) : null}
        </div>

        {/* The correction and not the wall: the launch button already refuses, and this is
            the way to put it right without going back to the selector. It sits beside the two
            controls that produce it, which is where it can be acted on. */}
        {outsideCurriculum.length > 0 ? (
          <Alert tone="attention" title={t("form.outside.title")}>
            <p>{t("form.outside.body", { names: outsideCurriculum.join(", ") })}</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                onClick={() => {
                  const drop = new Set(outsideCurriculum);
                  patch({ concepts: state.concepts.filter((c) => !drop.has(c)) });
                }}
              >
                {plural("form.outside.drop", outsideCurriculum.length)}
              </Button>
              <Button
                size="sm"
                variant="ghost"
                onClick={() => patch({ curriculum: [], usePresetCurriculum: false })}
              >
                {t("form.outside.lift")}
              </Button>
            </div>
          </Alert>
        ) : null}

        <div className="flex flex-wrap items-center justify-center gap-2">
          <Button size="lg" variant="outline" onClick={() => setPicking("concepts")}>
            <ListChecks />
            {t("form.practise.pick", { n: state.concepts.length })}
          </Button>
          {state.concepts.length > 1 ? (
            <Button size="sm" variant="ghost" onClick={() => patch({ concepts: [] })}>
              {t("form.practise.clear")}
            </Button>
          ) : null}
        </div>

        <ChosenConcepts
          names={state.concepts}
          colourFor={colourFor}
          onRemove={(name) =>
            patch({ concepts: state.concepts.filter((c) => c !== name) })
          }
          empty={t("form.practise.empty")}
          centred
        />

        {/* The chosen topics against what the bank can illustrate. It survives the filter
            becoming fixed because a commission can still be RESTORED with topics that have
            no exemplar left — "generate more like this one" over a bank that has changed —
            and nothing else on the screen says the batch will be written with no example
            to imitate. */}
        {wholeBatchZeroShot ? (
          <p className="flex items-start gap-1.5 text-small text-attention">
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
            {exemplarType
              ? t("form.zeroShot.wholeBatchType", { type: typeLabel })
              : t("form.zeroShot.wholeBatch")}
          </p>
        ) : zeroShot.length > 0 ? (
          <p className="text-small text-muted-foreground">
            {t("form.zeroShot.butOthers", {
              lead: exemplarType
                ? t("form.zeroShot.noneOfType")
                : t("form.zeroShot.noneOwn"),
              names: zeroShot.join(", "),
            })}
          </p>
        ) : null}

        {given.length > 0 || forbidden.length > 0 ? (
          <div className="space-y-2 rounded-lg border border-dashed border-border p-2.5">
            <p className="text-small text-muted-foreground">{t("form.graphSays")}</p>
            <ConceptTrack
              tone="given"
              icon={<Check className="size-3" />}
              label={t("form.given")}
              concepts={given}
            />
            <ConceptTrack
              tone="forbidden"
              icon={<Ban className="size-3" />}
              label={t("form.forbidden")}
              concepts={forbidden}
            />
          </div>
        ) : null}
      </FormStep>

      {chosen && asksDifficulty ? (
        <FormStep
          index={++index}
          title={t("form.difficulty.title")}
          hint={t("form.difficulty.hint")}
          answered={state.decisions[difficultyField!] !== undefined}
          summary={
            state.decisions[difficultyField!] === undefined
              ? t("form.difficulty.any")
              : readableValue(String(state.decisions[difficultyField!]))
          }
          {...step("difficulty")}
        >
          <DifficultyChoice
            levels={difficultyLevels}
            description={typeSpec!.fields[difficultyField!]?.description}
            value={state.decisions[difficultyField!]}
            onChange={(next) => {
              patch({ decisions: { ...state.decisions, [difficultyField!]: next } });
              if (next !== undefined) advance("difficulty");
            }}
          />
        </FormStep>
      ) : null}

      {chosen && decided.length > 0 ? (
        <FormStep
          index={++index}
          title={
            decided.length === 1
              ? t("form.decisions.titleOne")
              : t("form.decisions.titleMany")
          }
          hint={t("form.decisions.hint")}
          answered={decided.some((field) => state.decisions[field] !== undefined)}
          summary={decisionSummary}
          {...step("decisions")}
        >
          {decided.map((field) => {
            const spec = typeSpec!.fields[field];
            const kind = baseType(spec.schema);
            const discrete = kind === "enum" || kind === "boolean";
            return (
              <DecisionField
                key={field}
                name={field}
                spec={spec}
                value={state.decisions[field]}
                onChange={(next) => {
                  const decisions = { ...state.decisions, [field]: next };
                  patch({ decisions });
                  if (
                    discrete &&
                    next !== undefined &&
                    decided.every((name) => decisions[name] !== undefined)
                  ) {
                    advance("decisions");
                  }
                }}
              />
            );
          })}
        </FormStep>
      ) : null}


      {/* "Instrucciones adicionales": the optional half, folded and after the required
          one. The disclosure is named after the one thing it holds, and says whether
          anything is set — a fold that hides a decision without saying so is where a
          decision goes to be forgotten. */}
      {chosen ? (
        <details
          // Unfolded the moment the judge refuses the text inside: the sentence has to be
          // read where the text is, and a disclosure that stays shut over it would leave
          // the locked button below pointing at nothing.
          open={blockedInstructions ? true : undefined}
          className="group rounded-xl border border-transparent open:border-border open:bg-card"
        >
          <summary className="flex cursor-pointer list-none items-center gap-2.5 px-3 py-2.5">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <PenLine className="size-3.5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-body font-medium">{t("form.instructions.title")}</span>
              <span className="mt-0.5 block truncate text-small text-muted-foreground">
                {settingsSummary}
              </span>
            </span>
            <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
          </summary>
          <div className="space-y-4 px-3 pb-3">
          {/* What the class has covered is chosen in the concepts step and nowhere else;
              what is left here is the free text alone.

              `usePresetCurriculum` survives in the form state and is never set true by this
              screen: `fromParams` still reads it, so a row whose request carried no
              `curriculum` at all — and therefore ran against the workspace's own — is
              described faithfully and re-runs exactly as it ran. */}
          <div className="space-y-2">
            {/* The catalogue is behind the (i): it is a dozen lines of derived prose read
                once, and it belongs beside the LABEL rather than under the box, because it
                answers "what do I write here" and not "what did I write". */}
            <div className="flex items-start gap-1.5">
              <p className="min-w-0 flex-1 text-small text-muted-foreground">
                {t("form.instructions.hint")}
              </p>
              {scope.data ? (
                <InfoHint label={t("form.instructions.title")}>
                  <div className="space-y-2">
                    <div>
                      <span className="font-medium">{t("form.scope.canAsk")}</span>
                      <ul className="mt-1 space-y-0.5">
                        {scope.data.slots.map((slot) => (
                          <li key={slot.key}>
                            {slot.label} — <span className="italic">«{slot.example}»</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                    {scope.data.owners.length > 0 ? (
                      <div>
                        <span className="font-medium">{t("form.scope.decidedAbove")}</span>
                        <ul className="mt-1 space-y-0.5">
                          {scope.data.owners.map((owner) => (
                            <li key={owner.key}>
                              {owner.label} — {owner.where}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {scope.data.facts.length > 0 ? (
                      <div>
                        <span className="font-medium">{t("form.scope.subjectFixes")}</span>
                        <p className="mt-1">
                          {scope.data.facts.map((fact) => fact.value).join(" · ")}
                        </p>
                      </div>
                    ) : null}
                  </div>
                </InfoHint>
              ) : null}
            </div>
            <Textarea
              aria-label={t("form.instructions.title")}
              value={state.instructions}
              maxLength={MAX_INSTRUCTIONS}
              onChange={(event) => patch({ instructions: event.target.value })}
              className={cn("min-h-20", blockedInstructions && "border-destructive")}
            />
            <div className="flex items-center gap-2">
              <span className="ml-auto text-small nums text-muted-foreground">
                {state.instructions.length}/{MAX_INSTRUCTIONS}
              </span>
            </div>

            {blockedInstructions ? (
              <Alert tone="danger" title={t("form.instructions.blocked")}>
                <p>{blockedInstructions}</p>
              </Alert>
            ) : null}
          </div>
          </div>
        </details>
      ) : null}
      {chosen ? (
        <div className="animate-slide-up space-y-3 rounded-xl border border-border bg-card p-3 shadow-sm">
          {variant === "generate" ? (
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-body font-medium">{t("form.howMany")}</span>
              <Count value={state.n} onChange={(n) => patch({ n })} />
              {state.n > 1 ? (
                <Badge variant="outline">{t("form.noRepeat")}</Badge>
              ) : null}
            </div>
          ) : null}

          {/* Before the effort and never after it: which levels exist, which are worth a
              warning, and whether the slider is drawn at all are properties of the model
              just chosen, so choosing it afterwards silently re-clamps what was just set.
              Nothing is drawn with a single model on offer.

              Not in the evaluation variant: the writer of a comparison's two local
              proposals is the installation's (`evaluation.local_model`), never the
              evaluator's. */}
          {variant === "generate" ? (
            <ModelChoice
              offered={offered}
              remote={remoteModels}
              missing={missingModels}
              value={generationModel ?? ""}
              onChange={(model) => patch({ model })}
            />
          ) : null}

          {/* In comparison there is no switch on purpose: the reasoning mode is what is measured
              there, so the session draws it. Saying so here keeps the control's absence from reading
              as a missing checkbox. */}
          {variant === "generate" ? (
            <div className="space-y-1.5 rounded-lg border border-border bg-muted/30 px-2.5 py-2">
              {/* WHO WRITES IT, and ONLY when the chooser above is not drawn: with two on
                  offer the selected card already names this one a centimetre up, and the
                  two would be the same string twice. With ONE offered there is no card at
                  all, and this is the only place in the whole application where the writer
                  is named — which is why it sits outside the slider's guard rather than
                  inside it, where `gemma-4-31b` (locked effort, and the first of the
                  shipped list) went unnamed everywhere. It reads as the badge in "Mis
                  variantes" does, same icon and same `modelLabel`: the same fact before
                  the run and after it. */}
              {generationModel && offered.length < 2 ? (
                <div className="flex flex-wrap items-center gap-x-1.5 text-small text-muted-foreground">
                  <Cpu className="size-3.5 shrink-0" />
                  <span>{t("form.model.writes")}</span>
                  <span className="font-medium text-foreground" title={generationModel}>
                    {modelLabel(generationModel)}
                  </span>
                </div>
              ) : null}
              <div className="flex flex-wrap items-center gap-2">
                <Switch checked={state.think} onCheckedChange={(think) => patch({ think })}>
                  <span className="flex items-center gap-1.5 text-body font-medium">
                    <Brain className="size-3.5" />
                    {t("form.think.short")}
                  </span>
                </Switch>
                <span className="ml-auto text-[12px] nums text-muted-foreground">
                  {/* The level is named whenever anybody has decided it — the slider here,
                      or "Modelos generadores" for a locked model. What reads plain is the
                      one state where nothing has: locked with no level declared, which the
                      engine resolves. */}
                  {state.think
                    ? adjustable || locked
                      ? t("form.think.on", { level: t(EFFORT_LABELS[effort]).toLowerCase() })
                      : t("form.think.onPlain")
                    : t("form.think.off")}
                </span>
              </div>
              {/* The slider only where it changes the answer, and which models those are is
                  the installation's (`generation.fixed_effort`): on a model measured to
                  answer the same at every level it offers a decision and then explains that
                  it makes none. The server has the last word on what is sent, the panel
                  editing both lists while a job sits in the queue. */}
              {state.think && adjustable ? (
                <EffortSlider
                  levels={policy.levels}
                  value={effort}
                  onChange={(level) => patch({ effort: level })}
                />
              ) : null}
              {state.think && warning ? (
                <Alert tone="attention" title={t("form.think.highEffort")}>
                  <p>{t(warning)}</p>
                </Alert>
              ) : null}
            </div>
          ) : null}

          {footnote}

          {problems.some((p) => p !== SILENT_OUTSIDE) ? (
            <ul className="space-y-1 text-small text-destructive">
              {problems
                .filter((problem) => problem !== SILENT_OUTSIDE)
                .map((problem) => (
                  <li key={problem}>· {problem}</li>
                ))}
            </ul>
          ) : null}

          {error ? <p className="text-small text-destructive">{error}</p> : null}

          {/* The judge's refusal locks the button, and says so beside it: the full sentence
              is in the instructions step, this is the one line that says why nothing
              happens here and what lifts it. */}
          {blockedInstructions ? (
            <p className="text-small text-destructive">{t("form.instructions.blockedLaunch")}</p>
          ) : null}

          {running ? (
            <CancelButton
              run={run}
              size="default"
              className="w-full"
              label={
                variant === "evaluation"
                  ? t("form.cancelComparison")
                  : t("form.cancelGeneration")
              }
            />
          ) : (
            <Button
              className="w-full"
              disabled={problems.length > 0 || pending || disabled || Boolean(blockedInstructions)}
              title={blockedInstructions ?? undefined}
              onClick={onLaunch}
            >
              {pending ? <Spinner /> : variant === "evaluation" ? <Scale /> : <Play />}
              {launchLabel ??
                (variant === "evaluation"
                  ? t("form.compare")
                  : plural("form.generateItems", state.n))}
            </Button>
          )}
        </div>
      ) : null}

      {/* The concepts the bank can illustrate are what the selector opens onto, and the
          rest is one switch away. The scope lives in the selector's own header and resets
          on every opening; in the default scope a prerequisite with nothing to imitate is
          not drawn either. A concept chosen without an example is what the zero-shot notice
          in this step is about. */}
      <ConceptSelector
        title={t("form.practise.title")}
        concepts={concepts}
        graph={graph}
        selected={state.concepts}
        onChange={(next) => patch({ concepts: next })}
        implied={implied}
        restrictTo={activeCurriculum}
        onlyWithExemplars
        exemplarType={exemplarType}
        open={picking === "concepts"}
        onClose={() => setPicking(null)}
        onConfirm={() => {
          setPicking(null);
          // An empty selection answers nothing, and one that contradicts the curriculum
          // above it is explained by the notice INSIDE this step — collapsing it would hide
          // the only explanation there is.
          if (state.concepts.length > 0 && !hasOutside(state.concepts)) advance("concepts");
        }}
        confirmLabel={t("form.confirmContinue")}
      />

      {/* No `restrictTo`: a curriculum is declared whole and nothing narrows it. `implied`
          marks what the ticked coverage rests on, and here the mark COUNTS — the list in
          force is `coveredCurriculum`. `allowNonTaggable`, because a non-taggable concept
          can perfectly well have been taught; a target, being what an item is ABOUT, is the
          one that must stay taggable. */}
      <ConceptSelector
        title={t("form.taught.title")}
        concepts={concepts}
        graph={graph}
        selected={state.curriculum}
        onChange={(next) => patch({ curriculum: next })}
        implied={impliedCurriculum}
        allowNonTaggable
        open={picking === "curriculum"}
        onClose={() => setPicking(null)}
        onConfirm={() => setPicking(null)}
        confirmLabel={t("form.confirmContinue")}
      />
    </div>
  );
}
