import { Hammer, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import { approx } from "@/lib/format";
import type { StageState } from "@/lib/types";
import { useCanEdit } from "@/state/auth";
import {
  useBuildEstimate,
  useHealth,
  usePipeline,
  useRawMissingFor,
  useSubmitJob,
} from "@/state/queries";

/** What the two halves of the action are called on a given screen, when the generic
 *  "Construir / Reconstruir" is not what that artifact's build is actually called. */
export interface BuildLabels {
  create: string;
  redo: string;
  /** Shown before a redo that would throw away work. Absent means no confirmation. */
  confirmRedo?: string;
}

/**
 * The one way to launch a build, wherever it is pressed.
 *
 * The panel and each stage screen offer the same action, so the rules for *not* offering
 * it — an unapproved upstream, an empty raw slot, no engine, something already running —
 * live here once. A disabled button always says why in its tooltip; that is the whole
 * point of centralising it.
 *
 * Creating and redoing are the same job with opposite consequences — the first fills an
 * empty slot, the second discards what is in it — so they never share a label, an icon
 * or a variant. A screen may rename the pair (the bank *extracts*; it does not "build"),
 * but the distinction itself is not a screen's to drop.
 */
export function BuildButton({
  stage,
  variant,
  size = "sm",
  className,
  labels,
}: {
  stage: StageState;
  variant?: "default" | "outline" | "ghost";
  size?: "sm" | "default";
  className?: string;
  labels?: BuildLabels;
}) {
  const submit = useSubmitJob();
  const pipeline = usePipeline();
  const health = useHealth();
  const rawMissing = useRawMissingFor(stage.artifact);
  const canEdit = useCanEdit();
  const estimate = useBuildEstimate(stage.artifact);

  const missing = stage.status === "missing";
  // The GPU is one machine for the whole installation, so «ocupado» means ocupado by
  // anyone — not only by this workspace. `current_job` is now scoped to what you may see,
  // so the global flag beside it is what this button has to read; using the scoped one
  // would offer a build that then sat in a queue with nothing on screen explaining why.
  const engineBusy = Boolean(pipeline.data?.engine_busy);
  const elsewhere = Boolean(pipeline.data?.engine_busy_elsewhere);
  const busy = engineBusy || submit.isPending;
  const offline = health.data ? !health.data.available : false;

  // The permission goes first: a viewer being told that a raw slot is empty would be
  // reading advice about a button they could not press even after fixing it.
  const reason = !canEdit
    ? "Tu permiso sobre esta instancia es de solo lectura."
    : stage.blocked_reason
      ? stage.blocked_reason
      : rawMissing
        ? `Faltan documentos en «${rawMissing}»: impórtalos en el panel antes de construir.`
        : offline
          ? "El motor de inferencia no responde."
          : busy
            ? elsewhere
              ? "La GPU está ocupada con un trabajo de otro workspace. Solo se ejecuta uno cada vez."
              : `Hay un trabajo en curso: ${pipeline.data?.current_job?.label ?? "espera a que termine"}.`
            : null;

  // The wait is part of the decision, so it belongs on the control that starts it and
  // not only on the bar that appears afterwards.
  const cost = estimate ? ` Tardará ≈ ${approx(estimate.seconds * 1000)}.` : "";

  const launch = () => {
    if (!missing && labels?.confirmRedo && !window.confirm(labels.confirmRedo)) return;
    submit.mutate({ kind: stage.build_job });
  };

  return (
    <Button
      size={size}
      variant={variant ?? (missing ? "default" : "outline")}
      className={className}
      disabled={Boolean(reason)}
      title={
        reason ??
        (missing
          ? `Construir ${stage.label.toLowerCase()} desde los datos en bruto.${cost}`
          : `Vuelve a ejecutar el constructor sobre los datos en bruto y sobrescribe ${stage.label.toLowerCase()}.${cost}`)
      }
      onClick={launch}
    >
      {submit.isPending ? <Spinner /> : missing ? <Hammer /> : <RefreshCw />}
      {missing ? (labels?.create ?? "Construir") : (labels?.redo ?? "Reconstruir")}
    </Button>
  );
}
