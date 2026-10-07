import { workspaceHeader } from "@/state/workspace";
import type {
  ContentContextState,
  AdminClassLink,
  Allowance,
  AdminEngine,
  AdminFeaturesPayload,
  AdminGenerationListing,
  AdminJobQueue,
  AdminOverview,
  ArtifactName,
  BankListing,
  ClassLinkTerms,
  ClassLinkView,
  BuildPlans,
  CommissionScope,
  ConceptSource,
  CerebrasCatalog,
  ConfigPayload,
  ExemplarsProfile,
  Coverage,
  FeatureMode,
  FeatureName,
  CurriculumState,
  EvaluatorProfile,
  GenerationDetail,
  GenerationListing,
  GraphView,
  Health,
  InviteImportOutcome,
  InvitePreview,
  InviteRow,
  InviteTerms,
  Job,
  JoinedSession,
  KgSummary,
  MaintenanceState,
  Member,
  MemberAction,
  MemberInvite,
  MembersBulkResult,
  MintedClassLink,
  StudentUses,
  ActivityHistory,
  ActivityWeek,
  MintedMemberInvite,
  MintedInvite,
  Pipeline,
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

/**
 * What both deletions answer. `rehomed` is about everybody who was inside the instance;
 * `landed` is the one entry the tab that made the request needs — where THIS account ends
 * up — so the browser can move there at once instead of blanking to "ninguna asignatura"
 * until `me` comes back. `null` means it stays where it was, which covers both "I was not
 * in it" and "I have nowhere left to go".
 *
 * `files_removed` says whether the directory tree went with the row. The administrator's
 * deletion always takes it; an owner's own takes it only when nobody else was a member,
 * which is why this is reported rather than assumed from which route was called.
 */
export type WorkspaceGone = {
  deleted: string;
  path: string;
  rehomed: Record<string, string | null>;
  landed: string | null;
  files_removed: boolean;
};

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    /** The server's stable name for the refusal (`X-Error-Code`), or null. What a screen
     *  matches on, never the sentence in `message`. */
    readonly code: string | null = null,
    /** How many seconds the server asks to wait before trying again (`Retry-After`), or
     *  null. What a refusal with a code builds its own sentence's wait from. */
    readonly retryAfter: number | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * `Retry-After` in seconds, or null when absent or unreadable.
 *
 * The server sends seconds; the header may also be an HTTP date, read as the seconds left
 * until it. Only a value with a letter in it is read as a date: `Date.parse` takes "1.5" and
 * "-5" for dates long past, and a wait of zero is not what either says.
 */
export function retryAfterSeconds(header: string | null, now: number = Date.now()): number | null {
  const value = header?.trim() ?? "";
  if (value === "") return null;
  if (/^\d+$/.test(value)) return Number(value);
  if (!/[a-z]/i.test(value)) return null;
  const at = Date.parse(value);
  return Number.isNaN(at) ? null : Math.max(0, Math.round((at - now) / 1000));
}

export interface RequestOptions extends RequestInit {
  /**
   * Read a NAMED instance instead of the one this tab is sitting in.
   *
   * Per request and never global: the tab's workspace stays what every other call means,
   * and the caller that has a slug in its hand — the panel that hands comparisons out,
   * which composes a commission for a workspace it is not standing in — says so on the
   * one call it makes. Setting the store instead would move the whole app under it.
   */
  workspace?: string | null;
}

export async function request<T>(path: string, init?: RequestOptions): Promise<T> {
  const response = await send(path, init);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

/** A call whose answer is a file and not JSON: an image of a page, read as its bytes. */
export async function requestBlob(path: string, init?: RequestOptions): Promise<Blob> {
  return (await send(path, init)).blob();
}

async function send(path: string, init?: RequestOptions): Promise<Response> {
  const { workspace, ...rest } = init ?? {};
  const response = await fetch(path, {
    ...rest,
    // The session is an httpOnly cookie, so nothing here ever reads or sends a token by
    // hand. Stated rather than left to the default because it is the whole auth scheme.
    credentials: "same-origin",
    // `X-Workspace` on EVERY call, in one place: a request that forgot it would silently
    // read whichever instance the account last activated, which is the bug this header
    // exists to prevent. It is a request, not a permission — the server checks membership
    // whatever the header says, and an administrator naming somebody else's instance gets
    // in through the bypass in `auth.deps.access_for` and nowhere else.
    headers: {
      ...(workspace ? { "X-Workspace": workspace } : workspaceHeader()),
      ...(rest.body ? { "Content-Type": "application/json" } : {}),
      ...rest.headers,
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
    throw new ApiError(
      detail,
      response.status,
      response.headers.get("X-Error-Code"),
      retryAfterSeconds(response.headers.get("Retry-After")),
    );
  }

  return response;
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
      else
        reject(
          new ApiError(
            body?.detail ?? `${xhr.status} ${xhr.statusText}`,
            xhr.status,
            xhr.getResponseHeader("X-Error-Code"),
            retryAfterSeconds(xhr.getResponseHeader("Retry-After")),
          ),
        );
    };
    // A key, not a sentence: this rejects into a screen, and the screen knows the
    // language. `ApiError.message` is rendered through `t()` wherever it is shown.
    xhr.onerror = () => reject(new ApiError("api.unreachable", 0));
    xhr.send(form);
  });
}

// Named exports rather than members of `api`, because the two screens that read the
// curriculum — the graph's tab and the generation form — import them by name.
//
// The `workspace` argument is why every caller wraps this in an arrow: react-query hands
// its own context to a bare `queryFn`, which would arrive here as a slug.
export const getCurriculum = (workspace?: string | null) =>
  request<CurriculumState>("/api/kg/curriculum", { workspace });

export const putCurriculum = (concepts: string[], closePrerequisites: boolean) =>
  put<CurriculumState>("/api/kg/curriculum", {
    concepts,
    close_prerequisites: closePrerequisites,
  });

// Named for the same reason: the generation form imports it directly. It 404s until the
// graph and the profile are built, which is what keeps the block off a fresh workspace.
export const getScope = (itemType: string, workspace?: string | null) =>
  request<CommissionScope>(`/api/pipeline/scope?item_type=${encodeURIComponent(itemType)}`, {
    workspace,
  });

export const api = {
  me: () => request<Session>("/api/auth/me"),
  updateMe: (body: { name: string; email: string | null }) =>
    patch<Session>("/api/auth/me", body),
  login: (username: string, password: string) =>
    post<Session>("/api/auth/login", { username, password }),
  logout: () => post<{ ok: boolean }>("/api/auth/logout"),
  logoutAll: () => post<{ ok: boolean; revoked: number }>("/api/auth/logout-all"),
  setLanguage: (language: string) =>
    post<{ ui_language: string }>("/api/auth/language", { language }),
  changePassword: (current: string, next: string) =>
    post<{ ok: boolean }>("/api/auth/password", { current, new: next }),
  forgotPassword: (username: string) => post<{ sent: boolean }>("/api/auth/forgot", { username }),
  resetPassword: (token: string, password: string) =>
    post<Session>("/api/auth/reset", { token, password }),

  invitePreview: (token: string) =>
    request<InvitePreview>(`/api/auth/invites/${encodeURIComponent(token)}`),
  // Nothing about what the account will be: the invitation says it, and nobody is asked.
  acceptInvite: (body: {
    token: string;
    username: string;
    name: string;
    password: string;
    ui_language: string;
  }) => post<Session>("/api/auth/accept", body),

  // An account that already exists entering the subject a link names: either kind of link.
  join: (token: string) => post<JoinedSession>("/api/auth/join", { token }),

  workspaces: () => request<WorkspaceListing>("/api/workspaces"),

  // The people of the subject in use, for its teachers (`server/routers/members.py`).
  members: () => request<{ members: Member[] }>("/api/members"),
  memberAction: (userId: number, action: MemberAction) =>
    action === "remove"
      ? request<{ members: Member[] }>(`/api/members/${userId}`, { method: "DELETE" })
      : post<{ members: Member[] }>(`/api/members/${userId}/${action}`),
  membersBulk: (action: MemberAction, userIds: number[]) =>
    post<MembersBulkResult>("/api/members/bulk", { action, user_ids: userIds }),
  // Ends the course: every active student paused (or removed) and the class link paused.
  endCourse: (action: "disable" | "remove") =>
    post<{ action: string; students: number; class_link_paused: boolean }>(
      "/api/members/end-course",
      { action },
    ),
  // The subject's class link. Its terms travel without the link; the link is a read of its
  // own, and the server logs who made it.
  classLink: () => request<{ class_link: ClassLinkView | null }>("/api/members/class-link"),
  classLinkUrl: () => request<{ link: string }>("/api/members/class-link/link"),
  // Mints the link, or renews it: the live one stops working, and whoever entered stays.
  mintClassLink: (terms: { max_uses: number; expires_at: string | null }) =>
    post<MintedClassLink>("/api/members/class-link", terms),
  editClassLink: (changes: ClassLinkTerms) =>
    patch<{ class_link: ClassLinkView }>("/api/members/class-link", changes),
  // Retires the live link without a new one: it stops working, and whoever entered stays.
  revokeClassLink: () =>
    request<{ revoked: boolean }>("/api/members/class-link", { method: "DELETE" }),
  // What the subject's students do, week by week, for its teachers; `student` narrows it.
  activityWeeks: (student: number | null) =>
    request<ActivityHistory>(`/api/activity/weeks${student ? `?student=${student}` : ""}`),
  activityWeek: (week: string, student: number | null) =>
    request<ActivityWeek>(
      `/api/activity/weeks/${encodeURIComponent(week)}${student ? `?student=${student}` : ""}`,
    ),
  // Queues the week's digest: what the class asked the tutor, in a few themes per concept.
  writeDigest: (week: string) =>
    post<{ job: Job; queue_position: number }>(
      `/api/activity/weeks/${encodeURIComponent(week)}/digest`,
    ),
  // What the subject's students may use; a teacher closes generating or the tutor to them.
  studentUses: () => request<StudentUses>("/api/members/uses"),
  setStudentUses: (changes: Partial<Pick<StudentUses, "generate" | "tutor">>) =>
    patch<StudentUses>("/api/members/uses", changes),
  // The subject's personal invitations, a student's each, one per name.
  // An owner gives a member another role, their own included: how ownership is handed over.
  changeMemberRole: (userId: number, role: Role) =>
    patch<{ member: Member }>(`/api/members/${userId}`, { role }),
  memberInvites: () => request<{ invites: MemberInvite[] }>("/api/members/invites"),
  // A student's each, or — an owner's to mint — a teacher's; `emails` beside the names where
  // the installation sends mail.
  mintMemberInvites: (body: {
    names: string[];
    expires_at: string | null;
    role?: Role;
    emails?: (string | null)[];
  }) => post<{ invites: MintedMemberInvite[] }>("/api/members/invites", { role: "viewer", ...body }),
  memberInviteLink: (id: number) => request<{ link: string }>(`/api/members/invites/${id}/link`),
  revokeMemberInvite: (id: number) =>
    request<{ revoked: boolean }>(`/api/members/invites/${id}`, { method: "DELETE" }),
  // The prompt language travels with the creation and only with it: the relation labels a
  // build writes into the graph are what the loader indexes by, so once anything is built
  // the choice is baked into the artifacts and there is nothing to change it to.
  createWorkspace: (slug: string, name: string, prompt_language: string) =>
    post<{ workspace: WorkspaceRow }>("/api/workspaces", { slug, name, prompt_language }),
  activateWorkspace: (slug: string) =>
    post<{ workspace: WorkspaceRow }>(`/api/workspaces/${encodeURIComponent(slug)}/activate`),
  // The route resolves its permission from the ACTIVE workspace, so the slug travels twice:
  // in the path, and in this call's own `X-Workspace`. Without the second one, deleting a
  // workspace from a list would mean switching into it first — three steps and a screen
  // that reloads twice to do one thing.
  deleteWorkspace: (slug: string) =>
    request<WorkspaceGone>(`/api/workspaces/${encodeURIComponent(slug)}`, {
      method: "DELETE",
      workspace: slug,
    }),
  workspaceSummary: (slug: string) =>
    request<WorkspaceSummary>(`/api/workspaces/${encodeURIComponent(slug)}/summary`),

  health: () => request<Health>("/api/health"),

  // The one call in this file that works with no session, and it has to stay that way:
  // whoever is looking at the login form is exactly who needs to be told the installation
  // is closed.
  maintenance: () => request<MaintenanceState>("/api/maintenance"),

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

  context: (workspace?: string | null) =>
    request<ContentContextState>("/api/context", { workspace }),

  // The three reads a commission is composed from, and the three that take a slug: the
  // panel builds a form against the instance the work will RUN in, which is not always
  // the one the tab is standing in. Omitted, they mean the tab's, exactly as before.
  profile: (workspace?: string | null) => request<ProfilePayload>("/api/profile", { workspace }),
  validateProfile: (profile: ExemplarsProfile) =>
    post<{ valid: boolean; error: string | null }>("/api/profile/validate", { profile }),
  saveProfile: (profile: ExemplarsProfile) => put<{ pipeline: Pipeline }>("/api/profile", { profile }),

  kg: (workspace?: string | null) => request<KgSummary>("/api/kg", { workspace }),
  kgGraph: (workspace?: string | null) => request<GraphView>("/api/kg/graph", { workspace }),
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
  // How many exercises one commission, and the day, may ask for here: a student's are bounded.
  allowance: () => request<Allowance>("/api/jobs/allowance"),
  currentJob: () =>
    request<{ job: Job | null; queued: Job[]; last_seq: number }>("/api/jobs/current"),
  job: (id: string) => request<{ job: Job }>(`/api/jobs/${id}`),
  jobEvents: (id: string, since = 0) =>
    request<{ events: VgEvent[] }>(`/api/jobs/${id}/events?since=${since}`),
  cancelJob: (id: string) =>
    request<{ cancelled: boolean }>(`/api/jobs/${id}`, { method: "DELETE" }),

  // No `scope`: the endpoint answers your own rows and nothing else. `workspace` reads
  // another subject's without switching to it, which is what "Mis asignaturas y
  // ejercicios" does for every subject it lists.
  generations: (
    params: {
      concept?: string;
      item_type?: string;
      q?: string;
      limit?: number;
      offset?: number;
    },
    workspace?: string | null,
  ) => {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "" && value !== null) search.set(key, String(value));
    }
    return request<GenerationListing>(`/api/generations?${search.toString()}`, { workspace });
  },
  generation: (id: string) =>
    request<GenerationDetail>(`/api/generations/${encodeURIComponent(id)}`),
  deleteGeneration: (id: string, workspace?: string | null) =>
    request<{ deleted: string }>(`/api/generations/${encodeURIComponent(id)}`, {
      method: "DELETE",
      workspace,
    }),

  adminOverview: () => request<AdminOverview>("/api/admin/overview"),
  // Read-only, and the one place anybody reads exercises that are not their own.
  adminWorkspaceGenerations: (
    slug: string,
    params: { author?: number; q?: string; limit?: number; offset?: number },
  ) => {
    const search = new URLSearchParams();
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined && value !== "") search.set(key, String(value));
    }
    return request<AdminGenerationListing>(
      `/api/admin/workspaces/${encodeURIComponent(slug)}/generations?${search.toString()}`,
    );
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
  adminCreateInvites: (body: InviteTerms & { count: number }) =>
    post<{ invites?: MintedInvite[]; invite: InviteRow; link: string }>(
      "/api/admin/invites",
      body,
    ),
  // Pasting back the link of an invitation deleted by mistake. Only a link nobody knows
  // creates anything; the outcome says which of the three things happened.
  adminImportInvite: (body: InviteTerms & { link: string }) =>
    post<MintedInvite & { outcome: InviteImportOutcome }>("/api/admin/invites/import", body),
  // A request of its own, and logged: the listing never carries a live link.
  adminInviteLink: (id: number) => request<{ link: string }>(`/api/admin/invites/${id}/link`),
  adminEditInvite: (id: number, changes: Partial<InviteTerms>) =>
    patch<{ invite: InviteRow }>(`/api/admin/invites/${id}`, changes),
  adminRevokeInvite: (id: number) =>
    request<{ revoked: boolean }>(`/api/admin/invites/${id}`, { method: "DELETE" }),
  // Every subject's live class link; the administrator pauses or retires one, and changes
  // nothing else of it — its seats and its date are its teachers'.
  adminClassLinks: () => request<{ class_links: AdminClassLink[] }>("/api/admin/class-links"),
  adminPauseClassLink: (id: number, paused: boolean) =>
    patch<{ id: number; paused: boolean }>(`/api/admin/class-links/${id}`, { paused }),
  adminRevokeClassLink: (id: number) =>
    request<{ revoked: number }>(`/api/admin/class-links/${id}`, { method: "DELETE" }),
  // The one thing the panel writes about instances, and it is deletion. It goes through
  // `/api/admin` and not `/api/workspaces` because the latter requires membership of the
  // active workspace, which would force entering each instance in order to remove it.
  // Renaming is the administrator's and nobody else's: there is no owner-facing route for
  // it any more, so this is the only door.
  adminRenameWorkspace: (slug: string, name: string) =>
    patch<{ slug: string; name: string }>(
      `/api/admin/workspaces/${encodeURIComponent(slug)}`,
      { name },
    ),
  adminDeleteWorkspace: (slug: string) =>
    request<WorkspaceGone>(
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

  adminJobHistory: (limit = 30) =>
    request<{ jobs: Job[] }>(`/api/admin/jobs/history?limit=${limit}`),
  adminClearJobHistory: () =>
    post<{ cleared: boolean }>("/api/admin/jobs/history/clear"),

  // The machine and the process: what is resident, what is on disk, the tunnel that reaches
  // the engine and the contexts this process keeps warm. Every write here is felt by every
  // workspace, which is why they are the administrator's.
  adminEngine: () => request<AdminEngine>("/api/admin/engine"),
  adminReleaseGpu: () => post<{ released: string[] }>("/api/admin/engine/release"),
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
  adminSetAdmin: (userId: number, isAdmin: boolean) =>
    post<{ user_id: number; is_admin: boolean }>(`/api/admin/accounts/${userId}/admin`, {
      is_admin: isAdmin,
    }),
  // The account's profile only climbs, so the one call there is makes a student a teacher:
  // the server refuses anything else (`profile_only_climbs`).
  adminMakeTeacher: (userId: number) =>
    post<{ user_id: number; evaluator_profile: EvaluatorProfile | null }>(
      `/api/admin/accounts/${userId}/profile`,
      { evaluator_profile: "teacher" },
    ),
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
  // Opens again a membership a teacher paused, as the teacher's own «Activar» does.
  adminEnableMembership: (userId: number, workspace: string) =>
    post<{ user_id: number; workspace: string }>(
      `/api/admin/accounts/${userId}/memberships/${encodeURIComponent(workspace)}/enable`,
    ),
  adminRevokeMembership: (userId: number, workspace: string) =>
    request<{ user_id: number; workspace: string }>(
      `/api/admin/accounts/${userId}/memberships/${encodeURIComponent(workspace)}`,
      { method: "DELETE" },
    ),

  // Who each optional function is for. A write without `accounts` leaves the list as it is.
  adminFeatures: () => request<AdminFeaturesPayload>("/api/admin/features"),
  adminSetFeature: (
    feature: FeatureName,
    body: { mode: FeatureMode; accounts?: number[]; workspaces?: string[] },
  ) =>
    put<AdminFeaturesPayload>(`/api/admin/features/${feature}`, body),

  adminMaintenance: () => request<MaintenanceState>("/api/admin/maintenance"),
  setMaintenance: (active: boolean, message: string | null) =>
    post<MaintenanceState>("/api/admin/maintenance", { active, message }),

  adminConfig: () => request<ConfigPayload>("/api/admin/config"),
  updateAdminConfig: (values: Record<string, unknown>) =>
    put<ConfigPayload>("/api/admin/config", { values }),
  reloadAdminConfig: () => post<ConfigPayload>("/api/admin/config/reload"),
  resetAdminConfig: (keys: string[]) => post<ConfigPayload>("/api/admin/config/reset", { keys }),
  adminCerebrasModels: () => request<CerebrasCatalog>("/api/admin/config/cerebras-models"),
};
