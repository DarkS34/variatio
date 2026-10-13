import type { ArtifactName, JobKind, RawKind } from "@/lib/types";

import { ARTIFACTS, PLANS, Refusal, say, type World } from "./world";

/**
 * THE DEMO'S ROUTES: every path the client calls, answered by the world.
 *
 * What `lib/api.setTransport` is handed while a demo is mounted. The table mirrors the
 * server's routers path by path; a path it does not list answers 404, as the server
 * would, and the screen behind it degrades as it does with an older API. Answers take a
 * moment on purpose: a screen drawn over instant answers never shows the states it was
 * written to show.
 */

type Handler = (world: World, match: RegExpMatchArray, query: URLSearchParams, body: any) => unknown;

interface Route {
  method: string;
  pattern: RegExp;
  handle: Handler;
}

const LATENCY = 20;

const raw = (match: RegExpMatchArray) => decodeURIComponent(match[1]) as RawKind;
const name = (match: RegExpMatchArray, at = 2) => decodeURIComponent(match[at]);

const ROUTES: Route[] = [
  // The account and the installation.
  { method: "GET", pattern: /^\/api\/auth\/me$/, handle: (w) => w.me() },
  { method: "PATCH", pattern: /^\/api\/auth\/me$/, handle: (w) => w.me() },
  { method: "POST", pattern: /^\/api\/auth\/language$/, handle: (w) => w.me() },
  { method: "POST", pattern: /^\/api\/auth\/logout$/, handle: () => ({ ok: true }) },
  { method: "GET", pattern: /^\/api\/maintenance$/, handle: () => ({ active: false, message: "", since: null }) },
  { method: "GET", pattern: /^\/api\/health$/, handle: (w) => w.health() },
  { method: "GET", pattern: /^\/api\/workspaces$/, handle: (w) => w.workspaces() },
  { method: "POST", pattern: /^\/api\/workspaces\/[^/]+\/activate$/, handle: (w) => w.me() },
  { method: "GET", pattern: /^\/api\/members\/uses$/, handle: () => ({ generate: true, tutor: false, tutor_installed: false, tutor_offered: false }) },
  { method: "GET", pattern: /^\/api\/context$/, handle: (w) => w.context() },

  // The pipeline.
  { method: "GET", pattern: /^\/api\/pipeline$/, handle: (w) => w.pipeline() },
  { method: "GET", pattern: /^\/api\/pipeline\/phases$/, handle: () => PLANS },
  { method: "GET", pattern: /^\/api\/pipeline\/scope$/, handle: (w) => w.scope() },
  { method: "GET", pattern: /^\/api\/pipeline\/([a-z_]+)\/history$/, handle: () => ({ snapshots: [] }) },
  { method: "POST", pattern: /^\/api\/pipeline\/([a-z_]+)\/approve$/, handle: (w, m) => w.approve(artifact(m)) },
  { method: "POST", pattern: /^\/api\/pipeline\/([a-z_]+)\/reopen$/, handle: (w, m) => w.reopen(artifact(m)) },

  // The raw material and its reading. The transcription routes go ABOVE `/{kind}/{name}`.
  { method: "GET", pattern: /^\/api\/raw$/, handle: (w) => w.rawListing() },
  { method: "GET", pattern: /^\/api\/raw\/(corpus|exemplars)\/transcription$/, handle: (w, m) => w.transcription(raw(m)) },
  {
    method: "POST",
    pattern: /^\/api\/raw\/(corpus|exemplars)\/transcription$/,
    handle: (w, m) => ({ job: w.submit("transcribe", { slot: raw(m) }), since: w.lastSeq }),
  },
  { method: "GET", pattern: /^\/api\/raw\/(corpus|exemplars)\/transcription\/([^/]+)$/, handle: (w, m) => w.documentPages(raw(m), name(m)) },
  { method: "PUT", pattern: /^\/api\/raw\/(corpus|exemplars)\/transcription\/([^/]+)\/\d+$/, handle: (w, m) => w.documentPages(raw(m), name(m)) },
  { method: "POST", pattern: /^\/api\/raw\/(corpus|exemplars)$/, handle: (w, m, _q, body) => w.uploadRaw(raw(m), fileNames(body)) },
  { method: "DELETE", pattern: /^\/api\/raw\/(corpus|exemplars)\/([^/]+)$/, handle: (w, m) => w.deleteRaw(raw(m), name(m)) },

  // The graph.
  { method: "GET", pattern: /^\/api\/kg$/, handle: (w) => w.kg() },
  { method: "GET", pattern: /^\/api\/kg\/graph$/, handle: (w) => w.kgGraph() },
  { method: "GET", pattern: /^\/api\/kg\/raw$/, handle: (w) => w.kgRaw() },
  { method: "GET", pattern: /^\/api\/kg\/neighbours$/, handle: (w, _m, q) => w.neighbours(q.get("concept") ?? "") },
  { method: "GET", pattern: /^\/api\/kg\/descriptions$/, handle: (w) => w.descriptionsPayload() },
  { method: "PUT", pattern: /^\/api\/kg\/descriptions$/, handle: (w, _m, _q, body) => w.saveDescription(body.concept, body.description) },
  { method: "GET", pattern: /^\/api\/kg\/curriculum$/, handle: (w) => w.curriculumState() },
  { method: "PUT", pattern: /^\/api\/kg\/curriculum$/, handle: (w, _m, _q, body) => w.putCurriculum(body.concepts ?? [], Boolean(body.close_prerequisites)) },
  { method: "POST", pattern: /^\/api\/kg\/domains$/, handle: (w, _m, _q, body) => w.addDomain(body.name) },
  { method: "PATCH", pattern: /^\/api\/kg\/domains$/, handle: (w, _m, _q, body) => w.renameDomain(body.name, body.new_name) },
  { method: "POST", pattern: /^\/api\/kg\/domains\/delete$/, handle: (w, _m, _q, body) => w.deleteDomain(body.name, body.move_to ?? null) },
  { method: "PUT", pattern: /^\/api\/kg\/domains\/order$/, handle: (w, _m, _q, body) => w.reorderDomains(body.order ?? []) },
  { method: "POST", pattern: /^\/api\/kg\/concepts$/, handle: (w, _m, _q, body) => w.addConcept(body.name, body.domain, body.taggable ?? true) },
  { method: "PATCH", pattern: /^\/api\/kg\/concepts$/, handle: (w, _m, _q, body) => w.updateConcept(body) },
  { method: "POST", pattern: /^\/api\/kg\/concepts\/delete$/, handle: (w, _m, _q, body) => w.deleteConcept(body.name) },
  { method: "POST", pattern: /^\/api\/kg\/relations\/edges$/, handle: (w, _m, _q, body) => w.addEdge(body.relation, body.source, body.target) },
  { method: "POST", pattern: /^\/api\/kg\/relations\/edges\/delete$/, handle: (w, _m, _q, body) => w.removeEdge(body.relation, body.source, body.target) },

  // The types of exercise.
  { method: "GET", pattern: /^\/api\/profile$/, handle: (w) => w.profilePayload() },
  { method: "POST", pattern: /^\/api\/profile\/validate$/, handle: () => ({ valid: true, error: null }) },
  { method: "PUT", pattern: /^\/api\/profile$/, handle: (w, _m, _q, body) => w.saveProfile(body.profile) },

  // The bank.
  { method: "GET", pattern: /^\/api\/bank$/, handle: (w, _m, q) => w.bankListing(q) },
  { method: "GET", pattern: /^\/api\/bank\/coverage$/, handle: (w) => w.coverage() },
  { method: "PATCH", pattern: /^\/api\/bank\/([^/]+)$/, handle: (w, m, _q, body) => w.patchItem(name(m, 1), body.fields ?? {}) },
  { method: "PUT", pattern: /^\/api\/bank\/([^/]+)\/concepts$/, handle: (w, m, _q, body) => w.setConcepts(name(m, 1), body.concepts ?? [], body.primary_concept ?? null) },
  { method: "DELETE", pattern: /^\/api\/bank\/([^/]+)$/, handle: (w, m) => w.deleteItem(name(m, 1)) },

  // The jobs.
  { method: "POST", pattern: /^\/api\/jobs$/, handle: (w, _m, _q, body) => ({ job: w.submit(body.kind as JobKind, body.params ?? {}), since: w.lastSeq }) },
  { method: "GET", pattern: /^\/api\/jobs$/, handle: (w) => ({ jobs: w.jobs.map((job) => w.jobDict(job)) }) },
  { method: "GET", pattern: /^\/api\/jobs\/allowance$/, handle: (w) => w.allowance() },
  { method: "GET", pattern: /^\/api\/jobs\/current$/, handle: (w) => w.jobsCurrent() },
  { method: "GET", pattern: /^\/api\/jobs\/([a-f0-9]+)$/, handle: (w, m) => ({ job: w.jobOf(m[1]) }) },
  { method: "DELETE", pattern: /^\/api\/jobs\/([a-f0-9]+)$/, handle: (w, m) => w.cancel(m[1]) },

  // The exercises.
  { method: "GET", pattern: /^\/api\/generations$/, handle: (w, _m, q) => w.generationsListing(q) },
  { method: "GET", pattern: /^\/api\/generations\/([^/]+)$/, handle: (w, m) => w.generationDetail(name(m, 1)) },
  { method: "DELETE", pattern: /^\/api\/generations\/([^/]+)$/, handle: (w, m) => w.deleteGeneration(name(m, 1)) },
];

function artifact(match: RegExpMatchArray): ArtifactName {
  const candidate = match[1] as ArtifactName;
  if (!ARTIFACTS.includes(candidate)) throw new Refusal(404, say("unknown_job", { name: candidate }));
  return candidate;
}

/** The names of the files an upload carries, read off its `FormData`. */
function fileNames(body: unknown): string[] {
  if (!(body instanceof FormData)) return [];
  return body.getAll("files").map((entry) => (entry instanceof File ? entry.name : String(entry)));
}

function parseBody(init: RequestInit): unknown {
  const body = init.body;
  if (body === undefined || body === null) return undefined;
  if (typeof body === "string") {
    try {
      return JSON.parse(body);
    } catch {
      return undefined;
    }
  }
  return body;
}

function json(data: unknown, status = 200, headers: Record<string, string> = {}): Response {
  if (data === undefined) return new Response(null, { status: 204, headers });
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });
}

/** Answer one request of the client off the world, as the server would. */
export function answer(world: World, path: string, init: RequestInit = {}): Response {
  const url = new URL(path, "http://demo.invalid");
  const method = (init.method ?? "GET").toUpperCase();
  const route = ROUTES.find((candidate) => candidate.method === method && candidate.pattern.test(url.pathname));
  if (!route) return json({ detail: say("no_route", { name: `${method} ${url.pathname}` }) }, 404);
  const match = url.pathname.match(route.pattern)!;
  try {
    return json(route.handle(world, match, url.searchParams, parseBody(init)));
  } catch (error) {
    if (error instanceof Refusal) {
      return json({ detail: error.message }, error.status, error.code ? { "X-Error-Code": error.code } : {});
    }
    return json({ detail: error instanceof Error ? error.message : String(error) }, 500);
  }
}

/** The transport `lib/api` sends through while a demo is mounted. */
export function transportFor(world: World): (path: string, init: RequestInit) => Promise<Response> {
  return (path, init) =>
    new Promise((resolve) => {
      world.schedule(LATENCY, () => resolve(answer(world, path, init)));
    });
}
