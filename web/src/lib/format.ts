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

export function bytes(value: number): string {
  if (value < 1024) return `${value} B`;
  const kb = value / 1024;
  if (kb < 1024) return `${Math.round(kb)} KB`;
  const mb = kb / 1024;
  return mb < 1024 ? `${mb.toFixed(1)} MB` : `${(mb / 1024).toFixed(2)} GB`;
}

export const ENGINE_LABEL: Record<string, string> = {
  ollama: "Ollama",
};

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
  { label: string; tone: "default" | "secondary" | "outline" | "settled" | "attention" | "danger" }
> = {
  missing: { label: "Sin construir", tone: "outline" },
  building: { label: "Construyendo", tone: "default" },
  draft: { label: "Borrador", tone: "attention" },
  approved: { label: "Aprobado", tone: "settled" },
  stale: { label: "Obsoleto", tone: "danger" },
};

export const JOB_STATUS: Record<JobStatus, { label: string; tone: string }> = {
  queued: { label: "En cola", tone: "text-muted-foreground" },
  running: { label: "En curso", tone: "text-primary" },
  succeeded: { label: "Completado", tone: "text-settled" },
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

/**
 * Stable, readable hue per domain — same colour in the graph, the table and the legend.
 *
 * A cool arc (teal → blue → violet → magenta) rather than the whole wheel, so the nodes
 * still belong to the same palette as the rest of the app and stay clear of the warm
 * hues the edges use. But the arc has to be WIDE and the domains have to differ on more
 * than hue: seven domains over the old 120° landed 17° apart at one fixed lightness,
 * which on a canvas full of 5px discs is one colour. 155° plus an alternating
 * lightness/chroma pair separates neighbours on two axes at once, so consecutive
 * domains — the ones that sit next to each other in the legend — are the easiest pairs
 * to tell apart rather than the hardest.
 */
export function domainColour(index: number, total: number): string {
  const count = Math.max(1, total);
  const hue = 175 + Math.round((index / Math.max(1, count - 1 || 1)) * 155);
  const dark = index % 2 === 1;
  return `oklch(${dark ? 0.58 : 0.73} ${dark ? 0.15 : 0.11} ${hue})`;
}

/** Colour of a relation TYPE, for the edges. Domains colour the nodes out of the cool
 *  arc above; edges are a different mark, so they get warm, saturated hues that read as
 *  lines over it — except the catch-all association, which is deliberately almost grey
 *  because it is the most numerous and the least informative. Keyed by the schema key so
 *  the same relation keeps its colour across instances and languages. */
const RELATION_TONE: Record<string, [number, number]> = {
  prerrequisito: [70, 0.14],
  prerequisite: [70, 0.14],
  se_engloba_en: [330, 0.11],
  falls_under: [330, 0.11],
  relacionado: [260, 0.02],
  related_to: [260, 0.02],
};

export function relationColour(type: string, index: number): string {
  const [hue, chroma] = RELATION_TONE[type] ?? [(index * 71 + 20) % 360, 0.1];
  return `oklch(0.63 ${chroma} ${hue})`;
}
