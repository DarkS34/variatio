import type { ArtifactStatus, JobStatus } from "./types";

export function duration(ms: number | null | undefined): string {
  if (ms === null || ms === undefined) return "—";
  if (ms < 1000) return `${Math.round(ms)} ms`;
  const seconds = ms / 1000;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  if (minutes < 60) return `${minutes} min ${rest.toString().padStart(2, "0")} s`;
  const hours = Math.floor(minutes / 60);
  return `${hours} h ${(minutes % 60).toString().padStart(2, "0")} min`;
}

export function clock(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString("es-ES", { hour12: false });
}

export function when(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("es-ES", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export const ARTIFACT_STATUS: Record<
  ArtifactStatus,
  { label: string; tone: "default" | "secondary" | "outline" | "success" | "warning" | "danger" | "info" }
> = {
  missing: { label: "Sin construir", tone: "outline" },
  building: { label: "Construyendo", tone: "info" },
  draft: { label: "Borrador", tone: "warning" },
  approved: { label: "Aprobado", tone: "success" },
  stale: { label: "Obsoleto", tone: "danger" },
};

export const JOB_STATUS: Record<JobStatus, { label: string; tone: string }> = {
  queued: { label: "En cola", tone: "text-muted-foreground" },
  running: { label: "En curso", tone: "text-[var(--info)]" },
  succeeded: { label: "Completado", tone: "text-[var(--success)]" },
  failed: { label: "Fallido", tone: "text-destructive" },
  cancelled: { label: "Cancelado", tone: "text-muted-foreground" },
};

export const TAGGING_METHOD: Record<string, string> = {
  single_dominant: "candidato dominante",
  llm: "verificado por LLM",
  llm_thinking: "LLM con razonamiento",
  rejected: "LLM descartó todos",
  failed: "fallo al parsear",
  no_candidates: "sin candidatos sobre el umbral",
  manual: "asignado a mano",
};

export function truncate(text: string, limit: number): string {
  return text.length > limit ? `${text.slice(0, limit)}…` : text;
}

/** Stable, readable hue per domain — same colour in the graph, the table and the legend.
 *  A cool arc (teal → blue → violet) rather than the whole wheel: still one colour per
 *  domain, but they belong to the same palette as the rest of the app. */
export function domainColour(index: number, total: number): string {
  const hue = 185 + Math.round((index / Math.max(1, total)) * 120);
  return `oklch(0.66 0.1 ${hue})`;
}
