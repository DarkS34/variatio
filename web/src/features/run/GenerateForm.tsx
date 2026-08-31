import { useQuery } from "@tanstack/react-query";
import {
  Ban,
  Brain,
  Check,
  ChevronRight,
  ListChecks,
  Minus,
  Play,
  Plus,
  Scale,
  Sliders,
  TriangleAlert,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { ConceptSelector } from "@/components/ConceptSelector";
import { Badge } from "@/components/ui/badge";
import { InfoHint } from "@/components/ui/hint";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Alert, Spinner, Switch } from "@/components/ui/misc";
import { getCurriculum } from "@/lib/api";
import { hasExemplars } from "@/lib/concepts";
import { assumedKnown, notYetTaught } from "@/lib/curriculum";
import { domainColours } from "@/lib/domains";
import { defaultTypeKey, typeKeys, userDecidedFields } from "@/lib/profile";
import type {
  CurriculumState,
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
import { EFFORT_LABELS, clampEffort, effortPolicy, effortWarning } from "./effort";
import { EffortSlider } from "./EffortSlider";
import { FormStep } from "./FormStep";
import { adjacency, posteriors, priors } from "./prerequisites";
import { CancelButton } from "@/components/CancelButton";
import type { RunView } from "@/state/runStore";

const MAX_ITEMS = 20;
// One identity for «the payload has not arrived», so the effect below is not re-run by a
// fresh `[]` on every render.
const NONE: string[] = [];
/** Mirrors config.GENERATION_INSTRUCTIONS_MAX_CHARS. */
const MAX_INSTRUCTIONS = 600;
/** Un problema que bloquea el lanzamiento y se explica en otro sitio. Ver `problems`. */
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

// The curriculum in force, in words: the form step reads it and so does the one line that
// replaces the whole form once it is collapsed. One derivation, because two of them drifted
// apart exactly where it mattered — «currículo de 0» over a request that carries `[]`, which
// is no restriction at all. `presetSize` is null when the workspace's own has not been read,
// which is the collapsed line's case: it has the state, not the query.
function curriculumLabel(
  state: FormState,
  presetSize: number | null,
  { t }: Translate,
): string {
  if (!state.useCurriculum) return t("form.curriculum.none");
  if (state.usePresetCurriculum) {
    if (presetSize === null) return t("form.curriculum.workspace");
    return presetSize > 0
      ? t("form.curriculum.workspaceN", { n: presetSize })
      : t("form.curriculum.none");
  }
  return state.curriculum.length > 0
    ? t("form.curriculum.ofN", { n: state.curriculum.length })
    : t("form.curriculum.noneChosen");
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
  for (const field of userDecidedFields(spec)) {
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

// The two lists the graph derives are read as a contrast, not as prose: one is what the
// item may lean on and the other what it may not name at all. Same shape, opposite tone.
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
          // The same two tones the curriculum view uses: what is settled behind you, and
          // what is ahead and not reachable yet. The strikethrough already carries
          // "forbidden"; the colour carries the POSITION, which is the whole thesis.
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

// What the full-screen selector left behind, read on the form itself: the overlay closes and
// its tray goes with it, so without this the answer to the question would be a number.
function ChosenConcepts({
  names,
  colourFor,
  onRemove,
  empty,
}: {
  names: string[];
  colourFor: (name: string) => string | undefined;
  onRemove: (name: string) => void;
  empty: string;
}) {
  const { t } = useT();
  if (names.length === 0) return <p className="text-body text-muted-foreground">{empty}</p>;
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      {names.map((name) => (
        <Badge key={name} variant="secondary" className="pr-1">
          <span
            className="size-1.5 shrink-0 rounded-full"
            style={{ background: colourFor(name) }}
          />
          <span className="max-w-56 truncate">{name}</span>
          <button
            type="button"
            onClick={() => onRemove(name)}
            aria-label={t("form.removeConcept", { name })}
            className="rounded-full p-0.5 hover:bg-background/60"
          >
            <X className="size-3" />
          </button>
        </Badge>
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
  // A stepper rather than a number box: emptying the box yields NaN, which compares
  // false against every bound and used to travel all the way to the server as null.
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
   *  which «Comparar tres propuestas» would misreport as one. */
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
  const [onlyWithExemplars, setOnlyWithExemplars] = useState(true);
  // What the full-screen selector is choosing: the targets, the ad-hoc curriculum, or
  // nothing. One state, because only one overlay can be open.
  const [picking, setPicking] = useState<"concepts" | "curriculum" | null>(null);
  const patch = (fields: Partial<FormState>) => onChange({ ...state, ...fields });

  // The workspace's preset curriculum. `undefined` while it loads, and its absence is what
  // decides whether the second switch is offered at all.
  const { data: preset } = useQuery<CurriculumState>({
    queryKey: workspace ? ["kg", "curriculum", workspace] : ["kg", "curriculum"],
    queryFn: () => getCurriculum(workspace),
  });

  // The restriction starts OFF whatever the workspace holds (2026-08-23, explicit user
  // request: every step starts unanswered): a preset curriculum is offered, never applied.
  // This reconciliation is deliberately NOT latched: with no preset
  // the second switch is not rendered, so leaving it on is a state nobody chose and nobody
  // can see, and it would send a request with no curriculum field — the server then resolves
  // the workspace's own, which is empty, i.e. no restriction — while the concepts picked by
  // hand right below it are silently dropped. The preset can be empty later as well as
  // sooner: the form is interactive before the query answers, and the graph's Currículo tab
  // writes this very cache entry when it saves, so emptying it there and coming back here
  // remounts this form and refetches past `staleTime` onto a preset that is now empty.
  useEffect(() => {
    if (preset && preset.concepts.length === 0 && state.usePresetCurriculum) {
      patch({ usePresetCurriculum: false });
    }
  }, [preset, state.usePresetCurriculum]);

  const types = typeKeys(profile);
  const typeKey = activeTypeKey(state, profile);
  const typeSpec = activeTypeSpec(state, profile);
  const decided = userDecidedFields(typeSpec);
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

  // WHICH MODEL WRITES IT IS NOT ASKED HERE ANY MORE (2026-09-01, explicit user request),
  // but it is still READ: which effort levels a family implements, and which of them is
  // worth a warning, are properties of the model, so the slider has to know what it is
  // sizing itself against. It is the first of `generation.models`, which is exactly what
  // the server resolves an absent `model` to. Read defensively — an API older than this
  // bundle sends no `offered`, and the slider degrades to the full scale.
  const health = useHealth();
  const offered = health.data?.models.offered ?? NONE;
  const generationModel = offered[0];
  const policy = effortPolicy(generationModel);
  const effort = clampEffort(state.effort, policy);
  const warning = effortWarning(effort, policy);

  // The curriculum that will actually be in force, resolved exactly as the server resolves
  // it. An empty list is NOT a restriction there (`if curriculum:`), and it is truthy here,
  // so it is collapsed to null now rather than at each of the three places that read it.
  const activeCurriculum = useMemo(() => {
    if (!state.useCurriculum) return null;
    const list = state.usePresetCurriculum ? (preset?.concepts ?? []) : state.curriculum;
    return list.length > 0 ? list : null;
  }, [state.useCurriculum, state.usePresetCurriculum, state.curriculum, preset]);

  const priorClosure = useMemo(
    () => (graphAdjacency && chosen ? priors(graphAdjacency, state.concepts) : []),
    [graphAdjacency, state.concepts, chosen],
  );
  const posteriorClosure = useMemo(
    () => (graphAdjacency && chosen ? posteriors(graphAdjacency, state.concepts) : []),
    [graphAdjacency, state.concepts, chosen],
  );

  // The lock is the bare closure on purpose, and independent of both switches: it says a
  // prerequisite of a target cannot itself be a target, which is a statement about targets
  // and not about coverage.
  const implied = useMemo(() => new Set(priorClosure), [priorClosure]);

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

  const withoutExemplars = useMemo(
    () =>
      concepts.filter((concept) => concept.taggable && !hasExemplars(concept, exemplarType))
        .length,
    [concepts, exemplarType],
  );
  // Anything already chosen stays on screen, so it is not part of what the filter hides.
  const hidden = withoutExemplars - zeroShot.length;

  const applyFilter = (next: boolean) => {
    setOnlyWithExemplars(next);
    if (next && zeroShot.length > 0) {
      patch({ concepts: state.concepts.filter((name) => !zeroShot.includes(name)) });
    }
  };

  // The steps actually on screen, in order. It is derived and not a constant because which
  // of them exist depends on the state: with a single modality declared there is nothing to
  // ask first, and the last two only appear once something has been chosen. It is also the
  // one place that order is written down — before this, the step after the concepts was
  // hardcoded in two more.
  // THE NUMBERED STEPS ARE THE COMMISSION, AND NOTHING OPTIONAL IS ONE OF THEM.
  // «¿Qué se ha visto ya?» used to be the second of five — optional, three levels deep —
  // in front of «¿Qué hay que practicar?», which is the only required answer and the whole
  // reason for the screen. Both optional questions live in «Ajustes» now, folded, and the
  // numbers describe the commission: modality if there is a choice, concepts, and the
  // fields the profile leaves to whoever asks.
  const steps = [
    types.length > 1 ? "itemType" : null,
    "concepts",
    chosen && decided.length > 0 ? "decisions" : null,
  ].filter((id): id is string => id !== null);

  const openStep = open === undefined ? steps[0] : open;
  const step = (id: string) => ({
    open: openStep === id,
    onOpen: () => setOpen(openStep === id ? null : id),
  });

  // Answering a step opens the next one. The rule is narrow on purpose: only a gesture that
  // leaves NOTHING else to decide in that step calls this, because collapsing a question the
  // person is still in the middle of is worse than the click it saves. Turning the curriculum
  // on is the case that proves it — it is not an answer, it opens two more.
  const advance = (from: string) => setOpen(steps[steps.indexOf(from) + 1] ?? null);

  // Changing modality changes which concepts have exemplars at all, so what was chosen
  // under the previous one has to pass the filter again — the same pruning `applyFilter`
  // does when it is switched on. With the filter off nothing is dropped: choosing a
  // concept the bank cannot illustrate is then a deliberate answer.
  const chooseType = (key: string) => {
    const kept = onlyWithExemplars
      ? state.concepts.filter((name) => {
          const concept = byName.get(name);
          return Boolean(concept && hasExemplars(concept, key));
        })
      : state.concepts;
    patch({ itemType: key, decisions: {}, concepts: kept });
    advance("itemType");
  };

  // Concepts that the curriculum, once chosen, leaves out. With the curriculum asked
  // BEFORE the concepts this could not happen — the selector restricted what was on offer
  // — and asking it after is what makes it possible. It is a correction and not a wall:
  // the launch button still refuses, and the offer to drop them is one click.
  const outsideCurriculum = useMemo(() => {
    if (!activeCurriculum) return [];
    const inside = new Set(activeCurriculum);
    return state.concepts.filter((c) => !inside.has(c));
  }, [activeCurriculum, state.concepts]);

  // Same rules the generator enforces server-side; failing here is just faster.
  const problems = useMemo(() => {
    const found: string[] = [];
    if (types.length > 1 && !typeKey) found.push(t("form.problem.itemType"));
    if (state.concepts.length === 0) found.push(t("form.problem.concepts"));
    // Este entra en la lista para que el botón se niegue, pero NO se imprime: el aviso
    // de «Ajustes» dice lo mismo y además ofrece las dos formas de arreglarlo, así que
    // repetirlo junto al botón es el mismo error dos veces en la misma pantalla.
    if (outsideCurriculum.length > 0) found.push(SILENT_OUTSIDE);
    if (state.instructions.trim().length > MAX_INSTRUCTIONS)
      found.push(t("form.problem.tooLong", { max: MAX_INSTRUCTIONS }));
    return found;
  }, [types.length, typeKey, state.concepts, outsideCurriculum, state.instructions, t]);

  const decisionSummary = decided
    .map((field) => describeDecision(field, state.decisions[field], t))
    .join(" · ");

  const curriculumSummary = curriculumLabel(state, preset ? preset.concepts.length : null, tr);

  // What «Ajustes» says while it is shut: nothing set reads as «nada»; anything set is
  // named, because a disclosure that hides a decision without saying so is where a
  // curriculum goes to be forgotten.
  const settingsSummary = (() => {
    const parts: string[] = [];
    if (state.useCurriculum && activeCurriculum) parts.push(curriculumSummary);
    if (state.instructions.trim()) parts.push(t("form.settings.withInstructions"));
    return parts.length > 0 ? parts.join(" · ") : t("form.settings.none");
  })();

  const filterLabel = exemplarType
    ? t("form.filter.ofType", { type: typeLabel })
    : t("form.filter.any");

  let index = 0;

  // THE FORM IS A SURFACE OF ITS OWN, AND NARROWER THAN THE PAGE (2026-09-01, explicit
  // user request). It used to be a bare `space-y-1` on the page's own ground, so the only
  // thing separating «the questions you answer» from «the header, the alerts and the
  // results» was vertical space. One step of tint plus a border says it in both themes —
  // `--muted` is BELOW `--background` in light and ABOVE it in dark — and it costs
  // nothing, because the open step is `bg-card` and now reads as a card ON something
  // rather than a card on the page.
  //
  // The width is here and NOT on the screens' own column: `max-w-4xl` there is the
  // reading width of a generated statement with a block of code in it, which is a
  // different measurement from the reading width of a question with three options. Both
  // screens that draw this form get the narrowing from one place.
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
                    "rounded-lg border p-2.5 text-left transition-colors",
                    active
                      ? "border-primary bg-primary/5"
                      : "border-border hover:bg-accent/40",
                  )}
                >
                  <span className="flex items-center gap-1.5">
                    {active ? <Check className="size-3.5 text-primary" /> : null}
                    <span className="text-body font-medium">{spec.label || key}</span>
                  </span>
                  <span className="mt-0.5 block font-mono text-[11px] text-muted-foreground">
                    {key}
                  </span>
                  {spec.description ? (
                    <span className="mt-1 block text-small text-muted-foreground">
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
        summary={state.concepts.join(" · ") || t("form.practise.none")}
        {...step("concepts")}
      >
        {withoutExemplars > 0 ? (
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-border bg-muted/40 px-2.5 py-2">
            <Switch checked={onlyWithExemplars} onCheckedChange={applyFilter}>
              <span className="text-small font-medium">{filterLabel}</span>
            </Switch>
            <span className="ml-auto text-[11px] nums text-muted-foreground">
              {onlyWithExemplars
                ? plural("form.hiddenNoExemplars", hidden)
                : plural("form.withoutExemplars", withoutExemplars)}
            </span>
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => setPicking("concepts")}>
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
        />

        {!onlyWithExemplars && withoutExemplars > 0 ? (
          <p className="flex items-start gap-1.5 text-small text-attention">
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
            {exemplarType
              ? t("form.zeroShot.filterOffType", { type: typeLabel })
              : t("form.zeroShot.filterOff")}
          </p>
        ) : null}

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


      {/* AJUSTES: LO OPCIONAL, PLEGADO Y DESPUÉS DE LO OBLIGATORIO.

          El currículo era el paso 2 de 5 — opcional, con tres niveles anidados — y
          estaba delante de «¿Qué hay que practicar?», que es el único obligatorio y el
          motivo de la pantalla. Quien solo quiere dos ejercicios de recursividad tenía
          que leer y descartar una pregunta de tres niveles antes de llegar a la suya.

          No desaparece nada: los dos siguen aquí, con las mismas preguntas y el mismo
          estado, detrás de una divulgación que dice cuántos hay puestos. Y el currículo
          aplicado DESPUÉS ya no puede restringir el selector, así que `problems` avisa
          de los conceptos que quedan fuera y ofrece quitarlos de un clic. */}
      {chosen ? (
        <details className="group rounded-xl border border-transparent open:border-border open:bg-card">
          <summary className="flex cursor-pointer list-none items-center gap-2.5 px-3 py-2.5">
            <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-muted text-muted-foreground">
              <Sliders className="size-3.5" />
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-body font-medium">{t("form.settings.title")}</span>
              <span className="mt-0.5 block truncate text-small text-muted-foreground">
                {settingsSummary}
              </span>
            </span>
            <ChevronRight className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-90" />
          </summary>
          <div className="space-y-4 px-3 pb-3">
          <div className="space-y-2">
            <p className="text-body font-medium">{t("form.taught.title")}</p>
          <div className="flex flex-wrap items-center gap-2">
            <Switch
              checked={state.useCurriculum}
              onCheckedChange={(useCurriculum) => {
                patch({ useCurriculum });
              }}
            >
              <span className="text-body font-medium">{t("form.taught.restrict")}</span>
            </Switch>
          </div>

          {state.useCurriculum ? (
            <div className="ml-6 space-y-2">
              {preset && preset.concepts.length > 0 ? (
                <div className="flex flex-wrap items-center gap-2">
                  <Switch
                    checked={state.usePresetCurriculum}
                    onCheckedChange={(usePresetCurriculum) => {
                      patch({ usePresetCurriculum });
                    }}
                  >
                    <span className="text-body">
                      {t("form.taught.usePreset", { n: preset.concepts.length })}
                    </span>
                  </Switch>
                </div>
              ) : (
                <p className="text-small text-muted-foreground">{t("form.taught.noPreset")}</p>
              )}
              {!state.usePresetCurriculum || !preset?.concepts.length ? (
                <Button size="sm" variant="outline" onClick={() => setPicking("curriculum")}>
                  <ListChecks />
                  {t("form.taught.pick", { n: state.curriculum.length })}
                </Button>
              ) : null}
            </div>
          ) : null}
          </div>
          <div className="space-y-2">
            {/* THE CATALOGUE IS BEHIND THE (i) (2026-09-01, explicit user request).
                What the free text may legitimately ask for — the four slots, the controls
                that already decide the rest, and the three facts the subject fixes — is a
                dozen lines of derived prose, and it sat UNDER the box as a permanent block
                twice the height of the field it explains. It is read once, which is what
                the hint is for; and it belongs beside the label rather than under the box,
                because it answers «what do I write here», not «what did I write». */}
            <div className="flex items-center gap-1.5">
              <p className="text-body font-medium">{t("form.instructions.title")}</p>
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
              placeholder={t("form.instructions.placeholder")}
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
            {/* La corrección, no el muro: el botón de lanzar ya se niega, y aquí está la
                forma de arreglarlo sin volver al selector. */}
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
                  <Button size="sm" variant="ghost" onClick={() => patch({ useCurriculum: false })}>
                    {t("form.outside.lift")}
                  </Button>
                </div>
              </Alert>
            ) : null}
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

          {/* In comparison there is no switch on purpose: the reasoning mode is what is measured
              there, so the session draws it. Saying so here keeps the control's absence from reading
              as a missing checkbox. */}
          {variant === "generate" ? (
            <div className="space-y-1.5 rounded-lg border border-border bg-muted/30 px-2.5 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <Switch checked={state.think} onCheckedChange={(think) => patch({ think })}>
                  <span className="flex items-center gap-1.5 text-body font-medium">
                    <Brain className="size-3.5" />
                    {t("form.think.short")}
                  </span>
                </Switch>
                <span className="ml-auto text-[11px] nums text-muted-foreground">
                  {state.think
                    ? policy.effortMatters === false
                      ? t("form.think.onPlain")
                      : t("form.think.on", { level: t(EFFORT_LABELS[effort]).toLowerCase() })
                    : t("form.think.off")}
                </span>
              </div>
              {/* The slider only where it changes the answer. On a family whose own note
                  says the three levels behave alike, drawing it offers a decision and
                  explains underneath that it makes no difference. `effort` is still sent
                  — clamped to a level the engine accepts — it just stops being asked. */}
              {state.think && policy.effortMatters !== false ? (
                <div className="flex flex-wrap items-end gap-x-3 gap-y-1">
                  <EffortSlider
                    levels={policy.levels}
                    value={effort}
                    onChange={(level) => patch({ effort: level })}
                  />
                  {/* The one place the writer is named at all, now that nobody picks it.
                      It is not a control: it is what the effort beside it applies to. */}
                  {generationModel ? (
                    <span className="font-mono text-[11px] text-muted-foreground">
                      {generationModel}
                    </span>
                  ) : null}
                </div>
              ) : null}
              <p className="text-small text-muted-foreground">
                {state.think ? t("form.think.onBody") : t("form.think.offBody")}
              </p>
              {state.think && policy.noteKey ? (
                <p className="text-small text-muted-foreground">{t(policy.noteKey)}</p>
              ) : null}
              {state.think && warning ? (
                <Alert tone="attention" title={t("form.think.highEffort")}>
                  <p>{t(warning)}</p>
                </Alert>
              ) : null}
            </div>
          ) : (
            <p className="flex items-start gap-1.5 text-small text-muted-foreground">
              <Brain className="mt-0.5 size-3.5 shrink-0" />
              {t("form.think.comparison")}
            </p>
          )}

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
              disabled={problems.length > 0 || pending || disabled}
              onClick={onLaunch}
            >
              {pending ? <Spinner /> : variant === "evaluation" ? <Scale /> : <Play />}
              {launchLabel ??
                (variant === "evaluation"
                  ? t("form.compareThree")
                  : plural("form.generateItems", state.n))}
            </Button>
          )}
        </div>
      ) : null}

      <ConceptSelector
        title={t("form.practise.title")}
        concepts={concepts}
        graph={graph}
        selected={state.concepts}
        onChange={(next) => patch({ concepts: next })}
        implied={implied}
        restrictTo={activeCurriculum}
        onlyWithExemplars={onlyWithExemplars}
        onShowWithoutExemplars={() => applyFilter(false)}
        exemplarType={exemplarType}
        open={picking === "concepts"}
        onClose={() => setPicking(null)}
        onConfirm={() => {
          setPicking(null);
          // Confirming an empty selection answers nothing: the step stays open, which is
          // where it already was.
          if (state.concepts.length > 0) advance("concepts");
        }}
        confirmLabel={t("form.confirmContinue")}
      />

      {/* Neither `implied` nor `restrictTo`: a curriculum is declared whole and nothing
          narrows it. `allowNonTaggable` because a non-taggable concept can perfectly well
          have been taught, which is what a curriculum states — a target, being what an item
          is ABOUT, is the one that must stay taggable. */}
      <ConceptSelector
        title={t("form.taught.title")}
        concepts={concepts}
        graph={graph}
        selected={state.curriculum}
        onChange={(next) => patch({ curriculum: next })}
        allowNonTaggable
        showExemplarCount={false}
        open={picking === "curriculum"}
        onClose={() => setPicking(null)}
        onConfirm={() => setPicking(null)}
        confirmLabel={t("form.confirmContinue")}
      />
    </div>
  );
}
