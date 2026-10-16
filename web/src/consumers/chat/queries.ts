import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useActiveWorkspace } from "@/state/queries";

import { chatApi } from "./api";
import type { ChatConversation, ChatQueued } from "./types";

/** Keyed by the workspace as well, so a switch of subject never shows another's conversations. */
export const chatKeys = {
  all: ["chat"] as const,
  conversations: (ws: string | null) => ["chat", ws, "conversations"] as const,
  conversation: (ws: string | null, id: string) => ["chat", ws, "conversation", id] as const,
};

// A reply is a job of the queue, and the conversation's own read says where it stands: polled
// while one is on its way, as the tutor's is, because the text only ever comes from the file.
const PENDING_POLL_MS = 1500;

export function useChatConversations() {
  const ws = useActiveWorkspace();
  return useQuery({
    queryKey: chatKeys.conversations(ws),
    queryFn: chatApi.conversations,
    refetchInterval: (query) =>
      query.state.data?.conversations.some((row) => row.pending) ? PENDING_POLL_MS * 2 : false,
  });
}

export function useChatConversation(id: string | null) {
  const ws = useActiveWorkspace();
  return useQuery({
    queryKey: chatKeys.conversation(ws, id ?? ""),
    queryFn: () => chatApi.conversation(id as string),
    enabled: id !== null,
    refetchInterval: (query) => (query.state.data?.pending ? PENDING_POLL_MS : false),
  });
}

/** Put a conversation the server just answered with into the cache, and refresh the list. */
function useAdopt() {
  const ws = useActiveWorkspace();
  const client = useQueryClient();
  return (conversation: ChatConversation) => {
    client.setQueryData(chatKeys.conversation(ws, conversation.id), conversation);
    void client.invalidateQueries({ queryKey: chatKeys.conversations(ws) });
  };
}

export function useOpenChat() {
  const adopt = useAdopt();
  return useMutation({
    mutationFn: ({
      message,
      generationId,
      bankId,
    }: {
      message: string;
      generationId?: string | null;
      bankId?: string | null;
    }) => chatApi.open(message, generationId, bankId),
    onSuccess: (queued: ChatQueued) => adopt(queued.conversation),
  });
}

export function useSendChat(id: string | null) {
  const adopt = useAdopt();
  return useMutation({
    mutationFn: (message: string) => chatApi.send(id as string, message),
    onSuccess: (queued: ChatQueued) => adopt(queued.conversation),
  });
}

export function useRetryChat(id: string | null) {
  const adopt = useAdopt();
  return useMutation({
    mutationFn: () => chatApi.retry(id as string),
    onSuccess: (queued: ChatQueued) => adopt(queued.conversation),
  });
}

export function useCancelChat(id: string | null) {
  const ws = useActiveWorkspace();
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => chatApi.cancel(id as string),
    onSettled: () => client.invalidateQueries({ queryKey: chatKeys.conversation(ws, id ?? "") }),
  });
}

export function useDeleteChat() {
  const ws = useActiveWorkspace();
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => chatApi.remove(id),
    onSuccess: () => client.invalidateQueries({ queryKey: chatKeys.conversations(ws) }),
  });
}
