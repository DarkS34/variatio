import type { RunView, StepView } from "@/state/runStore";

export const DOCUMENTS_STEP = "transcribe_documents";
export const PAGES_STEP = "transcribe";
export const SEAMS_STEP = "transcribe_seam";

export interface Loop {
  id: string;
  label: string;
  current: number;
  total: number | null;
  detail: string | null;
}

function lastOf(run: RunView | null, id: string): StepView | null {
  if (!run) return null;
  for (let i = run.steps.length - 1; i >= 0; i -= 1) {
    if (run.steps[i].id === id) return run.steps[i];
  }
  return null;
}

function loop(step: StepView | null): Loop | null {
  if (!step || step.status !== "running") return null;
  return {
    id: step.id,
    label: step.label,
    current: step.current ?? 0,
    total: step.total ?? null,
    detail: step.detail ?? null,
  };
}

/** The outer loop: which document of how many. */
export function documentLoop(run: RunView | null): Loop | null {
  return loop(lastOf(run, DOCUMENTS_STEP));
}

/**
 * The per-unit loop running inside the current document.
 *
 * Two of them exist and they are sequential, not parallel: every page of a document is
 * transcribed and only then are its seams reviewed. So there is at most one to draw, and
 * asking for "the inner one" rather than for a fixed id is what keeps the second bar
 * meaningful for the whole of a document instead of going blank halfway through it.
 */
export function innerLoop(run: RunView | null): Loop | null {
  return loop(lastOf(run, PAGES_STEP)) ?? loop(lastOf(run, SEAMS_STEP));
}

/**
 * The document being rewritten right now, which is the one page nobody may edit: the
 * transcriber writes the whole directory at the end, so a correction saved into it while
 * it runs is a correction thrown away without a word.
 */
export function busyDocument(run: RunView | null): string | null {
  if (run?.job?.status !== "running") return null;
  return documentLoop(run)?.detail ?? null;
}

export function loopLabel(entry: Loop): string {
  return entry.total ? `${entry.current}/${entry.total}` : String(entry.current);
}
