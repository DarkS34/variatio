import type { Language } from "@/lib/i18n";
import type {
  Allowance,
  ArtifactName,
  ArtifactStatus,
  BankItem,
  BankListing,
  BuildPlans,
  CommissionScope,
  ContentContextState,
  Coverage,
  CurriculumState,
  ExemplarsProfile,
  GenerationDetail,
  GenerationListing,
  GenerationRow,
  GraphView,
  Health,
  Job,
  JobKind,
  KgSummary,
  Pipeline,
  ProfilePayload,
  RawFile,
  RawKind,
  RawListing,
  RawSlot,
  RawUpload,
  Session,
  StageState,
  VgEvent,
  WorkspaceListing,
} from "@/lib/types";
import { runStore } from "@/state/runStore";

import plans from "./data/plans.json";
import server from "./data/server.json";
import subject from "./data/subject.json";
import { simulate } from "./jobs";

/**
 * THE DEMO'S SERVER, IN MEMORY: one subject of sample data and every answer the real
 * screens ask of `/api/*`, plus the jobs that change it.
 *
 * The landing draws the real client over this — the shell, the three steps and «Generar
 * ejercicios» — so what the visitor sees is the application and not a drawing of it. The
 * shapes answered here are the server's (the server's routes), read off a real installation
 * on 2026-10-12; the contents are lorem ipsum, by the user's request. Nothing here reaches
 * the wire, and nothing of the real session is read or written: the transport is swapped
 * (`lib/api.setTransport`) and the run store is driven (`runStore.drive`) while a demo is
 * mounted, and both are put back when it leaves.
 *
 * Two presets: `fresh`, a new subject — both origins empty and nothing built — so the
 * visitor walks the construction from step 1; and `ready`, where the whole construction is
 * closed and the door is open.
 */

export type Preset = "fresh" | "ready";

/** When the first sample document lands after the demo opens, and the gap to the next, in ms. */
const ARRIVE_FIRST = 500;
const ARRIVE_EVERY = 250;

export interface WorldOptions {
  preset: Preset;
  /** The interface language, read on every answer: the demo follows the landing's switch. */
  language: () => Language;
  /** The subject's and the teacher's names, in the landing's language. */
  subjectName: () => string;
  teacherName: () => string;
}

/** A refusal the transport turns into an HTTP answer, as the server's `HTTPException`. */
export class Refusal extends Error {
  constructor(
    readonly status: number,
    detail: string,
    readonly code: string | null = null,
  ) {
    super(detail);
  }
}

/**
 * One of the server's own sentences, as the real one says them: the API speaks Spanish
 * whatever the account reads (the screens name what they can by key). Data, not copy.
 */
export function say(key: Exclude<keyof typeof server, "stage_labels" | "job_labels">, params: Record<string, string> = {}): string {
  return server[key].replace(/\{(\w+)\}/g, (whole, name: string) => params[name] ?? whole);
}

export const ARTIFACTS: ArtifactName[] = ["knowledge_graph", "exemplars_profile", "exemplars_bank"];

const STAGE_LABEL = server.stage_labels as Record<ArtifactName, string>;

const BUILD_JOB: Record<ArtifactName, JobKind> = {
  knowledge_graph: "build_kg",
  exemplars_profile: "build_profile",
  exemplars_bank: "review_taggability",
};

/** The slot each artifact is built from (`server/approvals.RAW_SOURCE`). */
const RAW_SOURCE: Record<ArtifactName, RawKind> = {
  knowledge_graph: "corpus",
  exemplars_profile: "exemplars",
  exemplars_bank: "exemplars",
};

/** `server/jobs/catalogue.JOB_LABELS`: the fallback a screen names a job by. */
export const JOB_LABEL: Record<string, string> = server.job_labels;

const JOB_ARTIFACT: Partial<Record<string, ArtifactName>> = {
  build_profile: "exemplars_profile",
  build_kg: "knowledge_graph",
  build_bank: "exemplars_bank",
  tag: "exemplars_bank",
};

/** The bank's collection: the review heads it, and two links follow (`pipeline/chain.py`). */
const BANK_CHAIN: readonly JobKind[] = ["review_taggability", "build_bank", "index"];

/** The three relations of the sample graph, as the loader indexes them, in prompt language. */
export const RELATIONS = subject.relations;

/** The plans the client draws a build's bar from (`/api/pipeline/phases`): data, as the server's. */
export const PLANS = plans as BuildPlans;

interface Edge {
  relation: number;
  source: string;
  target: string;
}

interface StageRecord {
  status: ArtifactStatus;
  approved_at: string | null;
  hash: string | null;
}

interface Concept {
  name: string;
  domain: string;
  taggable: boolean;
}

type Slot = { files: RawFile[]; read: Set<string>; pages: Map<string, number> };

const hex = (n: number) => Array.from({ length: n }, () => Math.floor(Math.random() * 16).toString(16)).join("");
const now = () => Date.now() / 1000;
const stamp = () => new Date().toISOString().slice(0, 19);

export class World {
  readonly slug: string = subject.slug;
  readonly options: WorldOptions;

  stages: Record<ArtifactName, StageRecord>;
  raw: Record<RawKind, Slot>;
  /** A slot's documents changed after its artifacts were built: what `stale_because` names. */
  drift: Record<RawKind, { added: string[]; removed: string[] }> = {
    corpus: { added: [], removed: [] },
    exemplars: { added: [], removed: [] },
  };
  jobs: Job[] = [];
  domains: string[];
  concepts: Concept[];
  edges: Edge[];
  descriptions: Map<string, string | null>;
  curriculum: string[] = [];
  curriculumAt: string | null = null;
  profile: ExemplarsProfile;
  bank: BankItem[];
  generations: GenerationRow[] = [];
  private seq = 0;
  private version = 0;
  private listeners = new Set<() => void>();
  private arriving = 0;
  private arrived = false;
  private timers = new Set<ReturnType<typeof setTimeout>>();
  private stopped = false;

  constructor(options: WorldOptions) {
    this.options = options;
    const ready = options.preset === "ready";
    const built = (): StageRecord =>
      ready ? { status: "approved", approved_at: stamp(), hash: hex(64) } : { status: "missing", approved_at: null, hash: null };
    this.stages = { knowledge_graph: built(), exemplars_profile: built(), exemplars_bank: built() };
    // A fresh subject has nothing in either origin, as a new one in the application: step 1
    // is the one to do, and it reads as done once both hold a document (`lib/steps`). The
    // sample documents arrive by themselves a moment later (`arrive`).
    const slot = (files: typeof subject.raw.corpus): Slot => ({
      files: ready
        ? files.map(({ name, bytes, extension }) => ({ name, bytes, extension, modified: now() - 86_400 }))
        : [],
      read: new Set(ready ? files.map((file) => file.name) : []),
      pages: new Map(ready ? files.map((file) => [file.name, file.pages]) : []),
    });
    this.raw = { corpus: slot(subject.raw.corpus), exemplars: slot(subject.raw.exemplars) };
    this.domains = subject.units.map((unit) => unit.name);
    this.concepts = subject.units.flatMap((unit) =>
      unit.concepts.map((name) => ({ name, domain: unit.name, taggable: !subject.nonTaggable.includes(name) })),
    );
    this.edges = [
      ...subject.prerequisites.map(([source, target]) => ({ relation: 0, source, target })),
      ...subject.hierarchy.map(([source, target]) => ({ relation: 1, source, target })),
      ...subject.related.map(([source, target]) => ({ relation: 2, source, target })),
    ];
    this.descriptions = new Map(Object.entries(subject.descriptions));
    this.profile = JSON.parse(JSON.stringify(subject.profile)) as ExemplarsProfile;
    this.bank = JSON.parse(JSON.stringify(subject.bank)) as BankItem[];
    if (ready) {
      this.curriculum = [...subject.progress];
      this.curriculumAt = stamp();
      subject.generations.forEach((row, index) => this.addGeneration(this.rowOf(row, `20261010T091${index}00-${hex(12)}-1`, index)));
    }
  }

  /* TIME ------------------------------------------------------------------------------- */

  /** Run `fn` after `ms`, unless the demo has been stopped by then. */
  schedule(ms: number, fn: () => void): void {
    if (this.stopped) return;
    const id = setTimeout(() => {
      this.timers.delete(id);
      if (!this.stopped) fn();
    }, ms);
    this.timers.add(id);
  }

  /** The same, for a step of `job`: skipped once the job is no longer running. */
  later(job: Job, ms: number, fn: () => void): void {
    this.schedule(ms, () => {
      if (job.status === "running") fn();
    });
  }

  /** Drop every timer: the demo is leaving the screen. */
  stop(): void {
    this.stopped = true;
    for (const id of this.timers) clearTimeout(id);
    this.timers.clear();
    this.arriving = 0;
  }

  /** Take timers again: the frame mounts the same world twice under StrictMode. */
  resume(): void {
    this.stopped = false;
  }

  /* EVENTS ----------------------------------------------------------------------------- */

  /** Hand one event to the run store, stamped as the bus stamps it. */
  emit(job: Job | null, kind: string, payload: Record<string, unknown> = {}): void {
    const event: VgEvent = { seq: ++this.seq, ts: now(), job_id: job?.id ?? null, kind, ...payload };
    runStore.ingest([event]);
  }

  get lastSeq(): number {
    return this.seq;
  }

  /* THE ACCOUNT ------------------------------------------------------------------------ */

  me(): Session {
    return {
      user: {
        id: 1,
        username: "docente",
        email: null,
        name: this.options.teacherName(),
        is_admin: false,
        evaluator_profile: "teacher",
        ui_language: this.options.language(),
      },
      workspaces: [{ slug: this.slug, name: this.options.subjectName(), role: "owner", active: true }],
      active_workspace: this.slug,
      role: "owner",
      mail_configured: false,
      // «Mi clase» closed too: the sample subject has no class to show.
      features: { generate: true, evaluation: false, tutor: false, class: false },
    };
  }

  workspaces(): WorkspaceListing {
    return {
      workspaces: [
        {
          slug: this.slug,
          name: this.options.subjectName(),
          role: "owner",
          active: true,
          prompt_language: "es",
          as_admin: false,
          exercises: this.generations.length,
          // No `people`: without a count, the row offers no way into the class.
          disabled: false,
        } as WorkspaceListing["workspaces"][number],
      ],
      active: this.slug,
      can_create: true,
    };
  }

  health(): Health {
    const offered = ["qwen3.8:27b-q8_0", "gemma-4-31b"];
    return {
      engine: "ollama",
      host: "http://localhost:11434",
      available: true,
      models: {
        required: { GUARDRAIL_LLM: "granite4.1-guardian:8b-q4_K_M", EMBEDDING_LLM: "qwen3-embedding:4b", "GENERATION_MODELS[0]": offered[0] },
        offered,
        fixed_effort: [],
        fixed_effort_levels: {},
        installed: [...offered, "granite4.1-guardian:8b-q4_K_M", "qwen3-embedding:4b"],
        missing: [],
        remote: [],
        running: [],
      },
      context_ready: true,
      paths: {
        artifacts: `/workspaces/${this.slug}/artifacts`,
        raw_exemplars: `/workspaces/${this.slug}/raw/raw_exemplars_bank`,
        raw_corpus: `/workspaces/${this.slug}/raw/raw_corpus`,
        raw_exemplars_exists: true,
        raw_corpus_exists: true,
      },
      busy: this.live().some((job) => job.status === "running"),
    };
  }

  allowance(): Allowance {
    return { max_items: 20, daily_items: null, used_today: 0 };
  }

  scope(): CommissionScope {
    return subject.scope[this.options.language()] as CommissionScope;
  }

  context(): ContentContextState {
    const block = subject.context.narrative;
    return {
      exists: true,
      narrative: block,
      facts: subject.context.facts,
      block,
      source: "draft",
      path: `/workspaces/${this.slug}/artifacts/content_context_autogenerated.json`,
      pending_draft: null,
      canonical_keys: ["subject", "educational_level", "language_of_instruction"],
    };
  }

  /* THE PIPELINE ----------------------------------------------------------------------- */

  /** Every job still queued or running. */
  live(): Job[] {
    return this.jobs.filter((job) => job.status === "queued" || job.status === "running");
  }

  /** Whether a build of this artifact is live: the pipeline then reads it as building. */
  private building(artifact: ArtifactName): boolean {
    return this.live().some((job) =>
      artifact === "exemplars_bank" ? BANK_CHAIN.includes(job.kind) : JOB_ARTIFACT[job.kind] === artifact,
    );
  }

  stageState(artifact: ArtifactName): StageState {
    const record = this.stages[artifact];
    const building = this.building(artifact);
    const exists = record.status !== "missing";
    const drift = this.drift[RAW_SOURCE[artifact]];
    const drifted = exists && (drift.added.length > 0 || drift.removed.length > 0);
    const status: ArtifactStatus = building ? "building" : drifted && record.status !== "missing" ? "stale" : record.status;
    const upstream: ArtifactName[] =
      artifact === "exemplars_bank" ? ["knowledge_graph", "exemplars_profile"] : [];
    const blockedBy = upstream.filter((name) => this.stages[name].status !== "approved");
    const transcribing = this.live().find(
      (job) => job.kind === "transcribe" && job.params.slot === RAW_SOURCE[artifact],
    );
    return {
      artifact,
      label: STAGE_LABEL[artifact],
      status,
      hash: record.hash,
      path: exists ? `/workspaces/${this.slug}/artifacts/${artifact}.json` : null,
      is_autogenerated: artifact === "exemplars_profile" && exists,
      approved_at: record.approved_at,
      stale_because: drifted
        ? [
            {
              slot: RAW_SOURCE[artifact],
              label: STAGE_LABEL[artifact],
              reason: say("stale_documents"),
              added: drift.added,
              removed: drift.removed,
              changed: [],
            },
          ]
        : [],
      blocked_by: blockedBy,
      blocked_reason: blockedBy.length ? say("blocked_by", { names: blockedBy.map((name) => STAGE_LABEL[name]).join(", ") }) : null,
      build_job: BUILD_JOB[artifact],
      transcribing_slot: transcribing ? RAW_SOURCE[artifact] : null,
    };
  }

  pipeline(): Pipeline {
    const stages = ARTIFACTS.map((artifact) => this.stageState(artifact));
    const running = this.jobs.filter((job) => job.status === "running");
    const waiting = this.jobs.filter((job) => job.status === "queued");
    const holder = running[0] ?? null;
    return {
      stages,
      generation_unlocked: stages.every((stage) => stage.status === "approved"),
      current_job: holder ?? waiting[0] ?? null,
      queued: waiting.length,
      queue_length: running.length + waiting.length,
      queue_ahead: null,
      engine_busy: running.length > 0,
      engine_busy_elsewhere: false,
      lanes: {
        local: {
          busy: running.length > 0,
          running: running.length,
          capacity: 1,
          mine: running.length > 0,
          kind: holder?.kind ?? null,
          label: holder?.label ?? null,
          queued: waiting.length,
          ahead: waiting.length ? 0 : null,
        },
        remote: { busy: false, running: 0, capacity: 4, mine: false, kind: null, label: null, queued: 0, ahead: null },
      },
    };
  }

  approve(artifact: ArtifactName): Pipeline {
    const record = this.stages[artifact];
    if (record.status === "missing") throw new Refusal(409, say("nothing_to_approve"));
    record.status = "approved";
    record.approved_at = stamp();
    return this.pipeline();
  }

  reopen(artifact: ArtifactName): Pipeline {
    const record = this.stages[artifact];
    if (record.status === "approved") record.status = "draft";
    return this.pipeline();
  }

  /** A hand edit withdraws the stage's approval, as the server does. */
  private withdraw(artifact: ArtifactName): void {
    const record = this.stages[artifact];
    if (record.status === "approved") record.status = "draft";
  }

  /** What a build leaves: a draft with a new hash, and the drift it was built over cleared. */
  built(artifact: ArtifactName, approved = false): void {
    this.stages[artifact] = { status: approved ? "approved" : "draft", approved_at: approved ? stamp() : null, hash: hex(64) };
    this.drift[RAW_SOURCE[artifact]] = { added: [], removed: [] };
  }

  /** What a cancelled or failed build leaves: nothing new. */
  unbuilt(artifact: ArtifactName): void {
    if (this.stages[artifact].status === "missing") return;
  }

  /* THE RAW MATERIAL ------------------------------------------------------------------- */

  rawSlot(kind: RawKind): RawSlot {
    const slot = this.raw[kind];
    return {
      kind,
      label: say(kind === "corpus" ? "slot_corpus_label" : "slot_exemplars_label"),
      purpose: say(kind === "corpus" ? "slot_corpus_purpose" : "slot_exemplars_purpose"),
      feeds: kind === "corpus" ? ["knowledge_graph"] : ["exemplars_profile", "exemplars_bank"],
      path: `/workspaces/${this.slug}/raw/${kind === "corpus" ? "raw_corpus" : "raw_exemplars_bank"}`,
      exists: true,
      files: slot.files,
      bytes: slot.files.reduce((sum, file) => sum + file.bytes, 0),
    };
  }

  rawListing(): RawListing {
    return {
      supported_extensions: [".pdf", ".docx", ".pptx", ".md", ".txt"],
      max_bytes: 536_870_912,
      max_files: 100,
      max_request_bytes: 1_073_741_824,
      max_slot_bytes: 4_294_967_296,
      slots: [this.rawSlot("corpus"), this.rawSlot("exemplars")],
    } as RawListing;
  }

  transcription(kind: RawKind) {
    const slot = this.raw[kind];
    const documents = slot.files.map((file) => {
      const pages = slot.pages.get(file.name) ?? 1;
      const done = slot.read.has(file.name);
      return {
        name: file.name,
        pages,
        state: done ? "done" : "pending",
        reasons: [],
        chars: done ? pages * 2_150 : 0,
        seams_merged: done ? Math.floor(pages / 3) : 0,
        failed_pages: 0,
        retry_pages: 0,
        images: done && file.extension !== ".md" ? 1 : 0,
        images_unreadable: 0,
      };
    });
    const done = documents.filter((document) => document.state === "done").length;
    return {
      slot: kind,
      documents,
      done,
      pending: documents.length - done,
      stale: 0,
      retry: 0,
      total_pages: documents.reduce((sum, document) => sum + document.pages, 0),
    };
  }

  documentPages(kind: RawKind, name: string) {
    const slot = this.raw[kind];
    if (!slot.files.some((file) => file.name === name)) throw new Refusal(404, say("document_missing"));
    const count = slot.pages.get(name) ?? 1;
    const pages = Array.from({ length: count }, (_, index) => {
      const text = `## ${name.replace(/\.[a-z]+$/, "")} · ${index + 1}\n\n${subject.pages[index % subject.pages.length]}`;
      return { index: index + 1, text, chars: text.length, failed: false };
    });
    return { name, pages, original: null };
  }

  markRead(kind: RawKind, name: string): void {
    this.raw[kind].read.add(name);
  }

  /**
   * Hear every change of the origins' documents: the demo's bar offers the samples while
   * one origin is empty, and the frame refreshes the application's readings when the bar
   * adds them, since that change comes from outside the application.
   */
  subscribe = (listener: () => void): (() => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  /** A number that moves with every change of the origins, for `useSyncExternalStore`. */
  getVersion = (): number => this.version;

  private touched(): void {
    this.version += 1;
    for (const listener of this.listeners) listener();
  }

  /** Whether an origin has no document yet: what the samples are offered for. */
  missingDocuments(): boolean {
    return this.raw.corpus.files.length === 0 || this.raw.exemplars.files.length === 0;
  }

  /** Put the sample subject's documents in every origin that does not hold them yet. */
  addSamples(): void {
    for (const { kind, file } of this.samplesMissing()) this.addSample(kind, file);
    this.touched();
  }

  /** Whether the sample documents are on their way (`arrive`): the demo's bar says so. */
  isArriving(): boolean {
    return this.arriving > 0;
  }

  /**
   * Bring the sample documents in by themselves, one after another, as a teacher's upload
   * would (the user's request, 2026-10-12: «deja ficheros ya cargados, los usuarios solo
   * tienen que esperar»). A fresh demo opens on step 1 with its origins empty, «Te toca
   * ahora»; a moment later the documents land and the step reads done, with nothing to press.
   * Once per world: a document the visitor deletes afterwards is not brought back. A stop
   * half way (the frame's cleanup) leaves the rest to the next call.
   */
  arrive(): void {
    if (this.arrived) return;
    const missing = this.samplesMissing();
    if (!missing.length) {
      this.arrived = true;
      return;
    }
    this.arriving = missing.length;
    this.touched();
    missing.forEach(({ kind, file }, index) =>
      this.schedule(ARRIVE_FIRST + index * ARRIVE_EVERY, () => {
        this.addSample(kind, file);
        this.arriving -= 1;
        if (this.arriving === 0) this.arrived = true;
        this.touched();
      }),
    );
  }

  private samplesMissing() {
    return (["corpus", "exemplars"] as const).flatMap((kind) =>
      subject.raw[kind]
        .filter((file) => !this.raw[kind].files.some((held) => held.name === file.name))
        .map((file) => ({ kind, file })),
    );
  }

  private addSample(kind: RawKind, file: (typeof subject.raw.corpus)[number]): void {
    const slot = this.raw[kind];
    if (slot.files.some((held) => held.name === file.name)) return;
    slot.files.push({ name: file.name, bytes: file.bytes, extension: file.extension, modified: now() });
    slot.pages.set(file.name, file.pages);
    this.noteDrift(kind, "added", file.name);
  }

  pagesOf(kind: RawKind): { name: string; pages: number }[] {
    const slot = this.raw[kind];
    return slot.files.map((file) => ({ name: file.name, pages: slot.pages.get(file.name) ?? 1 }));
  }

  uploadRaw(kind: RawKind, names: string[]): RawUpload {
    const slot = this.raw[kind];
    const added = [];
    for (const name of names) {
      if (slot.files.some((file) => file.name === name)) continue;
      const extension = /\.[a-z0-9]+$/i.exec(name)?.[0].toLowerCase() ?? "";
      const bytes = 40_000 + Math.floor(Math.random() * 900_000);
      slot.files.push({ name, bytes, extension, modified: now() });
      slot.pages.set(name, 3 + Math.floor(Math.random() * 9));
      added.push({ name, bytes, renamed: false });
      this.noteDrift(kind, "added", name);
    }
    this.touched();
    return { added, rejected: [], slot: this.rawSlot(kind) };
  }

  deleteRaw(kind: RawKind, name: string): { deleted: string; slot: RawSlot } {
    const slot = this.raw[kind];
    if (!slot.files.some((file) => file.name === name)) throw new Refusal(404, say("document_missing"));
    slot.files = slot.files.filter((file) => file.name !== name);
    slot.read.delete(name);
    slot.pages.delete(name);
    this.noteDrift(kind, "removed", name);
    this.touched();
    return { deleted: name, slot: this.rawSlot(kind) };
  }

  /** A document added or removed after a build from its slot leaves that stage stale. */
  private noteDrift(kind: RawKind, how: "added" | "removed", name: string): void {
    const fed = ARTIFACTS.filter((artifact) => RAW_SOURCE[artifact] === kind);
    if (!fed.some((artifact) => this.stages[artifact].status !== "missing")) return;
    this.drift[kind][how].push(name);
  }

  /* THE GRAPH ---------------------------------------------------------------------------- */

  private requireGraph(): void {
    if (this.stages.knowledge_graph.status === "missing") throw new Refusal(404, say("graph_missing"));
  }

  private requireBank(): void {
    if (this.stages.exemplars_bank.status === "missing") throw new Refusal(404, say("bank_missing"));
  }

  private exemplarsOf(name: string): BankItem[] {
    if (this.stages.exemplars_bank.status === "missing") return [];
    return this.bank.filter((item) => item.primary_concept === name);
  }

  kg(): KgSummary {
    this.requireGraph();
    const degree = new Map<string, number>();
    for (const edge of this.edges) {
      degree.set(edge.source, (degree.get(edge.source) ?? 0) + 1);
      degree.set(edge.target, (degree.get(edge.target) ?? 0) + 1);
    }
    const concepts = this.concepts.map((concept) => {
      const exemplars = this.exemplarsOf(concept.name);
      const byType: Record<string, number> = {};
      for (const item of exemplars) {
        if (item.item_type) byType[item.item_type] = (byType[item.item_type] ?? 0) + 1;
      }
      return {
        name: concept.name,
        domain: concept.domain,
        taggable: concept.taggable,
        degree: degree.get(concept.name) ?? 0,
        description: this.descriptions.get(concept.name) ?? null,
        exemplars: exemplars.length,
        exemplars_by_type: byType,
      };
    });
    return {
      path: `/workspaces/${this.slug}/artifacts/knowledge_graph.json`,
      domains: this.domains.map((name) => ({ name, concepts: this.concepts.filter((c) => c.domain === name).map((c) => c.name) })),
      concepts,
      relations: RELATIONS.map((relation, index) => ({
        name: relation.key,
        details: { verbose: relation.key, directed: relation.directed, acyclic: relation.acyclic, use_in_embedding: relation.use_in_embedding },
        edges: this.edges.filter((edge) => edge.relation === index).length,
      })),
      totals: {
        domains: this.domains.length,
        concepts: concepts.length,
        taggable: concepts.filter((concept) => concept.taggable).length,
        described: concepts.filter((concept) => concept.description).length,
        with_exemplars: concepts.filter((concept) => concept.exemplars > 0).length,
        taggability_reviewed: this.stages.exemplars_bank.status !== "missing",
      },
    };
  }

  kgGraph(): GraphView {
    this.requireGraph();
    const index = new Map(this.concepts.map((concept, position) => [concept.name, position]));
    return {
      meta: { title: say("graph_title"), kind: "curated", generated: stamp().replace("T", " ").slice(0, 16), isolated: 0, prerequisite: 0 },
      relations: RELATIONS.map((relation, position) => ({
        key: relation.key,
        verbose: relation.key,
        type: relation.type,
        directed: relation.directed,
        acyclic: relation.acyclic,
        use_in_embedding: relation.use_in_embedding,
        prerequisite: relation.prerequisite,
        count: this.edges.filter((edge) => edge.relation === position).length,
      })),
      groups: this.domains.map((name) => ({ name, count: this.concepts.filter((concept) => concept.domain === name).length })),
      nodes: this.concepts.map((concept) => [concept.name, this.domains.indexOf(concept.domain), concept.taggable ? 0 : 1]),
      links: this.edges
        .filter((edge) => index.has(edge.source) && index.has(edge.target))
        .map((edge) => [index.get(edge.source)!, index.get(edge.target)!, edge.relation]),
    };
  }

  kgRaw(): { graph: Record<string, unknown> } {
    this.requireGraph();
    return {
      graph: {
        concepts_by_domains: Object.fromEntries(this.domains.map((name) => [name, this.concepts.filter((c) => c.domain === name).map((c) => c.name)])),
        generic_non_taggable_concepts: this.concepts.filter((c) => !c.taggable).map((c) => c.name),
        taggability_reviewed: true,
        relations: RELATIONS.map((relation, position) => ({
          ...relation,
          edges: this.edges.filter((edge) => edge.relation === position).map((edge) => [edge.source, edge.target]),
        })),
      },
    };
  }

  neighbours(name: string) {
    this.requireGraph();
    const relations: Record<string, { out: string[]; in: string[]; directed: boolean }> = {};
    RELATIONS.forEach((relation, position) => {
      const edges = this.edges.filter((edge) => edge.relation === position);
      relations[relation.key] = {
        out: edges.filter((edge) => edge.source === name).map((edge) => edge.target),
        in: edges.filter((edge) => edge.target === name).map((edge) => edge.source),
        directed: relation.directed,
      };
    });
    return { concept: name, relations };
  }

  descriptionsPayload() {
    this.requireGraph();
    const descriptions: Record<string, string | null> = {};
    for (const concept of this.concepts) descriptions[concept.name] = this.descriptions.get(concept.name) ?? null;
    return {
      descriptions,
      missing: this.concepts.filter((concept) => !this.descriptions.get(concept.name)).map((concept) => concept.name),
      sources: subject.sources as Record<string, { document: string; location: string; text: string }[]>,
      many_documents: true,
      unanchored: [],
    };
  }

  saveDescription(name: string, description: string): { concept: string } {
    this.descriptions.set(name, description.trim() || null);
    this.withdraw("knowledge_graph");
    return { concept: name };
  }

  /** Every concept, in the order of the syllabus: the demo's descriptions are written in it. */
  conceptNames(): string[] {
    return this.concepts.map((concept) => concept.name);
  }

  /** The descriptions a build leaves behind, before `describe_concepts` writes them. */
  forgetDescriptions(): void {
    for (const concept of this.concepts) this.descriptions.set(concept.name, null);
  }

  describe(name: string): void {
    const words = subject.lorem;
    const pick = () => words[Math.floor(Math.random() * words.length)];
    const text = `${pick()[0].toUpperCase()}${pick().slice(1)} ${Array.from({ length: 14 }, pick).join(" ")}.`;
    this.descriptions.set(name, text);
  }

  updateConcept(body: { name: string; new_name?: string | null; domain?: string | null; taggable?: boolean | null }) {
    this.requireGraph();
    const concept = this.concepts.find((candidate) => candidate.name === body.name);
    if (!concept) throw new Refusal(404, say("concept_missing", { name: body.name }));
    if (body.taggable !== undefined && body.taggable !== null) concept.taggable = body.taggable;
    if (body.domain) concept.domain = body.domain;
    if (body.new_name && body.new_name !== body.name) {
      const from = body.name;
      const to = body.new_name;
      concept.name = to;
      for (const edge of this.edges) {
        if (edge.source === from) edge.source = to;
        if (edge.target === from) edge.target = to;
      }
      this.descriptions.set(to, this.descriptions.get(from) ?? null);
      this.descriptions.delete(from);
      this.curriculum = this.curriculum.map((name) => (name === from ? to : name));
    }
    this.withdraw("knowledge_graph");
    return { pipeline: this.pipeline(), bank_references: this.exemplarsOf(concept.name).length };
  }

  addConcept(name: string, domain: string, taggable: boolean) {
    this.requireGraph();
    if (this.concepts.some((concept) => concept.name === name)) throw new Refusal(409, say("concept_exists", { name }));
    if (!this.domains.includes(domain)) throw new Refusal(404, say("unit_missing", { name: domain }));
    this.concepts.push({ name, domain, taggable });
    this.descriptions.set(name, null);
    this.withdraw("knowledge_graph");
    return { pipeline: this.pipeline() };
  }

  deleteConcept(name: string) {
    this.requireGraph();
    const references = this.exemplarsOf(name).length;
    this.concepts = this.concepts.filter((concept) => concept.name !== name);
    this.edges = this.edges.filter((edge) => edge.source !== name && edge.target !== name);
    this.descriptions.delete(name);
    this.curriculum = this.curriculum.filter((candidate) => candidate !== name);
    this.withdraw("knowledge_graph");
    return { pipeline: this.pipeline(), bank_references: references };
  }

  addDomain(name: string) {
    this.requireGraph();
    if (this.domains.includes(name)) throw new Refusal(409, say("unit_exists", { name }));
    this.domains.push(name);
    this.withdraw("knowledge_graph");
    return { pipeline: this.pipeline() };
  }

  renameDomain(name: string, next: string) {
    this.requireGraph();
    this.domains = this.domains.map((domain) => (domain === name ? next : domain));
    for (const concept of this.concepts) if (concept.domain === name) concept.domain = next;
    this.withdraw("knowledge_graph");
    return { pipeline: this.pipeline() };
  }

  deleteDomain(name: string, moveTo: string | null) {
    this.requireGraph();
    this.domains = this.domains.filter((domain) => domain !== name);
    if (moveTo) for (const concept of this.concepts) if (concept.domain === name) concept.domain = moveTo;
    else this.concepts = this.concepts.filter((concept) => concept.domain !== name);
    this.withdraw("knowledge_graph");
    return { pipeline: this.pipeline() };
  }

  reorderDomains(order: string[]) {
    this.requireGraph();
    this.domains = [...order.filter((name) => this.domains.includes(name)), ...this.domains.filter((name) => !order.includes(name))];
    this.withdraw("knowledge_graph");
    return { pipeline: this.pipeline() };
  }

  addEdge(relation: string, source: string, target: string) {
    this.requireGraph();
    const position = RELATIONS.findIndex((candidate) => candidate.key === relation);
    if (position === -1) throw new Refusal(404, say("relation_missing", { name: relation }));
    if (!this.edges.some((edge) => edge.relation === position && edge.source === source && edge.target === target)) {
      this.edges.push({ relation: position, source, target });
    }
    this.withdraw("knowledge_graph");
    return { pipeline: this.pipeline() };
  }

  removeEdge(relation: string, source: string, target: string) {
    this.requireGraph();
    const position = RELATIONS.findIndex((candidate) => candidate.key === relation);
    this.edges = this.edges.filter(
      (edge) => !(edge.relation === position && edge.source === source && edge.target === target),
    );
    this.withdraw("knowledge_graph");
    return { pipeline: this.pipeline() };
  }

  /* THE CURRICULUM --------------------------------------------------------------------- */

  curriculumState(): CurriculumState {
    return { concepts: this.curriculum, updated_at: this.curriculumAt, dropped: [] };
  }

  /** The prerequisite closure of a list, which is what the course's progress is saved as. */
  closure(names: string[]): string[] {
    const known = new Set(names.filter((name) => this.concepts.some((concept) => concept.name === name)));
    let grew = true;
    while (grew) {
      grew = false;
      for (const edge of this.edges) {
        if (edge.relation === 0 && known.has(edge.source) && !known.has(edge.target)) {
          known.add(edge.target);
          grew = true;
        }
      }
    }
    return this.concepts.map((concept) => concept.name).filter((name) => known.has(name));
  }

  putCurriculum(concepts: string[], close: boolean): CurriculumState {
    this.curriculum = close ? this.closure(concepts) : concepts;
    this.curriculumAt = stamp();
    return this.curriculumState();
  }

  /* THE PROFILE ------------------------------------------------------------------------ */

  profilePayload(): ProfilePayload {
    const exists = this.stages.exemplars_profile.status !== "missing";
    return {
      exists,
      profile: exists ? this.profile : null,
      path: exists ? `/workspaces/${this.slug}/artifacts/exemplars_profile_autogenerated.json` : null,
      is_autogenerated: exists,
      pending_draft: null,
      difficulty: subject.difficulty,
    };
  }

  saveProfile(profile: ExemplarsProfile): { pipeline: Pipeline } {
    this.profile = profile;
    this.withdraw("exemplars_profile");
    return { pipeline: this.pipeline() };
  }

  /* THE BANK --------------------------------------------------------------------------- */

  itemTypes(): BankListing["item_types"] {
    return Object.entries(this.profile.item_types).map(([key, spec]) => ({
      key,
      label: spec.label ?? key,
      description: spec.description ?? "",
      primary_field: spec.primary_field,
      embed_fields: spec.embed_fields ?? [spec.primary_field],
      fields: Object.keys(spec.fields),
      difficulty_field: subject.difficulty.field in spec.fields ? subject.difficulty.field : null,
      difficulty_levels: subject.difficulty.levels,
      count: this.bank.filter((item) => item.item_type === key).length,
    }));
  }

  bankListing(params: URLSearchParams): BankListing {
    this.requireBank();
    const q = (params.get("q") ?? "").trim().toLowerCase();
    const type = params.get("item_type");
    const source = params.get("source");
    const difficulty = params.get("difficulty");
    const untagged = params.get("untagged") === "true";
    const page = Math.max(1, Number(params.get("page") ?? 1));
    const size = Math.max(1, Number(params.get("page_size") ?? 50));
    const items = this.bank.filter(
      (item) =>
        (!q || JSON.stringify(item).toLowerCase().includes(q)) &&
        (!type || item.item_type === type) &&
        (!source || item.source === source) &&
        (!difficulty || item[subject.difficulty.field] === difficulty) &&
        (!untagged || !(item.concepts ?? []).length),
    );
    const counts = new Map<string, number>();
    for (const item of this.bank) counts.set(item.item_type ?? "", (counts.get(item.item_type ?? "") ?? 0) + 1);
    const tagged = this.bank.filter((item) => (item.concepts ?? []).length > 0).length;
    return {
      items: items.slice((page - 1) * size, page * size),
      total: items.length,
      page,
      page_size: size,
      item_types: this.itemTypes(),
      difficulties: subject.difficulty.levels.map((value) => ({
        value,
        count: this.bank.filter((item) => item[subject.difficulty.field] === value).length,
      })),
      default_type: [...counts.entries()].sort((a, b) => b[1] - a[1])[0]?.[0] ?? Object.keys(this.profile.item_types)[0],
      sources: [...new Set(this.bank.map((item) => item.source).filter((name): name is string => Boolean(name)))],
      totals: { items: this.bank.length, tagged, untagged: this.bank.length - tagged },
      thresholds: { similarity: 0.4, top_k: 10 },
    };
  }

  coverage(): Coverage {
    this.requireBank();
    const counts: Record<string, number> = {};
    for (const concept of this.concepts) if (concept.taggable) counts[concept.name] = this.exemplarsOf(concept.name).length;
    const names = Object.keys(counts);
    return {
      counts,
      covered: names.filter((name) => counts[name] > 0).length,
      total: names.length,
      without_exemplars: names.filter((name) => counts[name] === 0),
    };
  }

  private requireItem(id: string): BankItem {
    this.requireBank();
    const item = this.bank.find((candidate) => candidate.id === id);
    if (!item) throw new Refusal(404, say("item_missing", { name: id }));
    return item;
  }

  patchItem(id: string, fields: Record<string, unknown>): { item: BankItem } {
    const item = this.requireItem(id);
    Object.assign(item, fields);
    this.withdraw("exemplars_bank");
    return { item };
  }

  setConcepts(id: string, concepts: string[], primary: string | null): { item: BankItem } {
    const item = this.requireItem(id);
    item.concepts = concepts;
    item.primary_concept = primary ?? concepts[0] ?? null;
    item._tagging = { candidates: concepts.map((name) => [name, 1]), method: "manual" };
    this.withdraw("exemplars_bank");
    return { item };
  }

  deleteItem(id: string): { pipeline: Pipeline } {
    this.requireItem(id);
    this.bank = this.bank.filter((item) => item.id !== id);
    this.withdraw("exemplars_bank");
    return { pipeline: this.pipeline() };
  }

  /** Tag every item again, as the tagger would: the same concepts, a fresh trace. */
  retag(item: BankItem): void {
    item._tagging = { ...(item._tagging ?? { candidates: [] }), method: "llm", model: "qwen3.8:27b-q8_0", threshold: 0.4 };
  }

  /* THE EXERCISES ---------------------------------------------------------------------- */

  /** One of the sample exercises as a saved row, at a given id. */
  private rowOf(row: (typeof subject.generations)[number], id: string, daysAgo: number): GenerationRow {
    return {
      id,
      created_at: now() - 86_400 * (daysAgo + 1),
      job_id: id.split("-")[1] ?? null,
      item_type: row.item_type,
      concepts: row.concepts,
      targets: row.concepts,
      curriculum: row.curriculum,
      fixed: row.fixed,
      omit: row.omit,
      instructions: row.instructions,
      think: row.think,
      effort: row.think,
      model: row.model,
      author: { id: 1, name: this.options.teacherName(), username: "docente" },
      promoted_item_id: null,
      item: row.item,
      checks: row.checks as GenerationRow["checks"],
    };
  }

  addGeneration(row: GenerationRow): void {
    this.generations.unshift(row);
  }

  generationsListing(params: URLSearchParams): GenerationListing {
    const q = (params.get("q") ?? "").trim().toLowerCase();
    const type = params.get("item_type");
    const concept = params.get("concept");
    const limit = Math.max(1, Number(params.get("limit") ?? 60));
    const offset = Math.max(0, Number(params.get("offset") ?? 0));
    const rows = this.generations.filter(
      (row) =>
        (!q || JSON.stringify(row.item).toLowerCase().includes(q)) &&
        (!type || row.item_type === type) &&
        (!concept || row.concepts.includes(concept)),
    );
    return { generations: rows.slice(offset, offset + limit), total: rows.length, limit, offset };
  }

  generationDetail(id: string): GenerationDetail {
    const row = this.generations.find((candidate) => candidate.id === id);
    if (!row) throw new Refusal(404, say("exercise_missing"));
    return {
      generation: {
        ...row,
        thinking: null,
        retried: 0,
        format: 1,
        provenance: {
          resolved: { targets: row.concepts, curriculum: row.curriculum, model: row.model, effort: row.think },
          inputs: { knowledge_graph: this.stages.knowledge_graph.hash, exemplars_profile: this.stages.exemplars_profile.hash, exemplars_bank: this.stages.exemplars_bank.hash },
          settings: { prompt_language: "es" },
          system_version: "1.171.0",
          prompt: null,
        },
      },
    };
  }

  deleteGeneration(id: string): { deleted: string } {
    if (!this.generations.some((row) => row.id === id)) throw new Refusal(404, say("exercise_missing"));
    this.generations = this.generations.filter((row) => row.id !== id);
    return { deleted: id };
  }

  /* THE JOBS --------------------------------------------------------------------------- */

  jobDict(job: Job): Job {
    return {
      ...job,
      elapsed_ms: job.started_at ? Math.round(((job.finished_at ?? now()) - job.started_at) * 1000) : null,
    };
  }

  /** The route's gates: what `POST /api/jobs` refuses before queueing (`pipeline/gates`). */
  private gate(kind: JobKind, params: Record<string, unknown>): void {
    const live = this.live();
    if (kind === "generate" && live.some((job) => job.kind === "generate")) {
      throw new Refusal(409, say("generation_busy"), "generation_busy");
    }
    const artifact = JOB_ARTIFACT[kind] ?? (BANK_CHAIN.includes(kind) ? "exemplars_bank" : null);
    if (artifact && live.some((job) => job.kind === "transcribe" && job.params.slot === RAW_SOURCE[artifact])) {
      throw new Refusal(409, say("slot_transcribing"));
    }
    if (kind === "transcribe" && live.some((job) => job.kind === "transcribe" && job.params.slot === params.slot)) {
      throw new Refusal(409, say("slot_already_reading"));
    }
    if (kind === "review_taggability") {
      const blocked = this.stageState("exemplars_bank").blocked_reason;
      if (blocked) throw new Refusal(409, blocked);
    }
    if (artifact && this.building(artifact)) throw new Refusal(409, say("stage_already_building"));
  }

  /** Queue one job: `job.queued` goes out at once, and it starts a moment later. */
  submit(kind: JobKind, params: Record<string, unknown> = {}): Job {
    this.gate(kind, params);
    const job: Job = {
      id: hex(12),
      kind,
      workspace: this.slug,
      user_id: 1,
      user_name: "docente",
      params,
      status: "queued",
      created_at: now(),
      started_at: null,
      finished_at: null,
      error: null,
      error_code: null,
      result: null,
      label: JOB_LABEL[kind] ?? kind,
      artifact: JOB_ARTIFACT[kind] ?? null,
      elapsed_ms: null,
      queue_position: this.live().length + 1,
      backends: ["local"],
    };
    this.jobs.push(job);
    this.emit(job, "job.queued", { job: this.jobDict(job) });
    this.schedule(120, () => this.start(job));
    return this.jobDict(job);
  }

  private start(job: Job): void {
    if (job.status !== "queued") return;
    const ahead = this.jobs.some((other) => other !== job && other.status === "running");
    if (ahead) {
      this.schedule(80, () => this.start(job));
      return;
    }
    job.status = "running";
    job.started_at = now();
    job.queue_position = 0;
    this.emit(job, "job.started", { job: this.jobDict(job) });
    simulate(this, job);
  }

  /** Close a job as the runner does: the next link queued first, then the announcement. */
  finish(job: Job, result: Record<string, unknown> | null, next?: { kind: JobKind; params?: Record<string, unknown> }): void {
    if (job.status !== "running") return;
    job.status = "succeeded";
    job.finished_at = now();
    job.result = result;
    if (next) this.submit(next.kind, next.params ?? {});
    this.emit(job, "job.finished", { job: this.jobDict(job) });
  }

  fail(job: Job, error: string, code: string | null = null): void {
    if (job.status !== "running") return;
    job.status = "failed";
    job.finished_at = now();
    job.error = error;
    job.error_code = code;
    this.emit(job, "job.failed", { job: this.jobDict(job) });
  }

  cancel(id: string): { cancelled: boolean } {
    const job = this.jobs.find((candidate) => candidate.id === id);
    if (!job) throw new Refusal(404, say("job_missing"));
    if (job.status === "queued") {
      job.status = "cancelled";
      job.finished_at = now();
      this.emit(job, "job.cancelled", { job: this.jobDict(job) });
      return { cancelled: true };
    }
    if (job.status !== "running") return { cancelled: false };
    this.emit(job, "job.cancelling");
    this.schedule(200, () => {
      if (job.status !== "running") return;
      job.status = "cancelled";
      job.finished_at = now();
      this.emit(job, "job.cancelled", { job: this.jobDict(job) });
    });
    return { cancelled: true };
  }

  jobsCurrent() {
    const running = this.jobs.find((job) => job.status === "running") ?? null;
    return {
      job: running ? this.jobDict(running) : null,
      queued: this.jobs.filter((job) => job.status === "queued").map((job) => this.jobDict(job)),
      engine_busy: running !== null,
      engine_busy_elsewhere: false,
      last_seq: this.seq,
    };
  }

  jobOf(id: string): Job {
    const job = this.jobs.find((candidate) => candidate.id === id);
    if (!job) throw new Refusal(404, say("job_missing"));
    return this.jobDict(job);
  }
}

export function createWorld(options: WorldOptions): World {
  return new World(options);
}

export { subject as SUBJECT };
