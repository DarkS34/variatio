import type { ArtifactStatus } from "@/lib/types";

/** The two parts of step 3, in the order they are done: the types of exercise, then the bank. */
export type Part = "types" | "bank";

export const PARTS: readonly Part[] = ["types", "bank"];

/**
 * Where a part stands, in the bar's words under its steps — done, your turn, later, building —
 * plus the two a step never shows: being corrected, and types changed since the bank was
 * collected with them.
 */
export type PartState = "done" | "now" | "later" | "building" | "curating" | "changed";

/** What the step's screen knows about its two stages, its jobs and the syllabus. */
export interface PartFacts {
  profile: ArtifactStatus;
  /** Whether the types' file exists. A rebuild keeps the file it replaces until it ends. */
  profileHash: boolean;
  /** The types are stale for their DOCUMENTS, so rebuilding them is the move. */
  typesDrift: boolean;
  typesCurating: boolean;
  /** The types' editor holds a change the file does not have yet. */
  typesDirty: boolean;
  bank: ArtifactStatus;
  /** The bank is stale for any cause: its documents, or an upstream that moved. */
  bankStale: boolean;
  bankCurating: boolean;
  /** A link of the collection — the review, the extraction, the index — is queued or running. */
  collecting: boolean;
  /** The last collection stopped and left no bank. */
  collectionFailed: boolean;
  graphReady: boolean;
}

export interface PartReading {
  types: PartState;
  bank: PartState;
  /** Whether the bank's part may be opened: only once the types exist. */
  bankOpen: boolean;
  /** Whether there is a bank and no collection replacing it. */
  collected: boolean;
  /** A bank collected with types changed since, or stale: to collect again or to keep. */
  recollect: boolean;
  /** The part a visit opens on until somebody chooses one. */
  opening: Part;
}

/**
 * Read where each part of step 3 stands, which may be opened, and which a visit opens on.
 *
 * AT MOST ONE PART IS «Te toca ahora», the one the next move is in (the user's request,
 * 2026-10-08: once the types exist, the bank says it is next). A part is «done» as soon as
 * it is built (the user's request, the same day, for the bank): closing them is the screen's
 * way out, «Generar ejercicios», not a part's state. The types are confirmed when the bank is
 * collected or closed, never on their own, and are «changed» when they moved after the bank
 * was collected with them, which makes the bank's the move: extract it again or keep it.
 *
 * The bank's part opens only once the types exist (the user's request): without them there
 * is nothing to collect it with. A rebuild of the types keeps their file, so it keeps the
 * bank open too.
 */
export function readParts(facts: PartFacts): PartReading {
  const collected = facts.bank !== "missing" && !facts.collecting;
  const typesBuilt = facts.profile !== "missing" && facts.profile !== "building";
  const bankOpen = typesBuilt || (facts.profile === "building" && facts.profileHash);
  // An approval withdrawn by an edit, or an edit not written yet: either way the bank was
  // collected with types that are no longer these.
  const typesChanged = collected && (facts.profile !== "approved" || facts.typesDirty);
  const recollect = typesChanged || (collected && facts.bankStale);

  const types: PartState =
    facts.profile === "building"
      ? "building"
      : facts.typesCurating
        ? "curating"
        : facts.profile === "missing" || facts.typesDrift
          ? "now"
          : typesChanged
            ? "changed"
            : "done";
  // The bank is next only behind types that are settled and a syllabus that is closed: with
  // the types still to build, rebuild or correct, the move is theirs.
  const bank: PartState = facts.collecting
    ? "building"
    : facts.bankCurating
      ? "curating"
      : collected && !recollect
        ? "done"
        : (types === "done" || types === "changed") && facts.graphReady
          ? "now"
          : "later";

  // The bank once both parts have been built (the user's request, 2026-10-08), and while its
  // collection runs or where it stopped; the types while they are being built, and before
  // there is a bank.
  const opening: Part =
    bankOpen && facts.profile !== "building" && (collected || facts.collecting || facts.collectionFailed)
      ? "bank"
      : "types";

  return { types, bank, bankOpen, collected, recollect, opening };
}
