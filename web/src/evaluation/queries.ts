import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { runStore } from "@/state/runStore";

import { evaluationApi, type AdminGenerateParams } from "./api";
import type {
  EvaluationDetail,
  EvaluationParams,
  EvaluationRating,
  StageReview,
  EvaluationFilters,
  TriageValue,
} from "./types";

export const evaluationKeys = {
  evaluations: ["evaluations"] as const,
  evaluation: (id: string) => ["evaluations", id] as const,
  adminEvaluations: (filters: EvaluationFilters) => ["admin", "evaluations", filters] as const,
  adminStages: (filters: EvaluationFilters) => ["admin", "evaluations", "stages", filters] as const,
  adminSets: (workspace: string) => ["admin", "evaluations", "sets", workspace] as const,
};

export function useEvaluations(limit = 50) {
  return useQuery({ queryKey: evaluationKeys.evaluations, queryFn: () => evaluationApi.evaluations(limit) });
}

export function useEvaluation(id: string | null) {
  return useQuery({
    queryKey: evaluationKeys.evaluation(id ?? "none"),
    queryFn: () => evaluationApi.evaluation(id!),
    enabled: Boolean(id),
  });
}

export function useLaunchEvaluation() {
  return useMutation({
    mutationFn: (params: EvaluationParams) => evaluationApi.launchEvaluation(params),
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
      client.setQueryData(evaluationKeys.evaluation(detail.session.id), detail);
      client.invalidateQueries({ queryKey: evaluationKeys.evaluations });
    },
  });
}

export function useChooseProposal() {
  return useSessionMutation<{ choice: number | null; comment?: string }>((id, payload) =>
    evaluationApi.chooseEvaluation(id, payload.choice, payload.comment),
  );
}

export function useTriageProposal() {
  return useSessionMutation<{ position: number; value: TriageValue }>((id, payload) =>
    evaluationApi.triageProposal(id, payload.position, payload.value),
  );
}

export function useDeclineSession() {
  return useSessionMutation<{ comment?: string }>((id, payload) =>
    evaluationApi.declineEvaluation(id, payload.comment),
  );
}

export function useRateSession() {
  return useSessionMutation<Partial<EvaluationRating>>((id, payload) =>
    evaluationApi.rateEvaluation(id, payload),
  );
}

export function useAdminEvaluations(filters: EvaluationFilters) {
  return useQuery({
    queryKey: evaluationKeys.adminEvaluations(filters),
    queryFn: () => evaluationApi.adminEvaluations(filters),
    placeholderData: (previous) => previous,
  });
}

/** The construction forms under the same filters as the comparisons. */
export function useAdminStageEvaluations(filters: EvaluationFilters) {
  return useQuery({
    queryKey: evaluationKeys.adminStages(filters),
    queryFn: () => evaluationApi.adminStageEvaluations(filters),
    placeholderData: (previous) => previous,
  });
}

function useDeletion(call: (ids: string[]) => Promise<{ deleted: string[] }>) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: call,
    onSuccess: ({ deleted }) => {
      for (const id of deleted) client.removeQueries({ queryKey: evaluationKeys.evaluation(id) });
      client.invalidateQueries({ queryKey: ["admin", "evaluations"] });
      client.invalidateQueries({ queryKey: evaluationKeys.evaluations });
    },
  });
}

export const useDeleteOwnEvaluations = () => useDeletion(evaluationApi.deleteEvaluations);
export const useDeleteEvaluations = () => useDeletion(evaluationApi.adminDeleteEvaluations);

/** Withdraw evaluators from the evaluation: both instruments go, the accounts stay. */
export function useDeleteEvaluatorRecords() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (accounts: number[]) => evaluationApi.adminDeleteEvaluatorRecords(accounts),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["admin", "evaluations"] });
      client.invalidateQueries({ queryKey: evaluationKeys.evaluations });
    },
  });
}

export function useAssignableAccounts() {
  return useQuery({
    queryKey: ["admin", "evaluations", "accounts"] as const,
    queryFn: () => evaluationApi.adminAssignableAccounts(),
  });
}

export function useGenerateEvaluations() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: AdminGenerateParams) => evaluationApi.adminGenerateEvaluations(body),
    onSuccess: ({ jobs }) => {
      // The last one is what the run drawer follows; the queue behind it is the runner's.
      if (jobs.length > 0) runStore.setCurrentJob(jobs[jobs.length - 1].id);
      client.invalidateQueries({ queryKey: ["admin", "evaluations"] });
    },
  });
}

export function useEvaluationSets(workspace: string | null) {
  return useQuery({
    queryKey: evaluationKeys.adminSets(workspace ?? "none"),
    queryFn: () => evaluationApi.adminSets(workspace!),
    enabled: Boolean(workspace),
  });
}

export function useAssignSet() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ setId, accounts, repeat }: { setId: string; accounts: number[]; repeat?: boolean }) =>
      evaluationApi.adminAssignSet(setId, accounts, repeat),
    onSuccess: () => {
      client.invalidateQueries({ queryKey: ["admin", "evaluations"] });
      // The assignees' own queues change too, and one of them may be this browser.
      client.invalidateQueries({ queryKey: evaluationKeys.evaluations });
    },
  });
}

// WHAT A TEACHER ANSWERED ABOUT EACH ARTIFACT ---------------------------------------------

/** Keyed by artifact AND by workspace: the same stage of two subjects is two forms. */
export const stageReviewKey = (artifact: string) => ["stage-review", artifact] as const;

/**
 * Every stage's form at once, which is what an artifact write has to invalidate.
 *
 * The payload is not a constant: it says whether there is anything built to judge, and
 * under which hash the answer will be filed. So a build that finishes leaves it stale, and
 * `state/queries.useInvalidateChain` — the one home of what an artifact write invalidates —
 * reads this prefix rather than keeping a second copy of the key.
 */
export const stageReviewKeys = ["stage-review"] as const;

export function useStageReview(artifact: string | undefined) {
  return useQuery({
    queryKey: stageReviewKey(artifact ?? "none"),
    queryFn: () => evaluationApi.stageReview(artifact!),
    enabled: Boolean(artifact),
  });
}

/**
 * Save this person's verdict, and put the answer straight into the cache.
 *
 * The response IS the new state of the form, so there is nothing to refetch: a second
 * round trip would only make the badge flicker between "guardada" and "sin contestar".
 *
 * IT MERGES ONTO WHAT IS THERE rather than replacing it, and that is a floor and not a
 * nicety. The save used to answer a shorter shape than the read — no `instrument` — and
 * `StageReview` renders nothing without one, so saving made the whole block disappear
 * until the next reload. The server now answers the same shape (`evaluation/api/stages.py`),
 * and this is what keeps an API older than the bundle from doing it again.
 */
export function useSaveStageReview(artifact: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: {
      answers: Record<string, number>;
      overall: number | null;
      note: string | null;
      curated?: boolean;
    }) => evaluationApi.saveStageReview(artifact, body),
    onSuccess: (review) =>
      client.setQueryData(stageReviewKey(artifact), (previous: StageReview | undefined) =>
        previous ? { ...previous, ...review } : review,
      ),
  });
}

/** Tell the server the form was drawn. Fire and forget: it is a measurement, not a gate. */
export function useOpenStageReview() {
  return useMutation({
    mutationFn: (artifact: string) => evaluationApi.openStageReview(artifact),
  });
}
