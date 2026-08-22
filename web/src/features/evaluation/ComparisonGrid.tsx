import { Check, CircleSlash } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { ItemFields } from "@/features/run/ResultCard";
import { itemTypeOf } from "@/lib/profile";
import type { ExemplarsProfile, EvaluationPosition } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ARM_META, letterFor } from "./arms";

/**
 * Three proposals, told apart by nothing but a letter.
 *
 * Everything here exists to keep the cards indistinguishable until the evaluator has
 * committed: identical height so a longer statement cannot read as "more complete"
 * before it is read, identical field order, no colour, no ids, no reasoning, no JSON —
 * only the system's arm produces interesting reasoning, which makes it a perfect tell.
 */
function ProposalCard({
  position,
  profile,
  itemType,
  revealed,
  chosen,
  onChoose,
  pending,
  choosable,
}: {
  position: EvaluationPosition;
  profile: ExemplarsProfile;
  itemType: string;
  revealed: boolean;
  chosen: boolean;
  onChoose: () => void;
  pending: boolean;
  choosable: boolean;
}) {
  const letter = letterFor(position.position);
  const meta = revealed && position.arm ? ARM_META[position.arm] : null;
  const hasItem = Boolean(position.item);

  return (
    <article
      className={cn(
        "flex h-full flex-col overflow-hidden rounded-xl border bg-card shadow-sm transition-colors",
        chosen ? "border-transparent ring-2 ring-[var(--ring)]" : "border-border",
      )}
      style={meta ? { borderColor: `color-mix(in oklch, ${meta.colour} 45%, transparent)` } : undefined}
    >
      <header className="flex items-center gap-2.5 border-b border-border px-3 py-2.5">
        <span
          className={cn(
            "flex size-8 shrink-0 items-center justify-center rounded-lg font-mono text-heading transition-colors",
            meta ? "text-background" : "bg-muted text-muted-foreground",
          )}
          style={meta ? { backgroundColor: meta.colour, color: "var(--background)" } : undefined}
        >
          {letter}
        </span>
        <div className="min-w-0">
          <p className="truncate text-body font-medium">
            {meta ? meta.label : `Propuesta ${letter}`}
          </p>
          {meta ? (
            <p className="truncate font-mono text-[11px] text-muted-foreground">
              {position.model}
            </p>
          ) : null}
        </div>
        {chosen ? (
          <span className="ml-auto flex shrink-0 items-center gap-1 text-small font-medium text-primary">
            <Check className="size-3.5" />
            tu elección
          </span>
        ) : null}
      </header>

      <div className="thin-scroll max-h-[30rem] flex-1 space-y-3 overflow-y-auto p-3">
        {hasItem ? (
          <ItemFields item={position.item!} spec={itemTypeOf(profile, { item_type: itemType })} />
        ) : (
          <div className="flex h-full min-h-32 flex-col items-center justify-center gap-2 text-center">
            <CircleSlash className="size-5 text-muted-foreground/60" />
            <p className="max-w-56 text-body text-muted-foreground">
              Esta propuesta no llegó a producir un ejercicio válido.
            </p>
            {revealed && position.error ? (
              <p className="max-w-64 text-small text-muted-foreground/80">{position.error}</p>
            ) : null}
          </div>
        )}
      </div>

      {choosable ? (
        <footer className="border-t border-border p-2">
          <Button
            variant="outline"
            className="w-full"
            disabled={!hasItem || pending}
            onClick={onChoose}
            aria-label={`Elegir la propuesta ${letter}`}
          >
            {pending ? <Spinner /> : null}
            {hasItem ? `Elegir ${letter}` : "Sin ejercicio"}
          </Button>
        </footer>
      ) : null}
    </article>
  );
}

export function ComparisonGrid({
  positions,
  profile,
  itemType,
  revealed,
  choice,
  onChoose,
  pending,
}: {
  positions: EvaluationPosition[];
  profile: ExemplarsProfile;
  itemType: string;
  revealed: boolean;
  choice: number | null;
  onChoose: (choice: number | null, comment?: string) => void;
  pending: boolean;
}) {
  const [note, setNote] = useState("");

  return (
    <div className="space-y-4">
      <div className="grid items-stretch gap-4 xl:grid-cols-3">
        {positions.map((position) => (
          <ProposalCard
            key={position.position}
            position={position}
            profile={profile}
            itemType={itemType}
            revealed={revealed}
            chosen={choice === position.position}
            onChoose={() => onChoose(position.position, note)}
            pending={pending}
            choosable={!revealed}
          />
        ))}
      </div>

      {!revealed ? (
        <div className="animate-slide-up flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-3 shadow-raised">
          <p className="text-body font-medium">¿Cuál usarías en clase?</p>
          <Input
            aria-label="Por qué, en una línea"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder="Por qué, en una línea (opcional)"
            className="h-9 min-w-48 flex-1"
          />
          {/* Forcing a pick between three bad ones turns noise into signal. */}
          <Button variant="ghost" disabled={pending} onClick={() => onChoose(null, note)}>
            Ninguna me convence
          </Button>
        </div>
      ) : null}
    </div>
  );
}
