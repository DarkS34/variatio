import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { runStore } from "@/state/runStore";

import { studyApi } from "./api";
import type { EvaluationDetail, EvaluationParams, EvaluationRating } from "./types";

export const studyKeys = {
  evaluations: ["evaluations"] as const,
  evaluation: (id: string) => ["evaluations", id] as const,
  adminEvaluations: (filters: Record<string, unknown>) =>
    ["admin", "evaluations", filters] as const,
};

export function useEvaluations(limit = 50) {
  return useQuery({ queryKey: studyKeys.evaluations, queryFn: () => studyApi.evaluations(limit) });
}

export function useEvaluation(id: string | null) {
  return useQuery({
    queryKey: studyKeys.evaluation(id ?? "none"),
    queryFn: () => studyApi.evaluation(id!),
    enabled: Boolean(id),
  });
}

export function useLaunchEvaluation() {
  return useMutation({
    mutationFn: (params: EvaluationParams) => studyApi.launchEvaluation(params),
    onSuccess: ({ job }) => runStore.setCurrentJob(job.id),
  });
}

/** The choice and the rubric both return the whole session, so the cache takes the
 *  response instead of refetching: the reveal must be instant, not a second round trip. */
function useSessionMutation<T>(call: (id: string, payload: T) => Promise<EvaluationDetail>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: string; payload: T }) => call(id, payload),
    onSuccess: (detail) => {
      client.setQueryData(studyKeys.evaluation(detail.session.id), detail);
      client.invalidateQueries({ queryKey: studyKeys.evaluations });
    },
  });
}

export function useChooseProposal() {
  return useSessionMutation<{ choice: number | null; comment?: string }>((id, payload) =>
    studyApi.chooseEvaluation(id, payload.choice, payload.comment),
  );
}

export function useRateSession() {
  return useSessionMutation<Partial<EvaluationRating>>((id, payload) =>
    studyApi.rateEvaluation(id, payload),
  );
}

export function useAdminEvaluations(filters: {
  workspace?: string | null;
  account?: number | null;
}) {
  return useQuery({
    queryKey: studyKeys.adminEvaluations(filters),
    queryFn: () => studyApi.adminEvaluations(filters),
    placeholderData: (previous) => previous,
  });
}

function useDeletion(call: (ids: string[]) => Promise<{ deleted: string[] }>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: ({ deleted }) => {
      for (const id of deleted) client.removeQueries({ queryKey: studyKeys.evaluation(id) });
      client.invalidateQueries({ queryKey: ["admin", "evaluations"] });
      client.invalidateQueries({ queryKey: studyKeys.evaluations });
    },
  });
}

export const useDeleteOwnEvaluations = () => useDeletion(studyApi.deleteEvaluations);
export const useDeleteEvaluations = () => useDeletion(studyApi.adminDeleteEvaluations);
