/** The generated exercises, and what this account may still ask for today. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { keys, scoped } from "./keys";

export function useGenerations(
  params: {
    concept?: string;
    item_type?: string;
    q?: string;
    limit?: number;
    offset?: number;
    bank?: "in" | "out";
    difficulty?: string;
  },
  workspace?: string | null,
) {
  return useQuery({
    queryKey: scoped(keys.generations(params), workspace),
    queryFn: () => api.generations(params, workspace),
    placeholderData: (previous) => previous,
  });
}

export function useGeneration(id: string | null) {
  return useQuery({
    queryKey: keys.generation(id ?? ""),
    queryFn: () => api.generation(id!),
    enabled: id !== null,
  });
}

/** Deletes one of your own exercises in `workspace`, and the count its subject shows. */
export function useDeleteGeneration(workspace?: string | null) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteGeneration(id, workspace),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["generations"] });
      client.invalidateQueries({ queryKey: keys.workspaces });
    },
  });
}

/**
 * What this account may ask for here: the count of one commission and what is left of the
 * day. A teacher's answer has no day; a student's says how much is left.
 */
export function useAllowance(enabled = true) {
  return useQuery({ queryKey: keys.allowance, queryFn: api.allowance, enabled });
}
