import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { runStore } from "@/state/runStore";

import { studyApi, type AdminGenerateParams } from "./api";
import type {
  EvaluationDetail,
  EvaluationParams,
  EvaluationRating,
  StageReview,
  TriageValue,
} from "./types";

export const studyKeys = {
  evaluations: ["evaluations"] as const,
  evaluation: (id: string) => ["evaluations", id] as const,
  adminEvaluations: (filters: Record<string, unknown>) =>
    ["admin", "evaluations", filters] as const,
  adminSets: (workspace: string) => ["admin", "evaluations", "sets", workspace] as const,
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

export function useTriageProposal() {
  return useSessionMutation<{ position: number; value: TriageValue }>((id, payload) =>
    studyApi.triageProposal(id, payload.position, payload.value),
  );
}

export function useDeclineSession() {
  return useSessionMutation<{ comment?: string }>((id, payload) =>
    studyApi.declineEvaluation(id, payload.comment),
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

export function useAssignableAccounts() {
  return useQuery({
    queryKey: ["admin", "evaluations", "accounts"] as const,
    queryFn: () => studyApi.adminAssignableAccounts(),
  });
}

export function useGenerateEvaluations() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: AdminGenerateParams) => studyApi.adminGenerateEvaluations(body),
    onSuccess: ({ jobs }) => {
      // The last one is what the run drawer follows; the queue behind it is the runner's.
      if (jobs.length > 0) runStore.setCurrentJob(jobs[jobs.length - 1].id);
      client.invalidateQueries({ queryKey: ["admin", "evaluations"] });
    },
  });
}

export function useEvaluationSets(workspace: string | null) {
  return useQuery({
    queryKey: studyKeys.adminSets(workspace ?? "none"),
    queryFn: () => studyApi.adminSets(workspace!),
    enabled: Boolean(workspace),
  });
}

export function useAssignSet() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ setId, accounts, repeat }: { setId: string; accounts: number[]; repeat?: boolean }) =>
      studyApi.adminAssignSet(setId, accounts, repeat),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["admin", "evaluations"] });
      // The assignees' own queues change too, and one of them may be this browser.
      client.invalidateQueries({ queryKey: studyKeys.evaluations });
    },
  });
}

// WHAT A TEACHER ANSWERED ABOUT EACH ARTIFACT ---------------------------------------------

/** Keyed by artifact AND by workspace: the same stage of two subjects is two forms. */
export const stageReviewKey = (artifact: string) => ["stage-review", artifact] as const;

export function useStageReview(artifact: string | undefined) {
  return useQuery({
    queryKey: stageReviewKey(artifact ?? "none"),
    queryFn: () => studyApi.stageReview(artifact!),
    enabled: Boolean(artifact),
  });
}

/**
 * Save this person's verdict, and put the answer straight into the cache.
 *
 * The response IS the new state of the form, so there is nothing to refetch: a second
 * round trip would only make the badge flicker between «guardada» and «sin contestar».
 *
 * IT MERGES ONTO WHAT IS THERE rather than replacing it, and that is a floor and not a
 * nicety. The save used to answer a shorter shape than the read — no `instrument` — and
 * `StageReview` renders nothing without one, so saving made the whole block disappear
 * until the next reload. The server now answers the same shape (`study/api/stages.py`),
 * and this is what keeps an API older than the bundle from doing it again.
 */
export function useSaveStageReview(artifact: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      answers: Record<string, string>;
      overall: number | null;
      note: string | null;
      curated?: boolean;
    }) => studyApi.saveStageReview(artifact, body),
    onSuccess: (review) =>
      client.setQueryData(stageReviewKey(artifact), (previous: StageReview | undefined) =>
        previous ? { ...previous, ...review } : review,
      ),
  });
}

/** Tell the server the form was drawn. Fire and forget: it is a measurement, not a gate. */
export function useOpenStageReview() {
  return useMutation({
    mutationFn: (artifact: string) => studyApi.openStageReview(artifact),
  });
}
