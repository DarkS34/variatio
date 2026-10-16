/** Step 1: the raw documents' slots. */

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ArtifactName, RawKind } from "@/lib/types";
import { useHasWorkspace, useIsStudent } from "../auth";
import { keys } from "./keys";

// Gated like `useHealth`: the shell reads it, and `/api/raw` resolves a membership like
// every route, so an account in no workspace would only ever get a 403 — and so would a
// student, to whom the raw material is closed (`auth.EDIT`).
export function useRaw() {
  const hasWorkspace = useHasWorkspace();
  const student = useIsStudent();
  return useQuery({ queryKey: keys.raw, queryFn: api.raw, enabled: hasWorkspace && !student });
}

/**
 * The KIND of the raw slot this artifact needs and that has no documents, or null.
 *
 * Which slot feeds which artifact is the server's (`slot.feeds`), so no screen carries a
 * second copy of that mapping. The kind and not the label, because the label arrives in the
 * API's own language: `lib/raw.slotLabelOf` is where it becomes the reader's.
 */
export function useRawMissingFor(artifact: ArtifactName | undefined): RawKind | null {
  const raw = useRaw();
  if (!artifact) return null;
  const slot = (raw.data?.slots ?? []).find(
    (candidate) => candidate.feeds.includes(artifact) && candidate.files.length === 0,
  );
  return slot?.kind ?? null;
}
