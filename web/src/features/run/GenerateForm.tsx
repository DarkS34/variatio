import { Ban, Brain, Check, Minus, Play, Plus, Scale, TriangleAlert } from "lucide-react";
import { useMemo, useState, type ReactNode } from "react";

import { ConceptPicker, hasExemplars } from "@/components/ConceptPicker";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Alert, Spinner, Switch } from "@/components/ui/misc";
import { defaultTypeKey, typeKeys, userDecidedFields } from "@/lib/profile";
import type { ExemplarsProfile, GenerateParams, GraphView, ItemTypeSpec, KgConcept } from "@/lib/types";
import { cn } from "@/lib/utils";

import { DecisionField, describeDecision } from "./DecisionField";
import { FormStep } from "./FormStep";
import { adjacency, posteriors, priorClosure, priors } from "./prerequisites";

const MAX_ITEMS = 20;
/** Mirrors config.GENERATION_INSTRUCTIONS_MAX_CHARS. */
const MAX_INSTRUCTIONS = 600;

export interface FormState {
  n: number;
  concepts: string[];
  /** null means "the profile's first modality"; resolved against the profile on render. */
  itemType: string | null;
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
  return defaultTypeKey(profile);
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
  if (state.curriculum.length > 0) params.curriculum = state.curriculum;
  if (state.instructions.trim()) params.instructions = state.instructions.trim();
  return params;
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
  if (state.curriculum.length > 0) parts.push(`currículo de ${state.curriculum.length}`);
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
          "inline-flex items-center gap-1 text-[11px] font-medium uppercase tracking-wide",
          tone === "given" ? "text-[var(--success)]" : "text-[var(--warning)]",
        )}
      >
        {icon}
        {label}
      </span>
      {concepts.map((name) => (
        <span
          key={name}
          className={cn(
            "rounded-full border px-2 py-0.5 text-xs",
            tone === "given"
              ? "border-[color-mix(in_oklch,var(--success)_35%,transparent)] text-[var(--success)]"
              : "border-[color-mix(in_oklch,var(--warning)_35%,transparent)] text-[var(--warning)] line-through decoration-[var(--warning)]/50",
          )}
        >
          {name}
        </span>
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
      <span className="w-8 text-center text-sm font-medium tabular-nums">{value}</span>
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
  const [open, setOpen] = useState<string | null>("concepts");
  const [onlyWithExemplars, setOnlyWithExemplars] = useState(true);
  const patch = (fields: Partial<FormState>) => onChange({ ...state, ...fields });

  const types = typeKeys(profile);
  const typeKey = activeTypeKey(state, profile);
  const typeSpec = activeTypeSpec(state, profile);
  const decided = userDecidedFields(typeSpec);
  const graphAdjacency = useMemo(() => adjacency(graph), [graph]);
  const chosen = state.concepts.length > 0;

  const given = useMemo(
    () => (graphAdjacency && chosen ? priors(graphAdjacency, state.concepts) : []),
    [graphAdjacency, state.concepts, chosen],
  );
  const forbidden = useMemo(
    () => (graphAdjacency && chosen ? posteriors(graphAdjacency, state.concepts) : []),
    [graphAdjacency, state.concepts, chosen],
  );

  const byName = useMemo(
    () => new Map(concepts.map((concept) => [concept.name, concept])),
    [concepts],
  );

  const zeroShot = useMemo(
    () => state.concepts.filter((name) => !byName.has(name) || !hasExemplars(byName.get(name)!)),
    [state.concepts, byName],
  );

  // The bank is searched with the whole set at once, so one concept with exemplars is
  // enough to keep the batch out of zero-shot: the warning is about the empty set, not
  // about each name that happens to have none.
  const wholeBatchZeroShot = chosen && zeroShot.length === state.concepts.length;

  const withoutExemplars = useMemo(
    () => concepts.filter((concept) => concept.taggable && !hasExemplars(concept)).length,
    [concepts],
  );
  // Anything already chosen stays on screen, so it is not part of what the filter hides.
  const hidden = withoutExemplars - zeroShot.length;

  const applyFilter = (next: boolean) => {
    setOnlyWithExemplars(next);
    if (next && zeroShot.length > 0) {
      patch({ concepts: state.concepts.filter((name) => !zeroShot.includes(name)) });
    }
  };

  // Same rules the generator enforces server-side; failing here is just faster.
  const problems = useMemo(() => {
    const found: string[] = [];
    if (state.concepts.length === 0) found.push("Elige al menos un concepto objetivo.");
    if (state.curriculum.length > 0) {
      const inside = new Set(state.curriculum);
      const outside = state.concepts.filter((c) => !inside.has(c));
      if (outside.length > 0)
        found.push(`Estos conceptos objetivo no están en el currículo: ${outside.join(", ")}.`);

      // The graph carries every concept it extracted; only the taggable ones can be
      // named in a curriculum. The picker filters them out and so does the closure, so
      // this only fires if some other path ever puts one here.
      const taggable = new Set(concepts.filter((c) => c.taggable).map((c) => c.name));
      const unusable = state.curriculum.filter((c) => !taggable.has(c));
      if (unusable.length > 0)
        found.push(`Estos conceptos del currículo no son etiquetables: ${unusable.join(", ")}.`);
    }
    if (state.instructions.trim().length > MAX_INSTRUCTIONS)
      found.push(`Las instrucciones no pueden pasar de ${MAX_INSTRUCTIONS} caracteres.`);
    return found;
  }, [state.concepts, state.curriculum, state.instructions, concepts]);

  const step = (id: string) => ({
    open: open === id,
    onOpen: () => setOpen(open === id ? null : id),
  });

  const decisionSummary = decided
    .map((field) => describeDecision(field, state.decisions[field]))
    .join(" · ");

  let index = 0;

  return (
    <div className={cn("space-y-1", disabled && "pointer-events-none opacity-50")}>
      {types.length > 1 ? (
        <FormStep
          index={++index}
          title="¿Qué tipo de ítem?"
          hint="La modalidad decide el esquema del ítem, sus reglas de redacción y de qué ejemplares del banco se sirve el few-shot: solo entran los de esta misma modalidad."
          answered={Boolean(typeKey)}
          summary={typeSpec?.label || typeKey || "Ninguna"}
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
                  onClick={() => patch({ itemType: key, decisions: {} })}
                  className={cn(
                    "rounded-lg border p-2.5 text-left transition-colors",
                    active
                      ? "border-primary bg-primary/5"
                      : "border-border hover:bg-accent/40",
                  )}
                >
                  <span className="flex items-center gap-1.5">
                    {active ? <Check className="size-3.5 text-primary" /> : null}
                    <span className="text-sm font-medium">{spec.label || key}</span>
                  </span>
                  <span className="mt-0.5 block font-mono text-[11px] text-muted-foreground">
                    {key}
                  </span>
                  {spec.description ? (
                    <span className="mt-1 block text-xs text-muted-foreground">
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
              label="Solo conceptos con ejemplares en el banco"
            />
            <span className="text-xs font-medium">Solo conceptos con ejemplares en el banco</span>
            <span className="ml-auto text-[11px] tabular-nums text-muted-foreground">
              {onlyWithExemplars
                ? `${hidden} oculto${hidden === 1 ? "" : "s"} sin ejemplares`
                : `${withoutExemplars} sin ningún ejemplar a la vista`}
            </span>
          </div>
        ) : null}

        <ConceptPicker
          concepts={concepts}
          selected={state.concepts}
          onChange={(next) => patch({ concepts: next })}
          onlyWithExemplars={onlyWithExemplars}
          emptyHint="Elige los conceptos que deben practicarse"
        />

        {!onlyWithExemplars && withoutExemplars > 0 ? (
          <p className="flex items-start gap-1.5 text-xs text-[var(--warning)]">
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
            Con el filtro apagado puedes elegir conceptos sin ningún ítem en el banco. Si
            ninguno de los elegidos tiene ejemplares, la generación será zero-shot y la
            calidad del resultado puede empeorar.
          </p>
        ) : null}

        {wholeBatchZeroShot ? (
          <p className="flex items-start gap-1.5 text-xs text-[var(--warning)]">
            <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
            Ningún concepto elegido tiene ejemplares en el banco: se generará en zero-shot.
          </p>
        ) : zeroShot.length > 0 ? (
          <p className="text-xs text-muted-foreground">
            Sin ejemplares propios, pero el lote sí tendrá ejemplos de los demás conceptos:{" "}
            {zeroShot.join(", ")}.
          </p>
        ) : null}

        {given.length > 0 || forbidden.length > 0 ? (
          <div className="space-y-2 rounded-lg border border-dashed border-border p-2.5">
            <p className="text-xs text-muted-foreground">Lo que el grafo le dirá al modelo:</p>
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
          title="¿Qué se ha visto ya?"
          hint="Restringe lo que el modelo puede dar por sabido: el ítem no podrá exigir nada fuera de esta lista. Los conceptos objetivo deben estar dentro."
          optional
          answered={state.curriculum.length > 0}
          summary={
            state.curriculum.length > 0
              ? `${state.curriculum.length} conceptos`
              : "Sin restricción de currículo"
          }
          {...step("curriculum")}
        >
          <div className="flex flex-wrap items-center gap-2">
            {graphAdjacency ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  patch({ curriculum: priorClosure(graphAdjacency, state.concepts) })
                }
              >
                Todo lo anterior en el grafo
              </Button>
            ) : null}
            {state.curriculum.length > 0 ? (
              <Button size="sm" variant="ghost" onClick={() => patch({ curriculum: [] })}>
                Quitar la restricción
              </Button>
            ) : null}
          </div>

          <ConceptPicker
            concepts={concepts}
            selected={state.curriculum}
            onChange={(next) => patch({ curriculum: next })}
            emptyHint="Sin restricción: el modelo se guía solo por el grafo"
            showExemplarCount={false}
            maxHeight="12rem"
          />
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
            value={state.instructions}
            maxLength={MAX_INSTRUCTIONS}
            placeholder="Por ejemplo: que el contexto sea deportivo, o que el enunciado incluya una tabla de datos"
            onChange={(event) => patch({ instructions: event.target.value })}
            className={cn("min-h-20 text-sm", blockedInstructions && "border-destructive")}
          />
          <div className="flex items-center gap-2">
            <span className="ml-auto text-xs tabular-nums text-muted-foreground">
              {state.instructions.length}/{MAX_INSTRUCTIONS}
            </span>
          </div>

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
              <span className="text-sm font-medium">¿Cuántos ítems?</span>
              <Count value={state.n} onChange={(n) => patch({ n })} />
              {state.n > 1 ? (
                <Badge variant="outline">no repetirán temática entre sí</Badge>
              ) : null}
            </div>
          ) : null}

          {/* En comparación no hay interruptor a propósito: el modo de razonamiento es lo
              que allí se mide, así que lo sortea la sesión. Decirlo aquí evita que la
              ausencia del control se lea como una casilla que falta. */}
          {variant === "generate" ? (
            <div className="space-y-1.5 rounded-lg border border-border bg-muted/30 px-2.5 py-2">
              <div className="flex flex-wrap items-center gap-2">
                <Switch
                  checked={state.think}
                  onCheckedChange={(think) => patch({ think })}
                  label="Razonamiento previo del modelo"
                />
                <span className="flex items-center gap-1.5 text-sm font-medium">
                  <Brain className="size-3.5" />
                  Razonamiento previo
                </span>
                <span className="ml-auto text-[11px] tabular-nums text-muted-foreground">
                  {state.think ? "activado" : "desactivado"}
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                {state.think
                  ? "El modelo delibera antes de escribir: repasa el objetivo, lo que se da por sabido y lo que aún no se ha impartido. Por eso tarda bastante más —hasta varios minutos por ítem— y ese razonamiento queda visible junto al resultado."
                  : "El modelo responde directamente, sin deliberar. Va mucho más rápido, pero suele ajustarse peor al concepto objetivo y respetar peor lo que el grafo marca como todavía no impartido."}
              </p>
            </div>
          ) : (
            <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
              <Brain className="mt-0.5 size-3.5 shrink-0" />
              El razonamiento previo no se elige aquí: cada comparación lo enciende o lo apaga
              al azar, igual para las dos propuestas locales —la comercial delibera según
              decida su proveedor—. Así, sesión a sesión, los datos dicen si deliberar antes de
              escribir sirve de algo.
            </p>
          )}

          {footnote}

          {problems.length > 0 ? (
            <ul className="space-y-1 text-xs text-destructive">
              {problems.map((problem) => (
                <li key={problem}>· {problem}</li>
              ))}
            </ul>
          ) : null}

          {error ? <p className="text-xs text-destructive">{error}</p> : null}

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
    </div>
  );
}
