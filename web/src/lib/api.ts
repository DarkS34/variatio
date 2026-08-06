import type {
  BankListing,
  ContentProfile,
  Coverage,
  GraphView,
  Health,
  Job,
  KgSummary,
  Pipeline,
  ProfilePayload,
  RawKind,
  RawListing,
  RawSlot,
  RawUpload,
  VgEvent,
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
    headers: init?.body ? { "Content-Type": "application/json", ...init?.headers } : init?.headers,
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
  health: () => request<Health>("/api/health"),

  pipeline: () => request<Pipeline>("/api/pipeline"),
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
  validateProfile: (profile: ContentProfile) =>
    post<{ valid: boolean; error: string | null }>("/api/profile/validate", { profile }),
  saveProfile: (profile: ContentProfile) => put<{ pipeline: Pipeline }>("/api/profile", { profile }),

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
};
