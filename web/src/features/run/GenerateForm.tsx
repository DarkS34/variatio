import { useQuery } from "@tanstack/react-query";
import {
  Ban,
  Brain,
  Check,
  ListChecks,
  Minus,
  Play,
  Plus,
  Scale,
  TriangleAlert,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";

import { ConceptSelector } from "@/components/ConceptSelector";
import { Badge } from "@/components/ui/badge";
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
  GenerateParams,
  GraphView,
  ItemTypeSpec,
  KgConcept,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { useScope } from "@/state/queries";

import { DecisionField, describeDecision } from "./DecisionField";
import { FormStep } from "./FormStep";
import { adjacency, posteriors, priors } from "./prerequisites";

const MAX_ITEMS = 20;
/** Mirrors config.GENERATION_INSTRUCTIONS_MAX_CHARS. */
const MAX_INSTRUCTIONS = 600;

export interface FormState {
  n: number;
  concepts: string[];
  /** null means "not chosen yet"; it resolves on its own only when the profile declares a
   *  single modality, because then there is nothing to choose. */
  itemType: string | null;
  /** Off = no restriction. */
  useCurriculum: boolean;
  /** Only counts with `useCurriculum`. On = the workspace's own. */
  usePresetCurriculum: boolean;
  /** The ad-hoc one; only counts with `useCurriculum` on and `usePresetCurriculum` off. */
  curriculum: string[];
  decisions: Record<string, unknown>;
  instructions: string;
  /** Only the "generate" variant reads it: an evaluation draws its own, at random. */
  think: boolean;
}

export const EMPTY_FORM: FormState = {
  n: 2,
  concepts: [],
  itemType: null,
  useCurriculum: false,
  usePresetCurriculum: true,
  curriculum: [],
  decisions: {},
  instructions: "",
  think: true,
};

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

export function toParams(state: FormState): GenerateParams {
  const params: GenerateParams = { n: state.n, concepts: state.concepts, think: state.think };
  if (state.itemType) params.item_type = state.itemType;
  const fixed: Record<string, unknown> = {};
  for (const [field, value] of Object.entries(state.decisions)) {
    if (value === undefined || value === null) continue;
    if (typeof value === "string" && !value.trim()) continue;
    fixed[field] = value;
  }
  if (Object.keys(fixed).length > 0) params.fixed = fixed;
  // Absent and `[]` are NOT the same request: `server/curriculum.resolve` returns the
  // parameter unchanged whenever it is given — the empty list included, which is how one
  // says "no restriction" — and only falls back to the workspace's stored curriculum when
  // nothing arrives at all. So the preset case sends no field, not an empty one.
  if (!state.useCurriculum) params.curriculum = [];
  else if (!state.usePresetCurriculum) params.curriculum = state.curriculum;
  if (state.instructions.trim()) params.instructions = state.instructions.trim();
  return params;
}

// The exact inverse of `toParams`, and it has to stay its mirror: it is what lets a screen
// describe the commission that RAN instead of the one on screen. A job carries its own
// parameters; the form state does not survive a reload or a visit to another screen, so the
// two drift apart and the collapsed bar ends up quoting the empty form's defaults over the
// results of a run that asked for something else.
export function fromParams(params: Record<string, unknown>): FormState {
  const curriculum = Array.isArray(params.curriculum)
    ? (params.curriculum as string[])
    : undefined;
  return {
    ...EMPTY_FORM,
    // `int(params.get("n") or 1)`, as the handler reads it.
    n: Number(params.n) || 1,
    concepts: Array.isArray(params.concepts) ? [...(params.concepts as string[])] : [],
    itemType: (params.item_type as string) || null,
    // Absent is the workspace's own and `[]` is «sin restricción», exactly as the server
    // resolves them.
    useCurriculum: curriculum === undefined || curriculum.length > 0,
    usePresetCurriculum: curriculum === undefined,
    curriculum: curriculum ? [...curriculum] : [],
    decisions: { ...((params.fixed as Record<string, unknown>) ?? {}) },
    instructions: (params.instructions as string) ?? "",
    think: params.think !== false,
  };
}

// The curriculum in force, in words: the form step reads it and so does the one line that
// replaces the whole form once it is collapsed. One derivation, because two of them drifted
// apart exactly where it mattered — «currículo de 0» over a request that carries `[]`, which
// is no restriction at all. `presetSize` is null when the workspace's own has not been read,
// which is the collapsed line's case: it has the state, not the query.
function curriculumLabel(state: FormState, presetSize: number | null): string {
  if (!state.useCurriculum) return "Sin restricción de currículo";
  if (state.usePresetCurriculum) {
    if (presetSize === null) return "Currículo del workspace";
    return presetSize > 0
      ? `Currículo del workspace (${presetSize} conceptos)`
      : "Sin restricción de currículo";
  }
  return state.curriculum.length > 0
    ? `Currículo de ${state.curriculum.length} conceptos`
    : "Sin conceptos elegidos todavía";
}

export function summarize(state: FormState, profile: ExemplarsProfile | null): string {
  const spec = activeTypeSpec(state, profile);
  const parts = [`${state.n} ítem${state.n === 1 ? "" : "s"}`];
  if (spec && typeKeys(profile).length > 1) parts.push(spec.label || activeTypeKey(state, profile)!);
  parts.push(state.concepts.join(" · ") || "sin conceptos");
  for (const field of userDecidedFields(spec)) {
    const value = state.decisions[field];
    if (value !== undefined && value !== null && value !== "") parts.push(String(value));
  }
  const label = curriculumLabel(state, null);
  parts.push(label.charAt(0).toLowerCase() + label.slice(1));
  if (state.instructions.trim()) parts.push("con instrucciones");
  if (!state.think) parts.push("sin razonamiento previo");
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
            aria-label={`Quitar ${name}`}
            className="rounded-full p-0.5 hover:bg-background/60"
          >
            <X className="size-3" />
          </button>
        </Badge>
      ))}
    </div>
  );
}

function Count({ value, onChange }: { value: number; onChange: (next: number) => void }) {
  // A stepper rather than a number box: emptying the box yields NaN, which compares
  // false against every bound and used to travel all the way to the server as null.
  const clamp = (next: number) => onChange(Math.min(MAX_ITEMS, Math.max(1, next)));
  return (
    <div className="flex items-center gap-1 rounded-lg border border-border p-1">
      <Button variant="ghost" size="icon-sm" onClick={() => clamp(value - 1)} disabled={value <= 1}>
        <Minus />
      </Button>
      <span className="w-8 text-center text-body font-medium nums">{value}</span>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={() => clamp(value + 1)}
        disabled={value >= MAX_ITEMS}
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
  onCancel,
  variant = "generate",
  footnote,
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
  onCancel: () => void;
  /** "evaluation" drops the item counter: one item per arm is what makes the session
   *  the statistical unit. Everything else is shared, which is precisely what
   *  guarantees the commission is the same one on both screens. */
  variant?: "generate" | "evaluation";
  footnote?: ReactNode;
}) {
  const [open, setOpen] = useState<string | null | undefined>(undefined);
  const [onlyWithExemplars, setOnlyWithExemplars] = useState(true);
  // What the full-screen selector is choosing: the targets, the ad-hoc curriculum, or
  // nothing. One state, because only one overlay can be open.
  const [picking, setPicking] = useState<"concepts" | "curriculum" | null>(null);
  const patch = (fields: Partial<FormState>) => onChange({ ...state, ...fields });

  // The workspace's preset curriculum. `undefined` while it loads, and its absence is what
  // decides whether the second switch is offered at all.
  const { data: preset } = useQuery<CurriculumState>({
    queryKey: ["kg", "curriculum"],
    queryFn: getCurriculum,
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
  const scope = useScope(typeKey);
  const graphAdjacency = useMemo(() => adjacency(graph), [graph]);
  const chosen = state.concepts.length > 0;

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
  };

  // Same rules the generator enforces server-side; failing here is just faster.
  const problems = useMemo(() => {
    const found: string[] = [];
    if (types.length > 1 && !typeKey) found.push("Elige el tipo de ítem.");
    if (state.concepts.length === 0) found.push("Elige al menos un concepto objetivo.");
    if (activeCurriculum) {
      const inside = new Set(activeCurriculum);
      const outside = state.concepts.filter((c) => !inside.has(c));
      if (outside.length > 0)
        found.push(`Estos conceptos objetivo no están en el currículo: ${outside.join(", ")}.`);
    }
    if (state.instructions.trim().length > MAX_INSTRUCTIONS)
      found.push(`Las instrucciones no pueden pasar de ${MAX_INSTRUCTIONS} caracteres.`);
    return found;
  }, [types.length, typeKey, state.concepts, activeCurriculum, state.instructions]);

  const firstStep = types.length > 1 ? "itemType" : "curriculum";
  const openStep = open === undefined ? firstStep : open;
  const step = (id: string) => ({
    open: openStep === id,
    onOpen: () => setOpen(openStep === id ? null : id),
  });

  const decisionSummary = decided
    .map((field) => describeDecision(field, state.decisions[field]))
    .join(" · ");

  const curriculumSummary = curriculumLabel(state, preset ? preset.concepts.length : null);

  const filterLabel = exemplarType
    ? `Solo conceptos con ejemplares de «${typeLabel}»`
    : "Solo conceptos con ejemplares en el banco";
  const nextAfterConcepts = decided.length > 0 ? "decisions" : "instructions";

  let index = 0;

  return (
    <div className={cn("space-y-1", disabled && "pointer-events-none opacity-50")}>
      {types.length > 1 ? (
        <FormStep
          index={++index}
          title="¿Qué tipo de ítem?"
          hint="La modalidad decide el esquema del ítem, sus reglas de redacción y de qué ejemplares del banco se sirve el few-shot: solo entran los de esta misma modalidad."
          answered={Boolean(typeKey)}
          summary={typeSpec?.label || typeKey || "Ningún tipo elegido todavía"}
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
        title="¿Qué se ha visto ya?"
        hint="Restringe lo que el modelo puede dar por sabido: el ítem no podrá exigir nada fuera de esta lista, y solo se ofrecerán como objetivo los conceptos que estén dentro."
        optional
        answered={state.useCurriculum && Boolean(activeCurriculum)}
        summary={curriculumSummary}
        {...step("curriculum")}
      >
        <div className="flex flex-wrap items-center gap-2">
          <Switch
            checked={state.useCurriculum}
            onCheckedChange={(useCurriculum) => patch({ useCurriculum })}
            label="Restringir a un currículo"
          />
          <span className="text-body font-medium">Restringir a un currículo</span>
        </div>

        {state.useCurriculum ? (
          <div className="ml-6 space-y-2">
            {preset && preset.concepts.length > 0 ? (
              <div className="flex flex-wrap items-center gap-2">
                <Switch
                  checked={state.usePresetCurriculum}
                  onCheckedChange={(usePresetCurriculum) => patch({ usePresetCurriculum })}
                  label={`Usar el currículo preestablecido (${preset.concepts.length} conceptos)`}
                />
                <span className="text-body">
                  Usar el currículo preestablecido ({preset.concepts.length} conceptos)
                </span>
              </div>
            ) : (
              <p className="text-small text-muted-foreground">
                Este workspace no tiene currículo preestablecido. Puedes definir uno en la
                pestaña Currículo del grafo, o elegir aquí los conceptos para este lote.
              </p>
            )}
            {!state.usePresetCurriculum || !preset?.concepts.length ? (
              <Button size="sm" variant="outline" onClick={() => setPicking("curriculum")}>
                <ListChecks />
                Elegir los conceptos cubiertos ({state.curriculum.length})
              </Button>
            ) : null}
          </div>
        ) : null}
      </FormStep>

      <FormStep
        index={++index}
        title="¿Qué hay que practicar?"
        hint="Lo que el ítem debe hacer practicar, no lo que menciona. Sale del grafo, y los ejemplos few-shot se eligen entre los ítems del banco etiquetados con estos conceptos."
        answered={chosen}
        summary={state.concepts.join(" · ") || "Ningún concepto elegido todavía"}
        {...step("concepts")}
      >
        {withoutExemplars > 0 ? (
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-border bg-muted/40 px-2.5 py-2">
            <Switch
              checked={onlyWithExemplars}
              onCheckedChange={applyFilter}
              label={filterLabel}
            />
            <span className="text-small font-medium">{filterLabel}</span>
            <span className="ml-auto text-[11px] nums text-muted-foreground">
              {onlyWithExemplars
                ? `${hidden} oculto${hidden === 1 ? "" : "s"} sin ejemplares`
                : `${withoutExemplars} sin ningún ejemplar a la vista`}
            </span>
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => setPicking("concepts")}>
            <ListChecks />
            Elegir conceptos ({state.concepts.length})
          </Button>
          {state.concepts.length > 1 ? (
            <Button size="sm" variant="ghost" onClick={() => patch({ concepts: [] })}>
              Limpiar
            </Button>
          ) : null}
        </div>

        <ChosenConcepts
          names={state.concepts}
          colourFor={colourFor}
          onRemove={(name) =>
            patch({ concepts: state.concepts.filter((c) => c !== name) })
          }
          empty="Elige los conceptos que deben practicarse"
        />

        {!onlyWithExemplars && withoutExemplars > 0 ? (
          <p className="flex items-start gap-1.5 text-small text-attention">
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
            {exemplarType
              ? `Con el filtro apagado puedes elegir conceptos sin ningún ítem de «${typeLabel}» en el banco. Si ninguno de los elegidos tiene ejemplares de esa modalidad, la generación será zero-shot y la calidad del resultado puede empeorar.`
              : "Con el filtro apagado puedes elegir conceptos sin ningún ítem en el banco. Si ninguno de los elegidos tiene ejemplares, la generación será zero-shot y la calidad del resultado puede empeorar."}
          </p>
        ) : null}

        {wholeBatchZeroShot ? (
          <p className="flex items-start gap-1.5 text-small text-attention">
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
            {exemplarType
              ? `Ningún concepto elegido tiene ejemplares de «${typeLabel}». El few-shot solo toma ejemplares de la modalidad elegida, así que el lote irá en zero-shot salvo que aporte alguno un prerrequisito.`
              : "Ningún concepto elegido tiene ejemplares en el banco: se generará en zero-shot."}
          </p>
        ) : zeroShot.length > 0 ? (
          <p className="text-small text-muted-foreground">
            {exemplarType ? "Sin ejemplares de esta modalidad" : "Sin ejemplares propios"}, pero
            el lote sí tendrá ejemplos de los demás conceptos: {zeroShot.join(", ")}.
          </p>
        ) : null}

        {given.length > 0 || forbidden.length > 0 ? (
          <div className="space-y-2 rounded-lg border border-dashed border-border p-2.5">
            <p className="text-small text-muted-foreground">Lo que el grafo le dirá al modelo:</p>
            <ConceptTrack
              tone="given"
              icon={<Check className="size-3" />}
              label="se da por sabido"
              concepts={given}
            />
            <ConceptTrack
              tone="forbidden"
              icon={<Ban className="size-3" />}
              label="todavía no impartido"
              concepts={forbidden}
            />
          </div>
        ) : null}
      </FormStep>

      {chosen && decided.length > 0 ? (
        <FormStep
          index={++index}
          title={decided.length === 1 ? "¿Cómo debe ser?" : "¿Cómo deben ser?"}
          hint="Lo que decides tú en vez del modelo. El perfil de ejemplares marca qué campos se preguntan aquí; «Cualquiera» se lo deja a él."
          answered={decided.some((field) => state.decisions[field] !== undefined)}
          summary={decisionSummary}
          {...step("decisions")}
        >
          {decided.map((field) => (
            <DecisionField
              key={field}
              name={field}
              spec={typeSpec!.fields[field]}
              value={state.decisions[field]}
              onChange={(next) => patch({ decisions: { ...state.decisions, [field]: next } })}
            />
          ))}
        </FormStep>
      ) : null}


      {chosen ? (
        <FormStep
          index={++index}
          title="Instrucciones adicionales"
          hint="Una petición libre para este lote. Se atiende siempre que no contradiga el objetivo, el conocimiento previo ni el currículo. Antes de entrar en el prompt la revisa un modelo juez."
          optional
          answered={state.instructions.trim().length > 0}
          summary={state.instructions.trim() || "Ninguna"}
          {...step("instructions")}
        >
          <Textarea
            aria-label="Instrucciones adicionales"
            value={state.instructions}
            maxLength={MAX_INSTRUCTIONS}
            placeholder="Por ejemplo: que el contexto sea deportivo"
            onChange={(event) => patch({ instructions: event.target.value })}
            className={cn("min-h-20", blockedInstructions && "border-destructive")}
          />
          <div className="flex items-center gap-2">
            <span className="ml-auto text-small nums text-muted-foreground">
              {state.instructions.length}/{MAX_INSTRUCTIONS}
            </span>
          </div>

          {scope.data ? (
            <div className="space-y-2 rounded-lg border border-border bg-muted/30 px-2.5 py-2 text-small">
              <div>
                <span className="font-medium">Aquí puedes pedir</span>
                <ul className="mt-1 space-y-0.5 text-muted-foreground">
                  {scope.data.slots.map((slot) => (
                    <li key={slot.key}>
                      {slot.label} — <span className="italic">«{slot.example}»</span>
                    </li>
                  ))}
                </ul>
              </div>
              {scope.data.owners.length > 0 ? (
                <div>
                  <span className="font-medium">Esto se decide más arriba</span>
                  <ul className="mt-1 space-y-0.5 text-muted-foreground">
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
                  <span className="font-medium">Esto lo fija la asignatura</span>
                  <p className="mt-1 text-muted-foreground">
                    {scope.data.facts.map((fact) => fact.value).join(" · ")}
                  </p>
                </div>
              ) : null}
            </div>
          ) : null}

          {blockedInstructions ? (
            <Alert tone="danger" title="Instrucciones bloqueadas">
              <p>{blockedInstructions}</p>
            </Alert>
          ) : null}
        </FormStep>
      ) : null}

      {chosen ? (
        <div className="animate-slide-up space-y-3 rounded-xl border border-border bg-card p-3 shadow-sm">
          {variant === "generate" ? (
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-body font-medium">¿Cuántos ítems?</span>
              <Count value={state.n} onChange={(n) => patch({ n })} />
              {state.n > 1 ? (
                <Badge variant="outline">no repetirán temática entre sí</Badge>
              ) : null}
            </div>
          ) : null}

          {/* In comparison there is no switch on purpose: the reasoning mode is what is measured
              there, so the session draws it. Saying so here keeps the control's absence from reading
              as a missing checkbox. */}
          {variant === "generate" ? (
            <div className="space-y-1.5 rounded-lg border border-border bg-muted/30 px-2.5 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <Switch
                  checked={state.think}
                  onCheckedChange={(think) => patch({ think })}
                  label="Razonamiento previo del modelo"
                />
                <span className="flex items-center gap-1.5 text-body font-medium">
                  <Brain className="size-3.5" />
                  Razonamiento previo
                </span>
                <span className="ml-auto text-[11px] nums text-muted-foreground">
                  {state.think ? "activado" : "desactivado"}
                </span>
              </div>
              <p className="text-small text-muted-foreground">
                {state.think
                  ? "El modelo delibera antes de escribir: repasa el objetivo, lo que se da por sabido y lo que aún no se ha impartido. Por eso tarda bastante más —hasta varios minutos por ítem— y ese razonamiento queda visible junto al resultado."
                  : "El modelo responde directamente, sin deliberar. Va mucho más rápido, pero suele ajustarse peor al concepto objetivo y respetar peor lo que el grafo marca como todavía no impartido."}
              </p>
            </div>
          ) : (
            <p className="flex items-start gap-1.5 text-small text-muted-foreground">
              <Brain className="mt-0.5 size-3.5 shrink-0" />
              El razonamiento previo no se elige aquí: cada comparación lo enciende o lo apaga
              al azar, igual para las dos propuestas locales —la comercial delibera según
              decida su proveedor—. Así, sesión a sesión, los datos dicen si deliberar antes de
              escribir sirve de algo.
            </p>
          )}

          {footnote}

          {problems.length > 0 ? (
            <ul className="space-y-1 text-small text-destructive">
              {problems.map((problem) => (
                <li key={problem}>· {problem}</li>
              ))}
            </ul>
          ) : null}

          {error ? <p className="text-small text-destructive">{error}</p> : null}

          {running ? (
            <Button variant="outline" className="w-full" onClick={onCancel}>
              <Ban />
              {variant === "evaluation" ? "Cancelar la comparación" : "Cancelar generación"}
            </Button>
          ) : (
            <Button
              className="w-full"
              disabled={problems.length > 0 || pending || disabled}
              onClick={onLaunch}
            >
              {pending ? <Spinner /> : variant === "evaluation" ? <Scale /> : <Play />}
              {variant === "evaluation"
                ? "Comparar tres propuestas"
                : `Generar ${state.n} ítem${state.n === 1 ? "" : "s"}`}
            </Button>
          )}
        </div>
      ) : null}

      <ConceptSelector
        title="¿Qué hay que practicar?"
        concepts={concepts}
        graph={graph}
        selected={state.concepts}
        onChange={(next) => patch({ concepts: next })}
        implied={implied}
        restrictTo={activeCurriculum}
        onlyWithExemplars={onlyWithExemplars}
        exemplarType={exemplarType}
        open={picking === "concepts"}
        onClose={() => setPicking(null)}
        onConfirm={() => {
          setPicking(null);
          setOpen(state.concepts.length > 0 ? nextAfterConcepts : "concepts");
        }}
        confirmLabel="Confirmar y continuar"
      />

      {/* Neither `implied` nor `restrictTo`: a curriculum is declared whole and nothing
          narrows it. `allowNonTaggable` because a non-taggable concept can perfectly well
          have been taught, which is what a curriculum states — a target, being what an item
          is ABOUT, is the one that must stay taggable. */}
      <ConceptSelector
        title="¿Qué se ha visto ya?"
        concepts={concepts}
        graph={graph}
        selected={state.curriculum}
        onChange={(next) => patch({ curriculum: next })}
        allowNonTaggable
        showExemplarCount={false}
        open={picking === "curriculum"}
        onClose={() => setPicking(null)}
        onConfirm={() => {
          setPicking(null);
          setOpen("concepts");
        }}
        confirmLabel="Confirmar y continuar"
      />
    </div>
  );
}
