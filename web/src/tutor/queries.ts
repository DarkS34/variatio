import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useActiveWorkspace } from "@/state/queries";

import { tutorApi } from "./api";
import type { Conversation, CriteriaDocument, TurnQueued } from "./types";

/**
 * Keyed by the workspace as well, so a switch of subject never shows one subject's
 * conversations under another's name for the instant the new answer takes.
 */
export const tutorKeys = {
  all: ["tutor"] as const,
  status: (ws: string | null) => ["tutor", ws, "status"] as const,
  conversations: (ws: string | null) => ["tutor", ws, "conversations"] as const,
  conversation: (ws: string | null, id: string) => ["tutor", ws, "conversation", id] as const,
  criteria: (ws: string | null) => ["tutor", ws, "criteria"] as const,
  notes: (ws: string | null, document: string) => ["tutor", ws, "notes", document] as const,
  admin: (slug: string, author: number | null, offset: number) =>
    ["tutor", "admin", slug, author, offset] as const,
  adminOne: (slug: string, author: number, id: string) =>
    ["tutor", "admin", slug, author, id] as const,
};

// A reply is a job of the queue, and the conversation's own read says where it stands. Polled
// while one is on its way and never otherwise: the stream would say it sooner, but the file is
// the author's and the stream is the workspace's, so the text only ever comes from here.
const PENDING_POLL_MS = 1500;

export function useTutorStatus() {
  const ws = useActiveWorkspace();
  return useQuery({
    queryKey: tutorKeys.status(ws),
    queryFn: tutorApi.status,
    refetchInterval: (query) => (query.state.data?.criteria.job ? PENDING_POLL_MS * 2 : false),
  });
}

export function useConversations() {
  const ws = useActiveWorkspace();
  return useQuery({
    queryKey: tutorKeys.conversations(ws),
    queryFn: tutorApi.conversations,
    // While a reply is on its way the row says so, and it has to stop saying it on arrival.
    refetchInterval: (query) =>
      query.state.data?.conversations.some((row) => row.pending) ? PENDING_POLL_MS * 2 : false,
  });
}

export function useConversation(id: string | null) {
  const ws = useActiveWorkspace();
  return useQuery({
    queryKey: tutorKeys.conversation(ws, id ?? ""),
    queryFn: () => tutorApi.conversation(id as string),
    enabled: id !== null,
    refetchInterval: (query) => (query.state.data?.pending ? PENDING_POLL_MS : false),
  });
}

/** Put a conversation the server just answered with into the cache, and refresh the list. */
function useAdoptConversation() {
  const ws = useActiveWorkspace();
  const client = useQueryClient();
  return (conversation: Conversation) => {
    client.setQueryData(tutorKeys.conversation(ws, conversation.id), conversation);
    void client.invalidateQueries({ queryKey: tutorKeys.conversations(ws) });
  };
}

export function useOpenConversation() {
  const adopt = useAdoptConversation();
  return useMutation({
    mutationFn: ({ message, generationId }: { message: string; generationId?: string | null }) =>
      tutorApi.open(message, generationId),
    onSuccess: (queued: TurnQueued) => adopt(queued.conversation),
  });
}

export function useSendMessage(id: string | null) {
  const adopt = useAdoptConversation();
  return useMutation({
    mutationFn: (message: string) => tutorApi.send(id as string, message),
    onSuccess: (queued: TurnQueued) => adopt(queued.conversation),
  });
}

export function useRetryTurn(id: string | null) {
  const adopt = useAdoptConversation();
  return useMutation({
    mutationFn: () => tutorApi.retry(id as string),
    onSuccess: (queued: TurnQueued) => adopt(queued.conversation),
  });
}

export function useCancelTurn(id: string | null) {
  const ws = useActiveWorkspace();
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => tutorApi.cancel(id as string),
    onSettled: () =>
      client.invalidateQueries({ queryKey: tutorKeys.conversation(ws, id ?? "") }),
  });
}

export function useDeleteConversation() {
  const ws = useActiveWorkspace();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => tutorApi.remove(id),
    onSuccess: () => client.invalidateQueries({ queryKey: tutorKeys.conversations(ws) }),
  });
}

/** One document of the notes, for the reader; read once per visit, since notes change rarely. */
export function useNotes(document: string | null) {
  const ws = useActiveWorkspace();
  return useQuery({
    queryKey: tutorKeys.notes(ws, document ?? ""),
    queryFn: () => tutorApi.notes(document as string),
    enabled: document !== null,
    staleTime: 5 * 60_000,
  });
}

export function useTutorCriteria(enabled: boolean) {
  const ws = useActiveWorkspace();
  return useQuery({
    queryKey: tutorKeys.criteria(ws),
    queryFn: tutorApi.criteria,
    enabled,
    refetchInterval: (query) => (query.state.data?.job ? PENDING_POLL_MS * 2 : false),
  });
}

export function useSaveCriteria() {
  const ws = useActiveWorkspace();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (criteria: CriteriaDocument) => tutorApi.saveCriteria(criteria),
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: tutorKeys.criteria(ws) });
      void client.invalidateQueries({ queryKey: tutorKeys.status(ws) });
    },
  });
}

export function useBuildCriteria() {
  const ws = useActiveWorkspace();
  const client = useQueryClient();
  return useMutation({
    mutationFn: tutorApi.buildCriteria,
    onSuccess: () => {
      void client.invalidateQueries({ queryKey: tutorKeys.criteria(ws) });
      void client.invalidateQueries({ queryKey: tutorKeys.status(ws) });
    },
  });
}

export function useAdminConversations(slug: string, author: number | null, offset: number) {
  return useQuery({
    queryKey: tutorKeys.admin(slug, author, offset),
    queryFn: () => tutorApi.adminConversations(slug, author, offset),
  });
}

export function useAdminConversation(slug: string, author: number | null, id: string | null) {
  return useQuery({
    queryKey: tutorKeys.adminOne(slug, author ?? 0, id ?? ""),
    queryFn: () => tutorApi.adminConversation(slug, author as number, id as string),
    enabled: author !== null && id !== null,
  });
}
