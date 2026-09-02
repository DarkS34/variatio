import type { RunView, StepView } from "@/state/runStore";

export const DOCUMENTS_STEP = "transcribe_documents";

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

/**
 * The outer loop: which document of how many.
 *
 * The inner one — pages, pictures, seams — used to be read here too, for a second bar the
 * slot's card drew by hand. The card draws the job's own timeline now, which groups every
 * loop as one row with its counter and bar, so what is left to read is the one thing the
 * timeline does not answer: WHICH document is being rewritten.
 */
export function documentLoop(run: RunView | null): Loop | null {
  return loop(lastOf(run, DOCUMENTS_STEP));
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
