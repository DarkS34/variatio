/** Step 1: the two slots of raw documents and what an upload answers. */

import type { ArtifactName } from "./pipeline";

export type RawKind = "corpus" | "exemplars";

export interface RawFile {
  name: string;
  bytes: number;
  modified: number;
  extension: string;
}

export interface RawSlot {
  kind: RawKind;
  label: string;
  purpose: string;
  feeds: ArtifactName[];
  path: string;
  exists: boolean;
  files: RawFile[];
  bytes: number;
}

export interface RawListing {
  supported_extensions: string[];
  max_bytes: number;
  slots: RawSlot[];
}

export interface RawUpload {
  added: { name: string; bytes: number; renamed: boolean }[];
  rejected: { name: string; reason: string }[];
  slot: RawSlot;
}
