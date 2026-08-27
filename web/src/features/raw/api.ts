import { post, request } from "@/lib/api";
import type { Job, RawKind } from "@/lib/types";

import type { DocumentPages, TranscriptionState } from "./types";

const slotPath = (kind: RawKind) => `/api/raw/${kind}/transcription`;
const documentPath = (kind: RawKind, name: string) =>
  `${slotPath(kind)}/${encodeURIComponent(name)}`;

export const rawApi = {
  transcription: (kind: RawKind) => request<TranscriptionState>(slotPath(kind)),
  startTranscription: (kind: RawKind) =>
    post<{ job: Job; since: number }>(slotPath(kind)),

  documentPages: (kind: RawKind, name: string) =>
    request<DocumentPages>(documentPath(kind, name)),
  savePage: (kind: RawKind, name: string, index: number, text: string) =>
    request<DocumentPages>(`${documentPath(kind, name)}/${index}`, {
      method: "PUT",
      body: JSON.stringify({ text }),
    }),
  insertPage: (kind: RawKind, name: string, after: number, text: string) =>
    post<DocumentPages & { index: number }>(documentPath(kind, name), { after, text }),
  deletePage: (kind: RawKind, name: string, index: number) =>
    request<DocumentPages>(`${documentPath(kind, name)}/${index}`, { method: "DELETE" }),
};
