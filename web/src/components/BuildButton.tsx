import { Hammer, RefreshCw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import type { StageState } from "@/lib/types";
import { useHealth, usePipeline, useRawMissingFor, useSubmitJob } from "@/state/queries";

/**
 * The one way to launch a build, wherever it is pressed.
 *
 * The panel and each stage screen offer the same action, so the rules for *not* offering
 * it — an unapproved upstream, an empty raw slot, no engine, something already running —
 * live here once. A disabled button always says why in its tooltip; that is the whole
 * point of centralising it.
 */
export function BuildButton({
  stage,
  variant,
  size = "sm",
  className,
}: {
  stage: StageState;
  variant?: "default" | "outline" | "ghost";
  size?: "sm" | "default";
  className?: string;
}) {
  const submit = useSubmitJob();
  const pipeline = usePipeline();
  const health = useHealth();
  const rawMissing = useRawMissingFor(stage.artifact);

  const missing = stage.status === "missing";
  const busy = Boolean(pipeline.data?.current_job) || submit.isPending;
  const offline = health.data ? !health.data.available : false;

  const reason = stage.blocked_reason
    ? stage.blocked_reason
    : rawMissing
      ? `Faltan documentos en «${rawMissing}»: impórtalos en el panel antes de construir.`
      : offline
        ? "El motor de inferencia no responde."
        : busy
          ? `Hay un trabajo en curso: ${pipeline.data?.current_job?.label ?? "espera a que termine"}.`
          : null;

  return (
    <Button
      size={size}
      variant={variant ?? (missing ? "default" : "outline")}
      className={className}
      disabled={Boolean(reason)}
      title={
        reason ??
        (missing
          ? `Construir ${stage.label.toLowerCase()} desde los datos en bruto`
          : `Vuelve a ejecutar el constructor sobre los datos en bruto y sobrescribe el borrador de ${stage.label.toLowerCase()}`)
      }
      onClick={() => submit.mutate({ kind: stage.build_job })}
    >
      {submit.isPending ? <Spinner /> : missing ? <Hammer /> : <RefreshCw />}
      {missing ? "Construir" : "Reconstruir"}
    </Button>
  );
}
