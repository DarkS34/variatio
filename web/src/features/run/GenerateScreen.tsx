import { Ban, Copy, Download, Lock, Play, TriangleAlert } from "lucide-react";
import { useMemo, useState } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { ConceptPicker } from "@/components/ConceptPicker";
import { RunTimeline } from "@/components/RunTimeline";
import { TechnicalDetails } from "@/components/TechnicalDetails";
import { TokenStream } from "@/components/TokenStream";
import { useActiveRun } from "@/components/RunDrawer";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label, Select, Textarea } from "@/components/ui/input";
import { Alert, Separator, Skeleton, Spinner, Switch } from "@/components/ui/misc";
import type { ContentProfile, FieldSpec } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  useCancelJob,
  useKg,
  usePipeline,
  useProfile,
  useSubmitJob,
} from "@/state/queries";

function baseType(schema: Record<string, any>): string {
  if (schema.enum) return "enum";
  const type = schema.type;
  if (Array.isArray(type)) return type.find((t: unknown) => t && t !== "null") ?? "string";
  return type ?? "string";
}

/** One control per schema field, decided at runtime: the profile is per-instance. */
function FixedField({
  name,
  spec,
  enabled,
  value,
  onToggle,
  onChange,
}: {
  name: string;
  spec: FieldSpec;
  enabled: boolean;
  value: unknown;
  onToggle: (next: boolean) => void;
  onChange: (next: unknown) => void;
}) {
  const type = baseType(spec.schema);
  const guidance = spec.guidance?.generation;

  return (
    <div className={cn("rounded-lg border border-border p-3", !enabled && "opacity-70")}>
      <div className="flex items-center gap-2">
        <Switch checked={enabled} onCheckedChange={onToggle} label={`fijar ${name}`} />
        <span className="font-mono text-sm">{name}</span>
        {guidance ? <InfoHint label={`Guía de ${name}`}>{guidance}</InfoHint> : null}
        <Badge variant="outline" className="ml-auto">
          {type}
        </Badge>
      </div>

      {enabled ? (
        <div className="mt-2 space-y-1">
          {type === "enum" ? (
            <Select value={String(value ?? "")} onChange={(event) => onChange(event.target.value)}>
              {(spec.schema.enum ?? []).map((option: string) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </Select>
          ) : type === "boolean" ? (
            <div className="flex items-center gap-2">
              <Switch checked={Boolean(value)} onCheckedChange={onChange} label={name} />
              <span className="text-sm">{value ? "verdadero" : "falso"}</span>
            </div>
          ) : type === "integer" || type === "number" ? (
            <Input
              type="number"
              value={value === null || value === undefined ? "" : String(value)}
              onChange={(event) =>
                onChange(event.target.value === "" ? null : Number(event.target.value))
              }
            />
          ) : (
            <Textarea
              value={value === null || value === undefined ? "" : String(value)}
              onChange={(event) => onChange(event.target.value)}
              className="min-h-16 text-sm"
            />
          )}
        </div>
      ) : null}
    </div>
  );
}

function ResultCard({
  index,
  item,
  thinking,
  profile,
}: {
  index: number;
  item: Record<string, unknown>;
  thinking?: string | null;
  profile: ContentProfile;
}) {
  const [showThinking, setShowThinking] = useState(false);
  const primary = String(item[profile.primary_field] ?? "");
  const others = Object.keys(profile.fields).filter((f) => f !== profile.primary_field);

  return (
    <Card className="animate-fade-in">
      <CardHeader className="pb-2">
        <div className="flex items-center gap-2">
          <CardTitle>Ítem {index}</CardTitle>
          <div className="ml-auto flex gap-1">
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Copiar JSON"
              onClick={() => navigator.clipboard.writeText(JSON.stringify(item, null, 2))}
            >
              <Copy />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        <p className="whitespace-pre-wrap text-sm leading-relaxed">{primary}</p>

        {others.map((field) => {
          const value = item[field];
          if (value === null || value === undefined || value === "") return null;
          const isCode = field.toLowerCase().includes("solution") || field.toLowerCase().includes("code");
          return (
            <div key={field} className="space-y-1">
              <Label>{field}</Label>
              {isCode ? (
                <CodeBlock code={String(value)} maxHeight="18rem" />
              ) : (
                <p className="text-sm text-muted-foreground">{String(value)}</p>
              )}
            </div>
          );
        })}

        {thinking ? (
          <div>
            <Button variant="ghost" size="sm" onClick={() => setShowThinking((v) => !v)}>
              {showThinking ? "Ocultar" : "Ver"} razonamiento
            </Button>
            {showThinking ? (
              <pre className="thin-scroll mt-2 max-h-56 overflow-auto rounded-md border border-border p-2 font-mono text-xs whitespace-pre-wrap text-muted-foreground">
                {thinking}
              </pre>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

function toMarkdown(items: { item: Record<string, unknown> }[], profile: ContentProfile): string {
  const lines: string[] = ["# Ítems generados", ""];
  items.forEach(({ item }, index) => {
    lines.push(`## Ítem ${index + 1}`, "", String(item[profile.primary_field] ?? ""), "");
    for (const field of Object.keys(profile.fields)) {
      if (field === profile.primary_field) continue;
      const value = item[field];
      if (value === null || value === undefined || value === "") continue;
      lines.push(`### ${field}`, "");
      const isCode = field.toLowerCase().includes("solution") || field.toLowerCase().includes("code");
      lines.push(isCode ? "```python" : "", String(value), isCode ? "```" : "", "");
    }
  });
  return lines.join("\n");
}

function download(name: string, content: string, type: string) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  URL.revokeObjectURL(url);
}

export function GenerateScreen() {
  const pipeline = usePipeline();
  const profileQuery = useProfile();
  const kg = useKg();
  const submit = useSubmitJob();
  const cancel = useCancelJob();
  const run = useActiveRun();

  const [n, setN] = useState(2);
  const [concepts, setConcepts] = useState<string[]>([]);
  const [curriculum, setCurriculum] = useState<string[]>([]);
  const [useCurriculum, setUseCurriculum] = useState(false);
  const [fixed, setFixed] = useState<Record<string, unknown>>({});
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});

  const profile = profileQuery.data?.profile ?? null;
  const conceptList = kg.data?.concepts ?? [];
  const unlocked = pipeline.data?.generation_unlocked ?? false;

  // Same rules the generator enforces server-side; failing here is just faster.
  const problems = useMemo(() => {
    const found: string[] = [];
    if (n < 1 || n > 20) found.push("El número de ítems debe estar entre 1 y 20.");
    if (concepts.length === 0) found.push("Elige al menos un concepto objetivo.");
    if (useCurriculum) {
      const set = new Set(curriculum);
      const outside = concepts.filter((c) => !set.has(c));
      if (curriculum.length === 0) found.push("El currículo está activado pero vacío.");
      else if (outside.length > 0)
        found.push(`Estos conceptos objetivo no están en el currículo: ${outside.join(", ")}.`);
    }
    // Fijar un campo a vacío le pide al modelo que lo deje en blanco, y así vuelve.
    const blank = Object.keys(enabled).filter(
      (field) =>
        enabled[field] &&
        (fixed[field] === undefined ||
          fixed[field] === null ||
          (typeof fixed[field] === "string" && !(fixed[field] as string).trim())),
    );
    if (blank.length > 0) found.push(`Campos fijos sin valor: ${blank.join(", ")}.`);
    return found;
  }, [n, concepts, curriculum, useCurriculum, enabled, fixed]);

  const zeroShot = useMemo(
    () => concepts.filter((name) => (conceptList.find((c) => c.name === name)?.exemplars ?? 0) === 0),
    [concepts, conceptList],
  );

  const running = run?.job?.status === "running" && run.job.kind === "generate";
  const results = useMemo(() => {
    if (run?.job?.kind !== "generate") return [];
    const fromResult = (run.job?.result?.items ?? []) as { item: Record<string, unknown>; thinking?: string }[];
    if (fromResult.length > 0) return fromResult;
    return run.items.map((i) => ({ item: i.item, thinking: i.thinking ?? undefined }));
  }, [run]);

  if (profileQuery.isLoading || kg.isLoading || pipeline.isLoading) {
    return <Skeleton className="h-96" />;
  }

  const launch = () => {
    const params: Record<string, unknown> = { n, concepts };
    const activeFixed: Record<string, unknown> = {};
    for (const [field, on] of Object.entries(enabled)) {
      const value = fixed[field];
      if (!on || value === undefined || value === null) continue;
      if (typeof value === "string" && !value.trim()) continue;
      activeFixed[field] = value;
    }
    if (Object.keys(activeFixed).length > 0) params.fixed = activeFixed;
    if (useCurriculum && curriculum.length > 0) params.curriculum = curriculum;
    submit.mutate({ kind: "generate", params });
  };

  return (
    <div className="space-y-5">
      <header className="flex items-center gap-2">
        <h1 className="text-xl font-semibold tracking-tight">Generar variantes</h1>
        <InfoHint label="Cómo se genera">
          Eliges los conceptos del grafo, cuántos ítems quieres y qué campos del esquema quedan
          fijos. El resto lo redacta el modelo guiado por los ejemplos del banco.
        </InfoHint>
      </header>

      {!unlocked ? (
        <Alert tone="warning" title="Generación bloqueada">
          <p className="flex items-center gap-1.5">
            <Lock className="size-3.5" />
            Sin aprobar:{" "}
            {(pipeline.data?.stages ?? [])
              .filter((s) => s.status !== "approved")
              .map((s) => s.label)
              .join(", ")}
          </p>
        </Alert>
      ) : null}

      <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(0,1.2fr)]">
        <div className={cn("space-y-4", !unlocked && "pointer-events-none opacity-50")}>
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-1.5">
                <CardTitle>Conceptos objetivo</CardTitle>
                <InfoHint label="Qué son los conceptos objetivo">
                  Lo que el ítem debe practicar. Salen del grafo, y los ejemplos few-shot se
                  eligen entre los ítems del banco etiquetados con ellos.
                </InfoHint>
              </div>
            </CardHeader>
            <CardContent>
              <ConceptPicker
                concepts={conceptList}
                selected={concepts}
                onChange={setConcepts}
                emptyHint="Elige los conceptos que deben practicarse"
              />
              {zeroShot.length > 0 ? (
                <p className="mt-2 flex items-start gap-1.5 text-xs text-[var(--warning)]">
                  <TriangleAlert className="mt-0.5 size-3.5 shrink-0" />
                  Sin ejemplos, se generarán en zero-shot: {zeroShot.join(", ")}.
                </p>
              ) : null}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle>Currículo</CardTitle>
                <InfoHint label="Para qué sirve el currículo">
                  Restringe lo que el modelo puede dar por sabido: no introducirá nada fuera de
                  esta lista. Los conceptos objetivo deben estar dentro.
                </InfoHint>
                <span className="flex-1" />
                <Switch checked={useCurriculum} onCheckedChange={setUseCurriculum} label="currículo" />
              </div>
            </CardHeader>
            <CardContent className={useCurriculum ? undefined : "hidden"}>
              {useCurriculum ? (
                <ConceptPicker
                  concepts={conceptList}
                  selected={curriculum}
                  onChange={setCurriculum}
                  emptyHint="Sin restricción de currículo"
                  showExemplarCount={false}
                  maxHeight="12rem"
                />
              ) : null}
            </CardContent>
          </Card>

          {profile ? (
            <Card>
              <CardHeader className="pb-2">
                <div className="flex items-center gap-1.5">
                  <CardTitle>Campos fijos</CardTitle>
                  <InfoHint label="Qué hacen los campos fijos">
                    Un campo fijado se le impone al modelo y se conserva tal cual en el ítem. Sin
                    fijar, lo decide él. Fijar un campo exige darle valor: en blanco no es un
                    valor.
                  </InfoHint>
                </div>
              </CardHeader>
              <CardContent className="space-y-2">
                {Object.entries(profile.fields).map(([name, spec]) => (
                  <FixedField
                    key={name}
                    name={name}
                    spec={spec}
                    enabled={Boolean(enabled[name])}
                    value={fixed[name]}
                    onToggle={(next) => {
                      setEnabled((current) => ({ ...current, [name]: next }));
                      if (next && fixed[name] === undefined) {
                        const type = baseType(spec.schema);
                        setFixed((current) => ({
                          ...current,
                          [name]:
                            type === "enum"
                              ? (spec.schema.enum ?? [""])[0]
                              : type === "boolean"
                                ? false
                                : type === "integer" || type === "number"
                                  ? 0
                                  : "",
                        }));
                      }
                    }}
                    onChange={(next) => setFixed((current) => ({ ...current, [name]: next }))}
                  />
                ))}
              </CardContent>
            </Card>
          ) : null}

          <Card>
            <CardContent className="space-y-3 pt-4">
              <div className="flex items-center gap-3">
                <Label className="shrink-0">Número de ítems</Label>
                <Input
                  type="number"
                  min={1}
                  max={20}
                  value={n}
                  onChange={(event) => setN(Number(event.target.value))}
                  className="max-w-24"
                />
              </div>

              {problems.length > 0 ? (
                <ul className="space-y-1 text-xs text-destructive">
                  {problems.map((problem) => (
                    <li key={problem}>· {problem}</li>
                  ))}
                </ul>
              ) : null}

              {submit.isError ? (
                <p className="text-xs text-destructive">{(submit.error as Error).message}</p>
              ) : null}

              {running ? (
                <Button
                  variant="outline"
                  className="w-full"
                  onClick={() => cancel.mutate(run!.job!.id)}
                  disabled={cancel.isPending}
                >
                  <Ban />
                  Cancelar generación
                </Button>
              ) : (
                <Button
                  className="w-full"
                  disabled={problems.length > 0 || submit.isPending || !unlocked}
                  onClick={launch}
                >
                  {submit.isPending ? <Spinner /> : <Play />}
                  Generar {n} ítem{n === 1 ? "" : "s"}
                </Button>
              )}
            </CardContent>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader className="pb-2">
              <div className="flex items-center gap-2">
                <CardTitle className="flex-1">Ejecución</CardTitle>
                {run?.job ? (
                  <Badge variant={running ? "info" : "outline"}>{run.job.label}</Badge>
                ) : null}
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {run && run.job?.kind === "generate" ? (
                <>
                  <RunTimeline steps={run.steps} />
                  <Separator />
                  <TokenStream
                    answer={run.answer}
                    thinking={run.thinking}
                    phase={run.phase}
                    active={Boolean(running)}
                    height="12rem"
                  />
                  <TechnicalDetails run={run} />
                </>
              ) : (
                <p className="text-sm text-muted-foreground">
                  Aquí aparecerán los pasos y la respuesta del modelo, en vivo.
                </p>
              )}
            </CardContent>
          </Card>

          {results.length > 0 && profile ? (
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <h2 className="text-sm font-semibold">
                  Resultados
                  <span className="ml-2 font-normal text-muted-foreground">
                    {results.length}
                    {run?.job?.result?.requested ? ` de ${run.job.result.requested}` : ""}
                  </span>
                </h2>
                {run?.job?.result &&
                run.job.result.produced < run.job.result.requested ? (
                  <Badge variant="warning">
                    generación parcial: {run.job.result.produced}/{run.job.result.requested}
                  </Badge>
                ) : null}
                <div className="ml-auto flex gap-1">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      navigator.clipboard.writeText(
                        JSON.stringify(results.map((r) => r.item), null, 2),
                      )
                    }
                  >
                    <Copy />
                    Copiar JSON
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      download(
                        "items.json",
                        JSON.stringify(results.map((r) => r.item), null, 2),
                        "application/json",
                      )
                    }
                  >
                    <Download />
                    JSON
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => download("items.md", toMarkdown(results, profile), "text/markdown")}
                  >
                    <Download />
                    Markdown
                  </Button>
                </div>
              </div>

              {results.map((result, index) => (
                <ResultCard
                  key={index}
                  index={index + 1}
                  item={result.item}
                  thinking={result.thinking}
                  profile={profile}
                />
              ))}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
