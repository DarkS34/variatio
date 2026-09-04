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
  X,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { ConceptSelector } from "@/components/ConceptSelector";
import { Badge } from "@/components/ui/badge";
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
} from "./effort";
import { EffortSlider } from "./EffortSlider";
import { FormStep } from "./FormStep";
import { ModelChoice } from "./ModelChoice";
import { modelLabel } from "./models";
import { adjacency, covered, posteriors, priors } from "./prerequisites";
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

  // WHICH MODEL WRITES IT IS THE COMMISSION'S AGAIN (2026-09-01, explicit user request,
  // reversing the removal of the same morning). The installation still decides everything
  // AROUND the choice, in «Configuración → Modelos generadores»: which models are on offer,
  // which of them is the default, and — new the same day — which of them let their effort
  // be adjusted at all. Offering exactly one is what makes the chooser disappear, so an
  // installation that wants to decide still does, without this screen changing shape.
  //
  // It is read before the effort because the effort depends on it: which levels a family
  // implements and which of them is worth a warning are the model's. Every read is
  // defensive — an API older than this bundle sends no `offered` and no `fixed_effort`, and
  // the screen degrades to «the installation decides» with the full scale, never to blank.
  const health = useHealth();
  const offered = health.data?.models.offered ?? NONE;
  const remoteModels = health.data?.models.remote ?? NONE;
  const missingModels = health.data?.models.missing ?? NONE;
  const fixedEffort = health.data?.models.fixed_effort ?? NONE;
  // The first offered one is what the server resolves an absent `model` to, so it is what
  // the screen has to name while nobody has chosen. A stored choice the installation has
  // stopped offering is not one: the panel edits that list while this form is open.
  const generationModel =
    state.model && offered.includes(state.model) ? state.model : offered[0];
  const policy = effortPolicy(generationModel);
  const effort = clampEffort(state.effort, policy);
  const warning = effortWarning(effort, policy);
  // Whether the slider is offered for THIS model. A measurement, and the installation's to
  // record: see `generation.fixed_effort`.
  const adjustable = effortAdjustable(generationModel, fixedEffort);

  // Same reconciliation the curriculum preset gets, and for the same reason: a value the
  // form can no longer show must not be what the request carries. The panel edits the
  // offered list while this form sits open.
  useEffect(() => {
    if (state.model && offered.length > 0 && !offered.includes(state.model)) {
      patch({ model: null });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state.model, offered]);

  // The curriculum that will actually be in force, resolved exactly as the server resolves
  // it. An empty list is NOT a restriction there (`if curriculum:`), and it is truthy here,
  // so it is collapsed to null now rather than at each of the three places that read it.
  //
  // WHAT IS TICKED IS CLOSED DOWNWARDS (2026-09-04, explicit user request): covering «if»
  // covers «Condición lógica» and what that rests on, exactly as the target selector marks
  // a chosen concept's prerequisites. `server/curriculum.resolve` closes the same list
  // before the generator reads it, so what this form counts, bounds the targets with and
  // draws as given is what will run; `state.curriculum` keeps only the picks, which is
  // what lets the selector MARK the rest instead of drawing it as chosen.
  const coveredCurriculum = useMemo(
    () => covered(graphAdjacency, state.curriculum),
    [graphAdjacency, state.curriculum],
  );
  const activeCurriculum = useMemo(() => {
    if (!state.useCurriculum) return null;
    const list = state.usePresetCurriculum ? [] : coveredCurriculum;
    return list.length > 0 ? list : null;
  }, [state.useCurriculum, state.usePresetCurriculum, coveredCurriculum]);

  const priorClosure = useMemo(
    () => (graphAdjacency && chosen ? priors(graphAdjacency, state.concepts) : []),
    [graphAdjacency, state.concepts, chosen],
  );
  const posteriorClosure = useMemo(
    () => (graphAdjacency && chosen ? posteriors(graphAdjacency, state.concepts) : []),
    [graphAdjacency, state.concepts, chosen],
  );

  // The MARK is the bare closure, and independent of both switches: it says where a concept
  // sits relative to the targets, which is a statement about the graph and not about
  // coverage. It stopped being a LOCK on 2026-09-04 (explicit user request) — a prerequisite
  // chosen as a target is a commission the generator already computes, because
  // `KnowledgeGraph._closure` subtracts the targets from what it returns.
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
    chosen && asksDifficulty ? "difficulty" : null,
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
  // under the previous one has to pass the same filter the selector applies.
  const chooseType = (key: string) => {
    const kept = state.concepts.filter((name) => {
      const concept = byName.get(name);
      return Boolean(concept && hasExemplars(concept, key));
    });
    patch({ itemType: key, decisions: {}, concepts: kept });
    advance("itemType");
  };

  // Concepts that the curriculum leaves out. Since the curriculum moved ABOVE the targets
  // (2026-09-02) the selector's `restrictTo` keeps it from arising the normal way round,
  // so what is left is NARROWING the curriculum after choosing — and a commission restored
  // from an older row. It is a correction and not a wall: the launch button still refuses,
  // and the offer to drop them is one click.
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
    // Este entra en la lista para que el botón se niegue, pero NO se imprime: el aviso
    // del paso de conceptos dice lo mismo y además ofrece las dos formas de arreglarlo,
    // así que repetirlo junto al botón es el mismo error dos veces en la misma pantalla.
    if (outsideCurriculum.length > 0) found.push(SILENT_OUTSIDE);
    if (state.instructions.trim().length > MAX_INSTRUCTIONS)
      found.push(t("form.problem.tooLong", { max: MAX_INSTRUCTIONS }));
    return found;
  }, [types.length, typeKey, state.concepts, outsideCurriculum, state.instructions, t]);

  const decisionSummary = decided
    .map((field) => describeDecision(field, state.decisions[field], t))
    .join(" · ");

  const curriculumSummary = curriculumLabel(state, null, tr);

  // What «Ajustes» says while it is shut: nothing set reads as «nada»; anything set is
  // named, because a disclosure that hides a decision without saying so is where a
  // decision goes to be forgotten. The curriculum left this summary with the control
  // itself (2026-09-02) — it is answered in the concepts step and reported in its line.
  const settingsSummary = state.instructions.trim()
    ? t("form.settings.withInstructions")
    : t("form.settings.none");

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
                  <span className="mt-0.5 block font-mono text-[12px] text-muted-foreground">
                    {key}
                  </span>
                  {spec.description ? (
                    <span className="mt-1 block text-body text-muted-foreground">
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
          state.useCurriculum && activeCurriculum ? curriculumSummary : null,
        ]
          .filter(Boolean)
          .join(" · ")}
        {...step("concepts")}
      >
        {/* HASTA DÓNDE HA LLEGADO LA CLASE VA ANTES DE ELEGIR LOS OBJETIVOS, Y EN EL
            MISMO PASO (2026-09-02, petición explícita). Vivía plegado en «Ajustes», que
            está DESPUÉS: se decidía qué practicar y sólo entonces, una sección más abajo,
            se podía acotar el temario que sostiene esa elección — y lo normal era no
            encontrarlo. Aquí es la primera mitad de una sola pregunta: primero el terreno,
            después el objetivo dentro de él.

            Es una caja propia y no una fila suelta: lo que la separa del botón grande de
            debajo es que acota, no elige, y sin borde las dos cosas se leerían como una
            lista de dos controles del mismo rango. */}
        <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-3">
          <Switch
            checked={state.useCurriculum}
            onCheckedChange={(useCurriculum) => patch({ useCurriculum })}
          >
            <span className="text-body font-medium">{t("form.taught.restrict")}</span>
          </Switch>
          <p className="text-small text-muted-foreground">{t("form.taught.hint")}</p>
          {state.useCurriculum ? (
            <Button size="sm" variant="outline" onClick={() => setPicking("curriculum")}>
              <ListChecks />
              {t("form.taught.pick", { n: coveredCurriculum.length })}
            </Button>
          ) : null}
        </div>

        {/* La corrección, no el muro: el botón de lanzar ya se niega, y aquí está la forma
            de arreglarlo sin volver al selector. Vive junto a los dos controles que la
            producen, que es donde se puede actuar sobre ella. */}
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
            no exemplar left — «Generar más como esta» over a bank that has changed since —
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


      {/* «INSTRUCCIONES ADICIONALES»: LO OPCIONAL, PLEGADO Y DESPUÉS DE LO OBLIGATORIO.

          Se llamaba «Ajustes» y guardaba dos cosas, el currículo y el texto libre. El
          currículo se fue al paso de conceptos (2026-09-02, petición explícita), así que
          un nombre genérico para una sola cosa era una etiqueta que no decía cuál: la
          divulgación se llama ahora como lo que contiene, y el rótulo de dentro se fue con
          el cambio para no decir lo mismo dos veces a un centímetro.

          Sigue detrás de una divulgación que dice si hay algo puesto, porque es opcional y
          va después de la única pregunta obligatoria de la pantalla. */}
      {chosen ? (
        <details className="group rounded-xl border border-transparent open:border-border open:bg-card">
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
          {/* WHAT THE CLASS HAS COVERED IS CHOSEN IN THE CONCEPTS STEP AND NOWHERE ELSE
              (2026-09-02, explicit user request). It used to be the first half of this
              disclosure; what is left here is the free text alone.

              `usePresetCurriculum` survives in the form state and is never set true by
              this screen: `fromParams` still reads it, so a row recorded before the
              workspace curriculum stopped being offered — whose request carried no
              `curriculum` at all and therefore ran against the workspace's own — is still
              described faithfully in the collapsed bar and re-runs exactly as it ran. */}
          <div className="space-y-2">
            {/* THE CATALOGUE IS BEHIND THE (i) (2026-09-01, explicit user request).
                What the free text may legitimately ask for — the four slots, the controls
                that already decide the rest, and the three facts the subject fixes — is a
                dozen lines of derived prose, and it sat UNDER the box as a permanent block
                twice the height of the field it explains. It is read once, which is what
                the hint is for; and it belongs beside the label rather than under the box,
                because it answers «what do I write here», not «what did I write». */}
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

          {/* BEFORE THE EFFORT AND NOT AFTER IT: which levels exist, which of them is worth
              a warning, and whether the slider is drawn at all are properties of the model
              that was just chosen, so choosing it afterwards would silently re-clamp what
              was just set. It draws nothing with a single model on offer. */}
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
                  shipped list) went unnamed everywhere. It reads as the badge in «Mis
                  variantes» does, same icon and same `modelLabel`: the same fact before
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
                  {state.think
                    ? adjustable
                      ? t("form.think.on", { level: t(EFFORT_LABELS[effort]).toLowerCase() })
                      : t("form.think.onPlain")
                    : t("form.think.off")}
                </span>
              </div>
              {/* The slider only where it changes the answer, and WHICH models those are is
                  the installation's since 2026-09-01 (`generation.fixed_effort`). On a
                  model measured to answer the same at every level, drawing it offers a
                  decision and then explains that it makes no difference. `effort` is still
                  sent — clamped to a level the engine accepts — it just stops being asked. */}
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

      {/* THE CONCEPTS THE BANK CAN ILLUSTRATE ARE WHAT THE SELECTOR OPENS ONTO, AND THE
          REST IS ONE SWITCH AWAY (2026-09-04, explicit user request, reversing the fixed
          filter of 2026-09-01). The scope lives in the selector's own header — «Con
          ejemplos» / «Todos los conceptos» — and resets to the bank's side on every opening;
          in the default scope a prerequisite that comes in locked but has nothing to
          imitate is not drawn either. A concept chosen without an example is what the
          zero-shot notice in this step is about. */}
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
          // Confirming an empty selection answers nothing: the step stays open, which is
          // where it already was. And so does a selection that CONTRADICTS the curriculum
          // chosen just above it — the launch button refuses for it and says nothing (the
          // notice inside this step is what explains it and offers the two ways out), so
          // collapsing the step here would hide the only explanation there is.
          if (state.concepts.length > 0 && !hasOutside(state.concepts)) advance("concepts");
        }}
        confirmLabel={t("form.confirmContinue")}
      />

      {/* No `restrictTo`: a curriculum is declared whole and nothing narrows it. `implied`
          marks what the ticked coverage rests on, and here the mark counts — the list in
          force is `coveredCurriculum` (2026-09-04, explicit user request). `allowNonTaggable`
          because a non-taggable concept can perfectly well have been taught, which is what
          a curriculum states — a target, being what an item is ABOUT, is the one that must
          stay taggable. */}
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
