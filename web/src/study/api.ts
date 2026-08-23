import { post, request } from "@/lib/api";
import type { Job } from "@/lib/types";

import type {
  AdminEvaluations,
  EvaluationDetail,
  EvaluationListing,
  EvaluationParams,
  EvaluationRating,
} from "./types";

const filterQuery = (filters: { workspace?: string | null; account?: number | null }) => {
  const search = new URLSearchParams();
  if (filters.workspace) search.set("workspace", filters.workspace);
  if (filters.account != null) search.set("account", String(filters.account));
  const query = search.toString();
  return query ? `?${query}` : "";
};

export const studyApi = {
  // No `n` anywhere in here: one item per arm per session is what makes the session the
  // statistical unit of the study.
  launchEvaluation: (params: EvaluationParams) =>
    post<{ job: Job; since: number }>("/api/evaluation", params),
  evaluations: (limit = 50, offset = 0) =>
    request<EvaluationListing>(`/api/evaluation?limit=${limit}&offset=${offset}`),
  evaluation: (id: string) => request<EvaluationDetail>(`/api/evaluation/${id}`),
  /** The reveal: the response already carries the origins of the three proposals. */
  chooseEvaluation: (id: string, choice: number | null, comment?: string) =>
    post<EvaluationDetail>(`/api/evaluation/${id}/choice`, { choice, comment }),
  rateEvaluation: (id: string, rating: Partial<EvaluationRating>) =>
    post<EvaluationDetail>(`/api/evaluation/${id}/rating`, rating),

  adminEvaluations: (filters: { workspace?: string | null; account?: number | null }) =>
    request<AdminEvaluations>(`/api/admin/evaluations${filterQuery(filters)}`),
  adminEvaluationCsvUrl: (filters: { workspace?: string | null; account?: number | null }) =>
    `/api/admin/evaluations/export.csv${filterQuery(filters)}`,
};
