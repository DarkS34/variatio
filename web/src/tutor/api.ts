import { post, request } from "@/lib/api";
import type { Job } from "@/lib/types";

import type {
  AdminConversation,
  AdminConversationListing,
  Conversation,
  ConversationRow,
  CriteriaDocument,
  CriteriaPayload,
  TurnQueued,
  TutorStatus,
} from "./types";

const conversation = (id: string) => `/api/tutor/conversations/${encodeURIComponent(id)}`;

/**
 * The tutor's half of the API, apart from `lib/api.ts` as the tutor is apart from the pipeline
 * on the server (`tutor/api/`). Every call carries the active workspace through `request`.
 */
export const tutorApi = {
  status: () => request<TutorStatus>("/api/tutor"),
  conversations: () => request<{ conversations: ConversationRow[] }>("/api/tutor/conversations"),
  conversation: (id: string) => request<Conversation>(conversation(id)),
  open: (message: string, generationId?: string | null) =>
    post<TurnQueued>("/api/tutor/conversations", {
      message,
      ...(generationId ? { generation_id: generationId } : {}),
    }),
  send: (id: string, message: string) =>
    post<TurnQueued>(`${conversation(id)}/messages`, { message }),
  retry: (id: string) => post<TurnQueued>(`${conversation(id)}/retry`),
  cancel: (id: string) =>
    request<{ cancelled: boolean }>(`${conversation(id)}/turn`, { method: "DELETE" }),
  remove: (id: string) => request<{ deleted: string }>(conversation(id), { method: "DELETE" }),
  criteria: () => request<CriteriaPayload>("/api/tutor/criteria"),
  saveCriteria: (criteria: CriteriaDocument) =>
    request<{ origin: string; criteria: CriteriaDocument; warnings: string[] }>(
      "/api/tutor/criteria",
      { method: "PUT", body: JSON.stringify({ criteria }) },
    ),
  buildCriteria: () => post<{ job: Job; queue_position: number }>("/api/tutor/criteria/build"),
  adminConversations: (slug: string, author?: number | null, offset = 0) => {
    const search = new URLSearchParams({ offset: String(offset) });
    if (author != null) search.set("author", String(author));
    return request<AdminConversationListing>(
      `/api/admin/workspaces/${encodeURIComponent(slug)}/tutor?${search.toString()}`,
    );
  },
  adminConversation: (slug: string, author: number, id: string) =>
    request<AdminConversation>(
      `/api/admin/workspaces/${encodeURIComponent(slug)}/tutor/${author}/${encodeURIComponent(id)}`,
    ),
};
