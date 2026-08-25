import { workspaceHeader } from "@/state/workspace";
import type {
  ContentContextState,
  AdminEngine,
  AdminJobQueue,
  AdminOverview,
  AdminSystem,
  ArtifactName,
  BankListing,
  BuildPlans,
  CommissionScope,
  ConceptSource,
  CerebrasCatalog,
  ConfigPayload,
  ExemplarsProfile,
  Coverage,
  CurriculumState,
  GenerationDetail,
  GenerationListing,
  GraphView,
  Health,
  InvitePreview,
  InviteRow,
  Job,
  KgSummary,
  Pipeline,
  PullStatus,
  TunnelStatus,
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

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
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

export const post = <T>(path: string, body?: unknown) =>
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

// Named exports rather than members of `api`, because the two screens that read the
// curriculum — the graph's tab and the generation form — import them by name.
export const getCurriculum = () => request<CurriculumState>("/api/kg/curriculum");

export const putCurriculum = (concepts: string[], closePrerequisites: boolean) =>
  put<CurriculumState>("/api/kg/curriculum", {
    concepts,
    close_prerequisites: closePrerequisites,
  });

// Named for the same reason: the generation form imports it directly. It 404s until the
// graph and the profile are built, which is what keeps the block off a fresh workspace.
export const getScope = (itemType: string) =>
  request<CommissionScope>(`/api/pipeline/scope?item_type=${encodeURIComponent(itemType)}`);

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

  context: () => request<ContentContextState>("/api/context"),
  saveContext: (narrative: string, facts: Record<string, string>) =>
    put<ContentContextState>("/api/context", { narrative, facts }),
  adoptContextDraft: () => post<ContentContextState>("/api/context/adopt-draft", {}),

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
    request<{
      descriptions: Record<string, string | null>;
      missing: string[];
      sources: Record<string, ConceptSource[]>;
      many_documents: boolean;
      unanchored: string[];
    }>("/api/kg/descriptions"),
  saveDescription: (concept: string, description: string) =>
    put<{ concept: string }>("/api/kg/descriptions", { concept, description }),

  addDomain: (name: string) => post<{ pipeline: Pipeline }>("/api/kg/domains", { name }),
  renameDomain: (name: string, newName: string) =>
    patch<{ pipeline: Pipeline }>("/api/kg/domains", { name, new_name: newName }),
  deleteDomain: (name: string, moveTo?: string) =>
    post<{ pipeline: Pipeline }>("/api/kg/domains/delete", { name, move_to: moveTo ?? null }),
  reorderDomains: (order: string[]) =>
    put<{ pipeline: Pipeline }>("/api/kg/domains/order", { order }),

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
  promoteGeneration: (id: number) =>
    post<{ generation: number; item: { id: string }; pipeline: Pipeline }>(
      `/api/generations/${id}/promote`,
    ),

  adminOverview: () => request<AdminOverview>("/api/admin/overview"),
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
  // The one thing the panel writes about instances, and it is deletion. It goes through
  // `/api/admin` and not `/api/workspaces` because the latter requires membership of the
  // active workspace, which would force entering each instance in order to remove it.
  adminDeleteWorkspace: (slug: string) =>
    request<{ deleted: string; path: string; files_removed: boolean }>(
      `/api/admin/workspaces/${encodeURIComponent(slug)}`,
      { method: "DELETE" },
    ),
  adminDeleteArtifact: (slug: string, artifact: ArtifactName) =>
    request<{ workspace: string; artifact: string; removed: string[]; derived: string[] }>(
      `/api/admin/workspaces/${encodeURIComponent(slug)}/artifacts/${artifact}`,
      { method: "DELETE" },
    ),

  adminJobs: () => request<AdminJobQueue>("/api/admin/jobs"),
  adminCancelJob: (id: string) =>
    request<{ cancelled: boolean }>(`/api/admin/jobs/${id}`, { method: "DELETE" }),
  adminJobHistory: (limit = 50) =>
    request<{ jobs: Job[] }>(`/api/admin/jobs/history?limit=${limit}`),

  // The machine and the process: what is resident, what is on disk, the tunnel that reaches
  // the engine and the contexts this process keeps warm. Every write here is felt by every
  // workspace, which is why they are the administrator's.
  adminEngine: () => request<AdminEngine>("/api/admin/engine"),
  adminReleaseGpu: () => post<{ released: string[] }>("/api/admin/engine/release"),
  adminPullModel: (model: string) =>
    post<{ pull: PullStatus }>("/api/admin/engine/models/pull", { model }),
  adminDeleteModel: (model: string) =>
    request<{ deleted: string }>(`/api/admin/engine/models/${encodeURIComponent(model)}`, {
      method: "DELETE",
    }),
  adminInvalidateContexts: () =>
    request<{ invalidated: number }>("/api/admin/engine/contexts", { method: "DELETE" }),
  adminInvalidateContext: (slug: string) =>
    request<{ invalidated: string }>(
      `/api/admin/engine/contexts/${encodeURIComponent(slug)}`,
      { method: "DELETE" },
    ),
  adminTunnelStart: () => post<TunnelStatus>("/api/admin/engine/tunnel/start"),
  adminTunnelStop: () => post<TunnelStatus>("/api/admin/engine/tunnel/stop"),
  adminSystem: () => request<AdminSystem>("/api/admin/system"),
  // The same job the panel's «Calentar» launches, aimed at a chosen workspace rather than the
  // active one: the header is the request's way of saying which instance it means.
  adminWarmModels: (slug: string) =>
    request<{ job: Job; since: number }>("/api/jobs", {
      method: "POST",
      body: JSON.stringify({ kind: "warm_models", params: {}, force: true }),
      headers: { "X-Workspace": slug },
    }),

  adminSetAdmin: (userId: number, isAdmin: boolean) =>
    post<{ user_id: number; is_admin: boolean }>(`/api/admin/accounts/${userId}/admin`, {
      is_admin: isAdmin,
    }),
  adminResetLink: (userId: number) =>
    post<{ user_id: number; link: string; expires_in_minutes: number }>(
      `/api/admin/accounts/${userId}/reset-link`,
    ),
  adminRevokeSessions: (userId: number) =>
    request<{ user_id: number; revoked: number }>(`/api/admin/accounts/${userId}/sessions`, {
      method: "DELETE",
    }),
  adminUnlockLogin: (userId: number) =>
    post<{ user_id: number; unlocked: boolean }>(`/api/admin/accounts/${userId}/unlock`),

  adminClearCache: (slug: string) =>
    request<{ workspace: string; files_removed: number; bytes_freed: number }>(
      `/api/admin/workspaces/${encodeURIComponent(slug)}/cache`,
      { method: "DELETE" },
    ),
  adminExportWorkspace: (slug: string) =>
    request<{ workspace: string; name: string; exported_at: string; files: Record<string, unknown> }>(
      `/api/admin/workspaces/${encodeURIComponent(slug)}/export`,
    ),

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

  adminConfig: () => request<ConfigPayload>("/api/admin/config"),
  updateAdminConfig: (values: Record<string, unknown>) =>
    put<ConfigPayload>("/api/admin/config", { values }),
  reloadAdminConfig: () => post<ConfigPayload>("/api/admin/config/reload"),
  resetAdminConfig: (keys: string[]) => post<ConfigPayload>("/api/admin/config/reset", { keys }),
  adminCerebrasModels: () => request<CerebrasCatalog>("/api/admin/config/cerebras-models"),
};
