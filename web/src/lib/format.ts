import { localeStore, type Key, type Language } from "@/lib/i18n";
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

/**
 * A month abbreviation is prose, so it answers to the reader and not to the server.
 *
 * `en-GB` and not `en-US` because the shape is the decision: day first and a 24-hour clock,
 * which is what every timestamp in this app already looked like. Read from the store rather
 * than taken as an argument — these two are called from ~30 places, all of them inside a
 * tree that `localeStore` re-renders when the language changes.
 */
const DATE_LOCALES: Record<Language, string> = { es: "es-ES", en: "en-GB" };

const dateLocale = () => DATE_LOCALES[localeStore.getSnapshot()];

export function clock(ts: number): string {
  return new Date(ts * 1000).toLocaleTimeString(dateLocale(), { hour12: false });
}

export function when(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString(dateLocale(), {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

/**
 * A moment somebody chose, which may be years away: `when` plus the year when it is not this one.
 *
 * `when` drops the year on purpose — a job ran today, a session was opened this week — and
 * an invitation's expiry is the one date in the app that has no upper bound, so the same
 * shape would print «01 ene, 09:30» for a date five Januaries off.
 */
export function dateTime(iso: string, now: Date = new Date()): string {
  const date = new Date(iso);
  return date.toLocaleString(dateLocale(), {
    day: "2-digit",
    month: "short",
    ...(date.getFullYear() === now.getFullYear() ? {} : { year: "numeric" }),
    hour: "2-digit",
    minute: "2-digit",
  });
}

const RELATIVE_UNITS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["year", 365 * 86_400],
  ["month", 30 * 86_400],
  ["day", 86_400],
  ["hour", 3_600],
  ["minute", 60],
];

/** How far off a moment is, in the reader's words: «dentro de 3 días», «hace 2 horas». */
export function relative(iso: string, now: number = Date.now()): string {
  const seconds = (new Date(iso).getTime() - now) / 1000;
  const format = new Intl.RelativeTimeFormat(dateLocale(), { numeric: "auto" });
  for (const [unit, size] of RELATIVE_UNITS) {
    if (Math.abs(seconds) >= size) return format.format(Math.round(seconds / size), unit);
  }
  return format.format(0, "minute");
}

export const ARTIFACT_STATUS: Record<
  ArtifactStatus,
  { labelKey: Key; tone: "default" | "secondary" | "outline" | "settled" | "attention" | "danger" }
> = {
  missing: { labelKey: "status.missing", tone: "outline" },
  building: { labelKey: "status.building", tone: "default" },
  draft: { labelKey: "status.draft", tone: "attention" },
  approved: { labelKey: "status.approved", tone: "settled" },
  // `attention` and not `danger`, like `lib/status.ts`'s mark for the same state: what
  // went stale is "the step above changed, close this one again", a move to make and not
  // information lost — the two tables used to disagree, so the badge printed red text
  // beside a blue mark.
  stale: { labelKey: "status.stale", tone: "attention" },
};

export const JOB_STATUS: Record<JobStatus, { labelKey: Key; tone: string }> = {
  queued: { labelKey: "job.queued", tone: "text-muted-foreground" },
  running: { labelKey: "job.running", tone: "text-primary" },
  succeeded: { labelKey: "job.succeeded", tone: "text-settled" },
  failed: { labelKey: "job.failed", tone: "text-destructive" },
  cancelled: { labelKey: "job.cancelled", tone: "text-muted-foreground" },
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
