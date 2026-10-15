import type { Job } from "@/lib/types";

/** The code a job carries when the free text was refused by the guardrail or the judge. */
export const INSTRUCTIONS_BLOCKED = "instructions_blocked";

/** What the judge refused: the text it read, and its sentence about it. */
export interface Refusal {
  text: string;
  reason: string;
}

/**
 * Whether a job failed because its additional instructions were refused, and what was said.
 *
 * Read off `error_code` and never off the sentence: the sentence is the workspace's, in
 * either language, and matching it against a catalogue key is what kept the block from
 * ever reaching the form. The `Name: ` the runner prefixes is dropped — it names a Python
 * class, and nobody on this side of the screen can act on it.
 */
export function refusal(job: Job | null | undefined): Refusal | null {
  if (!job || job.status !== "failed" || job.error_code !== INSTRUCTIONS_BLOCKED) return null;
  const text = typeof job.params.instructions === "string" ? job.params.instructions : "";
  return { text, reason: (job.error ?? "").replace(/^[A-Za-z_]+:\s*/, "") };
}

/**
 * The sentence that locks the launch button, while the refused text is still on the form.
 *
 * The comparison is on the TRIMMED text, which is what travelled: the block lifts the
 * moment the instructions change, because the judge has not read the new ones — and it
 * lifts on nothing else, so pressing again with the same words is not offered.
 */
export function stillRefused(job: Job | null | undefined, current: string): string | null {
  const found = refusal(job);
  if (!found || found.text !== current.trim()) return null;
  return found.reason;
}
