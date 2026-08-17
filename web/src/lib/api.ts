import { workspaceHeader } from "@/state/workspace";
import type {
  AdminEvaluations,
  AdminOverview,
  BankListing,
  BuildPlans,
  ExemplarsProfile,
  Coverage,
  EvaluationDetail,
  EvaluationListing,
  EvaluationParams,
  EvaluationRating,
  GenerationDetail,
  GenerationListing,
  GraphView,
  Health,
  InvitePreview,
  InviteRow,
  Job,
  KgSummary,
  Pipeline,
  ProfilePayload,
  RawKind,
  RawListing,
  RawSlot,
  RawUpload,
  Role,
  Session,
  VgEvent,
  WorkspaceListing,
  WorkspaceRow,
  WorkspaceSummary,
} from "./types";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    // The session is an httpOnly cookie, so nothing here ever reads or sends a token by
    // hand. Stated rather than left to the default because it is the whole auth scheme.
    credentials: "same-origin",
    // `X-Workspace` on EVERY call, in one place: a request that forgot it would silently
    // read whichever instance the account last activated, which is the bug this header
    // exists to prevent. It is a request, not a permission — the server checks membership
    // whatever the header says.
    headers: {
      ...workspaceHeader(),
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  if (!response.ok) {
    // FastAPI puts the human-readable reason in `detail`; surface it verbatim so the
    // user reads the pipeline's own words, not a generic HTTP message.
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      if (typeof body?.detail === "string") detail = body.detail;
      else if (Array.isArray(body?.detail)) detail = body.detail.map((d: any) => d.msg).join("; ");
    } catch {
      /* keep the status line */
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

const put = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "PUT", body: JSON.stringify(body) });

const patch = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "PATCH", body: JSON.stringify(body) });

/** Uploads go through XHR, not fetch: a 500 MB PDF needs a progress bar, and fetch
 *  still cannot report how much of a request body it has sent. */
function upload(path: string, files: File[], onProgress?: (fraction: number) => void) {
  const form = new FormData();
  for (const file of files) form.append("files", file, file.name);

  return new Promise<RawUpload>((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", path);
    for (const [name, value] of Object.entries(workspaceHeader())) {
      xhr.setRequestHeader(name, value);
    }
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress?.(event.loaded / event.total);
    };
    xhr.onload = () => {
      let body: any = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* fall through to the status line */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as RawUpload);
      else reject(new ApiError(body?.detail ?? `${xhr.status} ${xhr.statusText}`, xhr.status));
    };
    xhr.onerror = () => reject(new ApiError("No se pudo contactar con el servidor", 0));
    xhr.send(form);
  });
}

export const api = {
  me: () => request<Session>("/api/auth/me"),
  updateMe: (body: { name: string; email: string | null }) =>
    patch<Session>("/api/auth/me", body),
  login: (username: string, password: string) =>
    post<Session>("/api/auth/login", { username, password }),
  logout: () => post<{ ok: boolean }>("/api/auth/logout"),
  logoutAll: () => post<{ ok: boolean; revoked: number }>("/api/auth/logout-all"),
  changePassword: (current: string, next: string) =>
    post<{ ok: boolean }>("/api/auth/password", { current, new: next }),
  forgotPassword: (username: string) => post<{ sent: boolean }>("/api/auth/forgot", { username }),
  resetPassword: (token: string, password: string) =>
    post<Session>("/api/auth/reset", { token, password }),

  invitePreview: (token: string) =>
    request<InvitePreview>(`/api/auth/invites/${encodeURIComponent(token)}`),
  acceptInvite: (body: { token: string; username: string; name: string; password: string }) =>
    post<Session>("/api/auth/accept", body),

  workspaces: () => request<WorkspaceListing>("/api/workspaces"),
  createWorkspace: (slug: string, name: string) =>
    post<{ workspace: WorkspaceRow }>("/api/workspaces", { slug, name }),
  activateWorkspace: (slug: string) =>
    post<{ workspace: WorkspaceRow }>(`/api/workspaces/${encodeURIComponent(slug)}/activate`),
  renameWorkspace: (slug: string, name: string) =>
    patch<{ workspace: WorkspaceRow }>(`/api/workspaces/${encodeURIComponent(slug)}`, { name }),
  deleteWorkspace: (slug: string) =>
    request<{ deleted: string; path: string }>(`/api/workspaces/${encodeURIComponent(slug)}`, {
      method: "DELETE",
    }),
  workspaceSummary: (slug: string) =>
    request<WorkspaceSummary>(`/api/workspaces/${encodeURIComponent(slug)}/summary`),

  health: () => request<Health>("/api/health"),

  pipeline: () => request<Pipeline>("/api/pipeline"),
  buildPhases: () => request<BuildPlans>("/api/pipeline/phases"),
  approve: (artifact: string) => post<Pipeline>(`/api/pipeline/${artifact}/approve`),
  reopen: (artifact: string) => post<Pipeline>(`/api/pipeline/${artifact}/reopen`),
  history: (artifact: string) =>
    request<{ snapshots: { id: string; at: string; bytes: number }[] }>(
      `/api/pipeline/${artifact}/history`,
    ),
  restore: (artifact: string, snapshotId: string) =>
    post<Pipeline>(`/api/pipeline/${artifact}/restore`, { snapshot_id: snapshotId }),

  raw: () => request<RawListing>("/api/raw"),
  uploadRaw: (kind: RawKind, files: File[], onProgress?: (fraction: number) => void) =>
    upload(`/api/raw/${kind}`, files, onProgress),
  deleteRaw: (kind: RawKind, name: string) =>
    request<{ deleted: string; slot: RawSlot }>(`/api/raw/${kind}/${encodeURIComponent(name)}`, {
      method: "DELETE",
    }),

  profile: () => request<ProfilePayload>("/api/profile"),
  validateProfile: (profile: ExemplarsProfile) =>
    post<{ valid: boolean; error: string | null }>("/api/profile/validate", { profile }),
  saveProfile: (profile: ExemplarsProfile) => put<{ pipeline: Pipeline }>("/api/profile", { profile }),

  kg: () => request<KgSummary>("/api/kg"),
  kgGraph: () => request<GraphView>("/api/kg/graph"),
  kgRaw: () => request<{ graph: Record<string, any> }>("/api/kg/raw"),
  kgReplace: (graph: Record<string, any>) => put<{ pipeline: Pipeline }>("/api/kg/raw", { graph }),
  kgNeighbours: (concept: string) =>
    request<{ relations: Record<string, { out: string[]; in: string[]; directed: boolean }> }>(
      `/api/kg/neighbours?concept=${encodeURIComponent(concept)}`,
    ),
  descriptions: () =>
    request<{ descriptions: Record<string, string | null>; missing: string[] }>(
      "/api/kg/descriptions",
    ),
  saveDescription: (concept: string, description: string) =>
    put<{ concept: string }>("/api/kg/descriptions", { concept, description }),

  addDomain: (name: string) => post<{ pipeline: Pipeline }>("/api/kg/domains", { name }),
  renameDomain: (name: string, newName: string) =>
    patch<{ pipeline: Pipeline }>("/api/kg/domains", { name, new_name: newName }),
  deleteDomain: (name: string, moveTo?: string) =>
    post<{ pipeline: Pipeline }>("/api/kg/domains/delete", { name, move_to: moveTo ?? null }),

  addConcept: (name: string, domain: string, taggable = true) =>
    post<{ pipeline: Pipeline }>("/api/kg/concepts", { name, domain, taggable }),
  updateConcept: (body: {
    name: string;
    new_name?: string | null;
    domain?: string | null;
    taggable?: boolean | null;
  }) => patch<{ pipeline: Pipeline; bank_references?: number }>("/api/kg/concepts", body),
  deleteConcept: (name: string) =>
    post<{ pipeline: Pipeline; bank_references?: number }>("/api/kg/concepts/delete", { name }),

  addEdge: (relation: string, source: string, target: string) =>
    post<{ pipeline: Pipeline }>("/api/kg/relations/edges", { relation, source, target }),
  removeEdge: (relation: string, source: string, target: string) =>
    post<{ pipeline: Pipeline }>("/api/kg/relations/edges/delete", { relation, source, target }),

  bank: (params: Record<string, string | number | boolean | undefined>) => {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "" && value !== null) search.set(key, String(value));
    }
    return request<BankListing>(`/api/bank?${search.toString()}`);
  },
  coverage: () => request<Coverage>("/api/bank/coverage"),
  patchItem: (id: string, fields: Record<string, unknown>) =>
    patch<{ item: any }>(`/api/bank/${encodeURIComponent(id)}`, { fields }),
  setConcepts: (id: string, concepts: string[], primary: string | null) =>
    put<{ item: any }>(`/api/bank/${encodeURIComponent(id)}/concepts`, {
      concepts,
      primary_concept: primary,
    }),
  deleteItem: (id: string) =>
    request<{ pipeline: Pipeline }>(`/api/bank/${encodeURIComponent(id)}`, { method: "DELETE" }),

  submitJob: (kind: string, params: Record<string, unknown> = {}, force = false) =>
    post<{ job: Job; since: number }>("/api/jobs", { kind, params, force }),
  jobs: () => request<{ jobs: Job[] }>("/api/jobs"),
  currentJob: () =>
    request<{ job: Job | null; queued: Job[]; last_seq: number }>("/api/jobs/current"),
  job: (id: string) => request<{ job: Job }>(`/api/jobs/${id}`),
  jobEvents: (id: string, since = 0) =>
    request<{ events: VgEvent[] }>(`/api/jobs/${id}/events?since=${since}`),
  cancelJob: (id: string) =>
    request<{ cancelled: boolean }>(`/api/jobs/${id}`, { method: "DELETE" }),

  generations: (params: {
    scope?: "mine" | "workspace";
    concept?: string;
    item_type?: string;
    q?: string;
    limit?: number;
    offset?: number;
  }) => {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "" && value !== null) search.set(key, String(value));
    }
    return request<GenerationListing>(`/api/generations?${search.toString()}`);
  },
  generation: (id: number) => request<GenerationDetail>(`/api/generations/${id}`),
  deleteGeneration: (id: number) =>
    request<{ deleted: number }>(`/api/generations/${id}`, { method: "DELETE" }),

  adminOverview: () => request<AdminOverview>("/api/admin/overview"),
  adminEvaluations: (filters: { workspace?: string | null; account?: number | null }) => {
    const search = new URLSearchParams();
    if (filters.workspace) search.set("workspace", filters.workspace);
    if (filters.account != null) search.set("account", String(filters.account));
    const query = search.toString();
    return request<AdminEvaluations>(`/api/admin/evaluations${query ? `?${query}` : ""}`);
  },
  adminEvaluationCsvUrl: (filters: { workspace?: string | null; account?: number | null }) => {
    const search = new URLSearchParams();
    if (filters.workspace) search.set("workspace", filters.workspace);
    if (filters.account != null) search.set("account", String(filters.account));
    const query = search.toString();
    return `/api/admin/evaluations/export.csv${query ? `?${query}` : ""}`;
  },
  setAccountEnabled: (userId: number, enabled: boolean) =>
    post<{ disabled?: number; enabled?: number }>(
      `/api/admin/accounts/${userId}/${enabled ? "enable" : "disable"}`,
    ),
  // Not the same as disabling: this removes the account and leaves what it produced, whose
  // author becomes nobody. The panel is the only caller and says so before asking.
  deleteAccount: (userId: number) =>
    request<{ deleted: number; username: string }>(`/api/admin/accounts/${userId}`, {
      method: "DELETE",
    }),

  // Invitations and memberships are the installation administrator's, and only theirs:
  // there is one screen that hands out access and these are its calls.
  adminInvites: () => request<{ invites: InviteRow[] }>("/api/admin/invites"),
  adminCreateInvite: (body: { workspace: string | null; role: Role }) =>
    post<{ invite: InviteRow; link: string }>("/api/admin/invites", body),
  adminRevokeInvite: (id: number) =>
    request<{ revoked: boolean }>(`/api/admin/invites/${id}`, { method: "DELETE" }),
  adminGrantMembership: (userId: number, workspace: string, role: Role) =>
    post<{ user_id: number; workspace: string; role: Role }>(
      `/api/admin/accounts/${userId}/memberships`,
      { workspace, role },
    ),
  adminRevokeMembership: (userId: number, workspace: string) =>
    request<{ user_id: number; workspace: string }>(
      `/api/admin/accounts/${userId}/memberships/${encodeURIComponent(workspace)}`,
      { method: "DELETE" },
    ),

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
};
