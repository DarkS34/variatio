import type { RawKind } from "@/lib/types";

export type DocumentState = "done" | "pending" | "stale";

export interface TranscriptionDocument {
  name: string;
  pages: number;
  state: DocumentState;
  /** Stable codes, not sentences: `lib/raw.ts` turns them into the reader's language. */
  reasons: string[];
  chars: number;
  seams_merged: number;
  failed_pages: number;
  /** Pictures a Word or PowerPoint file carried, and how many left the unreadable mark. */
  images: number;
  images_unreadable: number;
}

export interface TranscriptionState {
  slot: RawKind;
  documents: TranscriptionDocument[];
  done: number;
  pending: number;
  stale: number;
  total_pages: number;
}

export interface DocumentPage {
  index: number;
  text: string;
  chars: number;
  failed: boolean;
}

export interface DocumentPages {
  name: string;
  pages: DocumentPage[];
}
