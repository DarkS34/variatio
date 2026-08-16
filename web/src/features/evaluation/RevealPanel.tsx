import { Brain, ChevronRight, Trophy } from "lucide-react";
import { useState } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { Badge } from "@/components/ui/badge";
import { duration } from "@/lib/format";
import type { EvaluationDetail, EvaluationPosition } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ARM_META, letterFor } from "./arms";

/**
 * The moment the screen goes from grey to colour.
 *
 * The reveal is irreversible by design: being able to re-choose after seeing the origins
 * would mean the datum was never blind. So this panel only tells; it never offers a way back.
 */
function Origin({
  position,
  chosen,
}: {
  position: EvaluationPosition;
  chosen: boolean;
}) {
  const [open, setOpen] = useState(false);
  const meta = position.arm ? ARM_META[position.arm] : null;
  if (!meta) return null;

  return (
    <div
      className="overflow-hidden rounded-lg border"
      style={{ borderColor: `color-mix(in oklch, ${meta.colour} 40%, transparent)` }}
    >
      <div className="flex flex-wrap items-center gap-2 px-3 py-2">
        <span
          className="flex size-7 shrink-0 items-center justify-center rounded-md font-mono text-sm font-semibold"
          style={{ backgroundColor: meta.colour, color: "var(--background)" }}
        >
          {letterFor(position.position)}
        </span>
        <span className="text-sm font-medium">{meta.label}</span>
        {chosen ? (
          <Badge variant="info">
            <Trophy />
            elegida
          </Badge>
        ) : null}
        {position.status !== "ok" ? (
          <Badge variant={position.status === "unavailable" ? "outline" : "warning"}>
            {position.status === "unavailable" ? "no disponible" : "sin ítem válido"}
          </Badge>
        ) : null}
        <span className="ml-auto flex items-center gap-3 font-mono text-[11px] text-muted-foreground">
          <span>{position.model || "—"}</span>
          <span className="tabular-nums">{duration(position.elapsed_ms)}</span>
        </span>
      </div>

      <p className="px-3 pb-2 text-xs leading-relaxed text-muted-foreground">
        {meta.description}
      </p>

      {position.error ? (
        <p className="px-3 pb-2 text-xs text-[var(--warning)]">{position.error}</p>
      ) : null}

      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center gap-2 border-t border-border px-3 py-1.5 text-left text-[11px] font-medium text-muted-foreground transition-colors hover:text-foreground"
      >
        <ChevronRight className={cn("size-3 transition-transform", open && "rotate-90")} />
        Ver el prompt exacto que recibió
        {position.exemplar_ids && position.exemplar_ids.length > 0 ? (
          <span className="ml-auto tabular-nums">
            {position.exemplar_ids.length} ejemplo
            {position.exemplar_ids.length === 1 ? "" : "s"} del banco
          </span>
        ) : (
          <span className="ml-auto">sin ejemplos</span>
        )}
      </button>
      {open ? (
        <div className="space-y-2 border-t border-border bg-muted/30 p-3">
          <CodeBlock code={position.prompt || "(sin prompt registrado)"} maxHeight="20rem" />
          {position.exemplar_ids && position.exemplar_ids.length > 0 ? (
            <p className="font-mono text-[11px] text-muted-foreground">
              {position.exemplar_ids.join(" · ")}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export function RevealPanel({ detail }: { detail: EvaluationDetail }) {
  const { session, positions } = detail;
  const chosenMeta = session.choice_arm ? ARM_META[session.choice_arm] : null;

  return (
    <section className="animate-fade-in space-y-3">
      <header className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
        <h2 className="text-sm font-semibold">De dónde salió cada propuesta</h2>
        <p className="text-sm text-muted-foreground">
          {session.choice === null
            ? "No elegiste ninguna."
            : `Elegiste ${letterFor(session.choice)} — ${chosenMeta?.label ?? ""}.`}
        </p>
        <span className="ml-auto flex items-center gap-2 font-mono text-[11px] text-muted-foreground">
          <span className="flex items-center gap-1">
            <Brain className="size-3" />
            {session.think ? "con razonamiento" : "sin razonamiento"}
          </span>
          <span>semilla {session.seed}</span>
        </span>
      </header>

      {/* Se dice después de elegir, nunca antes: es idéntico para las tres propuestas, así
          que no delata ninguna, pero sabiéndolo de antemano se lee distinto lo que hay en
          pantalla — y el sorteo existía justo para medirlo sin ese sesgo. */}
      <p className="text-xs text-muted-foreground">
        {session.think
          ? "Esta sesión salió sorteada con razonamiento previo: las dos propuestas locales deliberaron antes de escribir."
          : "Esta sesión salió sorteada sin razonamiento previo: las dos propuestas locales respondieron directamente."}
      </p>

      <div className="space-y-2">
        {positions.map((position) => (
          <Origin
            key={position.position}
            position={position}
            chosen={session.choice === position.position}
          />
        ))}
      </div>
    </section>
  );
}
