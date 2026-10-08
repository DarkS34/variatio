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
  /** Of those, how many the next read tries again. Absent from an API older than the
   *  bundle, which reads as none. */
  retry_pages?: number;
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
  /** Documents up to date but holding failed pages the next read tries again. */
  retry?: number;
  total_pages: number;
}

export interface DocumentPage {
  index: number;
  text: string;
  chars: number;
  failed: boolean;
}

/** The document itself, when the server can draw its pages. */
export interface DocumentOriginal {
  pages: number;
  /** What a page's address carries, so a replaced document is never read from a cache. */
  version: string;
  /** Each page's height over its width: the reader lays the document out before a page arrives. */
  ratios: number[];
  /** Whether the transcription holds one page per page of this very file. */
  paired: boolean;
  /** Why it does not: pages moved by hand, read from other bytes, or not as many. */
  unpaired: Unpaired | null;
}

export type Unpaired = "moved" | "source" | "count";

export interface DocumentPages {
  name: string;
  pages: DocumentPage[];
  /** Absent from an API older than the bundle; null where the document cannot be drawn. */
  original?: Partial<DocumentOriginal> | null;
}
