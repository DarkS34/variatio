/**
 * A conversation of the free chat to open on arrival, handed over from another screen.
 *
 * «Llevar al chat libre» on an exercise — a generated one of the account's, or one of the bank
 * a student reads — lands on `/chat` with the exercise in the box and named, so the
 * conversation is opened on it. Kept in the session's storage and taken once, as the tutor's
 * draft is (`lib/tutorDraft.ts`): a reload does not open it a second time.
 */
const KEY = "vg.chat.draft";

export interface ChatDraft {
  message: string;
  generationId: string | null;
  bankId: string | null;
}

export function stashChatDraft(draft: ChatDraft): void {
  try {
    sessionStorage.setItem(KEY, JSON.stringify(draft));
  } catch {
    /* without storage the chat simply opens empty */
  }
}

export function takeChatDraft(): ChatDraft | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    sessionStorage.removeItem(KEY);
    const parsed = JSON.parse(raw) as Partial<ChatDraft>;
    return typeof parsed.message === "string"
      ? { message: parsed.message, generationId: parsed.generationId ?? null, bankId: parsed.bankId ?? null }
      : null;
  } catch {
    return null;
  }
}
