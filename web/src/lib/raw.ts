import type { Key } from "@/lib/i18n";
import type { RawKind, RawSlot } from "@/lib/types";

/**
 * The raw slots, named once for the whole browser.
 *
 * The server declares the two of them and sends a `label` and a `purpose` with each, both
 * written in the API's own language. What identifies a slot is `kind`, which is stable and
 * says nothing about who is reading, so the wording lives in the catalogue like every other
 * sentence and this is the table between the two. The same reason `lib/evaluator.ts` keeps
 * the two evaluator profiles: an enumerable set the server sends by name is translated
 * here, never rendered as it arrives.
 *
 * `slot.label` survives as the fallback for a `kind` this bundle does not know, which is
 * what an API newer than the browser looks like.
 */
export const SLOT_LABEL_KEYS: Record<RawKind, Key> = {
  corpus: "raw.slot.corpus",
  exemplars: "raw.slot.exemplars",
};

export const SLOT_PURPOSE_KEYS: Record<RawKind, Key> = {
  corpus: "raw.slot.corpus.purpose",
  exemplars: "raw.slot.exemplars.purpose",
};

export function slotLabel(slot: RawSlot, t: (key: Key) => string): string {
  const key = SLOT_LABEL_KEYS[slot.kind];
  return key ? t(key) : slot.label;
}

export function slotPurpose(slot: RawSlot, t: (key: Key) => string): string {
  const key = SLOT_PURPOSE_KEYS[slot.kind];
  return key ? t(key) : slot.purpose;
}

export function slotLabelOf(kind: RawKind | null | undefined, t: (key: Key) => string): string | null {
  if (!kind) return null;
  const key = SLOT_LABEL_KEYS[kind];
  return key ? t(key) : kind;
}

/**
 * Why a transcription went stale, one key per code the stage sends.
 *
 * A badge saying «2 caducados» reports the state without the cause, and the cause is the
 * half you act on — so the reason has to arrive, and it has to arrive in something the
 * reader's own language can be written from.
 */
export const STALE_REASON_KEYS: Record<string, Key> = {
  document: "transcribe.reason.document",
  route: "transcribe.reason.route",
  model: "transcribe.reason.model",
  dpi: "transcribe.reason.dpi",
  ocr: "transcribe.reason.ocr",
  prompt: "transcribe.reason.prompt",
  temperature: "transcribe.reason.temperature",
  config: "transcribe.reason.config",
};

export function staleReasons(codes: string[], t: (key: Key) => string): string[] {
  const said: string[] = [];
  for (const code of codes) {
    const key = STALE_REASON_KEYS[code];
    const text = key ? t(key) : t("transcribe.reason.config");
    if (!said.includes(text)) said.push(text);
  }
  return said;
}
