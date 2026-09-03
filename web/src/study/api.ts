import { post, request } from "@/lib/api";
import type { Job } from "@/lib/types";

import type {
  AdminEvaluations,
  AdminSets,
  AdminStageEvaluations,
  AssignableAccount,
  EvaluationDetail,
  EvaluationListing,
  EvaluationParams,
  EvaluationRating,
  StageReview,
  StudyFilters,
  TriageValue,
} from "./types";

/** The commission, plus where it runs and how many separate comparisons to prepare. */
export interface AdminGenerateParams extends EvaluationParams {
  workspace: string;
  n: number;
}

const filterQuery = (filters: StudyFilters) => {
  const search = new URLSearchParams();
  if (filters.workspace) search.set("workspace", filters.workspace);
  if (filters.account != null) search.set("account", String(filters.account));
  if (filters.profile) search.set("profile", filters.profile);
  const query = search.toString();
  return query ? `?${query}` : "";
};

export const studyApi = {
  // WHAT A TEACHER ANSWERED ABOUT EACH ARTIFACT. The hash of the build being judged is
  // never sent: the server resolves it from the file on disk, so a verdict cannot be
  // stamped onto whatever the browser happened to believe was built.
  stageReview: (artifact: string) => request<StageReview>(`/api/stage-evaluations/${artifact}`),
  /** The form reached somebody. Recorded once; a reload never restarts the clock. */
  openStageReview: (artifact: string) =>
    post<{ opened_at: number | null }>(`/api/stage-evaluations/${artifact}/opened`, {}),
  saveStageReview: (
    artifact: string,
    body: {
      answers: Record<string, string>;
      overall: number | null;
      note: string | null;
      curated?: boolean;
    },
  ) =>
    request<StageReview>(`/api/stage-evaluations/${artifact}`, {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  // No `n` anywhere in here: one item per arm per session is what makes the session the
  // statistical unit of the study.
  launchEvaluation: (params: EvaluationParams) =>
    post<{ job: Job; since: number }>("/api/evaluation", params),
  evaluations: (limit = 50, offset = 0) =>
    request<EvaluationListing>(`/api/evaluation?limit=${limit}&offset=${offset}`),
  evaluation: (id: string) => request<EvaluationDetail>(`/api/evaluation/${id}`),
  /** One card, one answer, BEFORE the choice: a score given after the reveal is a score
   *  about a name. The server refuses it once the session is closed. */
  triageProposal: (id: string, position: number, value: TriageValue) =>
    post<EvaluationDetail>(`/api/evaluation/${id}/triage`, { position, value }),
  /** The reveal: the response already carries the origins of the three proposals. */
  chooseEvaluation: (id: string, choice: number | null, comment?: string) =>
    post<EvaluationDetail>(`/api/evaluation/${id}/choice`, { choice, comment }),
  /** «No tengo criterio»: closes the session without ever recording a preference. */
  declineEvaluation: (id: string, comment?: string) =>
    post<EvaluationDetail>(`/api/evaluation/${id}/decline`, { comment }),
  rateEvaluation: (id: string, rating: Partial<EvaluationRating>) =>
    post<EvaluationDetail>(`/api/evaluation/${id}/rating`, rating),
  deleteEvaluations: (ids: string[]) =>
    request<{ deleted: string[] }>("/api/evaluation", {
      method: "DELETE",
      body: JSON.stringify({ ids }),
    }),

  adminEvaluations: (filters: StudyFilters) =>
    request<AdminEvaluations>(`/api/admin/evaluations${filterQuery(filters)}`),
  adminEvaluationCsvUrl: (filters: StudyFilters) =>
    `/api/admin/evaluations/export.csv${filterQuery(filters)}`,
  // The other instrument, under the same three filters, so the two blocks of the panel
  // always describe the same people.
  adminStageEvaluations: (filters: StudyFilters) =>
    request<AdminStageEvaluations>(`/api/admin/evaluations/stages${filterQuery(filters)}`),
  adminStageCsvUrl: (filters: StudyFilters) =>
    `/api/admin/evaluations/stages/export.csv${filterQuery(filters)}`,
  /** Everything these evaluators contributed, both instruments; the accounts stay. */
  adminDeleteEvaluatorRecords: (accounts: number[]) =>
    request<{ accounts: number[]; sessions: number; forms: number }>(
      "/api/admin/evaluations/records",
      { method: "DELETE", body: JSON.stringify({ accounts }) },
    ),
  adminDeleteEvaluations: (ids: string[]) =>
    request<{ deleted: string[]; missing: string[] }>("/api/admin/evaluations", {
      method: "DELETE",
      body: JSON.stringify({ ids }),
    }),

  // Handing sets out. By hand and not by rule: the administrator is the one who knows
  // which subject each evaluator teaches.
  adminAssignableAccounts: () =>
    request<{ accounts: AssignableAccount[] }>("/api/admin/evaluations/accounts"),
  adminGenerateEvaluations: (body: AdminGenerateParams) =>
    post<{ jobs: Job[]; since: number }>("/api/admin/evaluations/generate", body),
  adminSets: (workspace: string) =>
    request<AdminSets>(`/api/admin/evaluations/sets?workspace=${encodeURIComponent(workspace)}`),
  adminAssignSet: (setId: string, accounts: number[], repeat = false) =>
    post<{ set_id: string; assigned: { session_id: string; account: string }[]; already_had_it: string[] }>(
      `/api/admin/evaluations/sets/${setId}/assign`,
      { accounts, repeat },
    ),
};
