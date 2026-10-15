import { post, request } from "@/lib/api";

import type { ChatConversation, ChatQueued, ChatRow } from "./types";

const conversation = (id: string) => `/api/chat/conversations/${encodeURIComponent(id)}`;

/**
 * The free chat's half of the API, apart from `lib/api.ts` as the chat is apart on the server
 * (`apps/chat/api/`). Every call carries the active workspace through `request`.
 */
export const chatApi = {
  conversations: () => request<{ conversations: ChatRow[] }>("/api/chat/conversations"),
  conversation: (id: string) => request<ChatConversation>(conversation(id)),
  open: (message: string, generationId?: string | null, bankId?: string | null) =>
    post<ChatQueued>("/api/chat/conversations", {
      message,
      ...(generationId ? { generation_id: generationId } : {}),
      ...(bankId && !generationId ? { bank_id: bankId } : {}),
    }),
  send: (id: string, message: string) => post<ChatQueued>(`${conversation(id)}/messages`, { message }),
  retry: (id: string) => post<ChatQueued>(`${conversation(id)}/retry`),
  cancel: (id: string) => request<{ cancelled: boolean }>(`${conversation(id)}/turn`, { method: "DELETE" }),
  remove: (id: string) => request<{ deleted: string }>(conversation(id), { method: "DELETE" }),
};
