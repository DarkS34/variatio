import type { BankItem, BuildPhase, FewShotExemplar, GenerationRow, Job, RawKind } from "@/lib/types";

import steps from "./data/steps.json";
import { PLANS, SUBJECT, say, type World } from "./world";

/**
 * THE DEMO'S JOBS: what each kind does to the world, and the events it says while doing it.
 *
 * Each script says what the real handler says (`server/pipeline/jobs.py`, the builders'
 * `BUILD_PHASES`, the generator's `progress.step`s) in the same order and with the same
 * payloads, only faster: a build takes seconds, not minutes. The screens read nothing
 * else, so what they draw — the segmented bar, the steps, the live feed of tagged items,
 * the streamed answer, the cards — is what they draw of a real run.
 */

/** A step's label as the library writes it (English, `progress.step`): data, like the plans. */
function step(id: keyof typeof steps, name = ""): string {
  return steps[id].replace("{name}", name);
}

/**
 * How long each piece of simulated work takes, in milliseconds: the one table of the demo's
 * pace. A visitor should wait seconds, not minutes (the user's request, 2026-10-12: «es una
 * demo»), so a whole build is a budget of about one or two seconds spread over its ticks;
 * `pace.test.ts` pins the totals.
 */
const PACE = {
  /** A slot's reading, every page of it. */
  transcribe: 1100,
  /** A build of the syllabus, every phase of its plan. */
  graph: 1600,
  /** The descriptions written after it, every concept. */
  describe: 450,
  /** A build of the types of exercise. */
  profile: 900,
  /** The bank's collection: the review, the reading, the extraction, the index. */
  review: 300,
  convert: 250,
  extract: 800,
  indexConcepts: 280,
  indexItems: 220,
  /** A retag of the whole bank. */
  tag: 700,
  /** A commission: the context, the screening, and per item the stream and the checks. */
  context: 120,
  guardrail: 180,
  admissibility: 140,
  token: 18,
  check: 150,
} as const;

/** How long each of `total` ticks lasts to fill `budget`: never slower than 60 ms, never under 10. */
function every(total: number, budget: number): number {
  return Math.max(10, Math.min(60, Math.round(budget / Math.max(1, total))));
}

const LOREM = SUBJECT.lorem;

function word(): string {
  return LOREM[Math.floor(Math.random() * LOREM.length)];
}

function sentence(length = 10 + Math.floor(Math.random() * 7)): string {
  const words = Array.from({ length }, word);
  return `${words[0][0].toUpperCase()}${words[0].slice(1)} ${words.slice(1).join(" ")}.`;
}

function paragraph(sentences = 2): string {
  return Array.from({ length: sentences }, () => sentence()).join(" ");
}

export function simulate(world: World, job: Job): void {
  switch (job.kind) {
    case "transcribe":
      return transcribe(world, job);
    case "build_kg":
      return build(world, job, "knowledge_graph", PLANS.artifacts.knowledge_graph, PACE.graph, () => {
        world.forgetDescriptions();
        world.built("knowledge_graph");
        world.finish(job, { artifact: "knowledge_graph" }, { kind: "describe_concepts" });
      });
    case "describe_concepts":
      return describe(world, job);
    case "build_profile":
      return build(world, job, "exemplars_profile", PLANS.artifacts.exemplars_profile, PACE.profile, () => {
        world.built("exemplars_profile");
        world.finish(job, { artifact: "exemplars_profile" });
      });
    case "review_taggability":
      return review(world, job);
    case "build_bank":
      return collect(world, job);
    case "index":
      return index(world, job);
    case "tag":
      return tag(world, job);
    case "generate":
      return generate(world, job);
    default:
      world.fail(job, say("unknown_job", { name: job.kind }));
  }
}

/* THE STEPS A SCRIPT IS MADE OF ----------------------------------------------------------- */

/** Walk a list of steps, each a function that calls `done` when it ends; stop on a job that stopped. */
function sequence(job: Job, steps: ((done: () => void) => void)[], after: () => void): void {
  const run = (index: number) => {
    if (job.status !== "running") return;
    if (index >= steps.length) {
      after();
      return;
    }
    steps[index](() => run(index + 1));
  };
  run(0);
}

/** `total` ticks of one step, `ms` apart, each reported with its `detail`. */
function ticking(
  world: World,
  job: Job,
  id: string,
  label: string,
  total: number,
  ms: number,
  detail: (index: number) => string | null,
  onTick?: (index: number) => void,
): (done: () => void) => void {
  return (done) => {
    world.emit(job, "step.started", { id, label, total });
    const tick = (index: number) => {
      if (index > total) {
        world.emit(job, "step.finished", { id, status: "ok", ms: total * ms });
        done();
        return;
      }
      onTick?.(index);
      world.emit(job, "step.progress", { id, current: index, total, detail: detail(index) });
      world.later(job, ms, () => tick(index + 1));
    };
    tick(1);
  };
}

/* THE SCRIPTS ----------------------------------------------------------------------------- */

/** Read a slot page by page: the documents turn «leído» one by one as their pages pass. */
function transcribe(world: World, job: Job): void {
  const kind = job.params.slot as RawKind;
  const documents = world.pagesOf(kind);
  const total = documents.reduce((sum, document) => sum + document.pages, 0);
  let cursor = 0;
  const pageOf = (index: number) => {
    let seen = 0;
    for (const document of documents) {
      if (index <= seen + document.pages) return { document, page: index - seen };
      seen += document.pages;
    }
    return { document: documents.at(-1)!, page: 1 };
  };
  sequence(
    job,
    [
      ticking(world, job, "transcribe", step("transcribe"), total, every(total, PACE.transcribe), (index) => {
        const { document, page } = pageOf(index);
        return `${document.name} · ${page}/${document.pages}`;
      }, (index) => {
        const { document, page } = pageOf(index);
        cursor = index;
        world.emit(job, "build.progress", {
          percent: Math.round((index / total) * 100),
          key: "transcribe",
          label: step("transcribe"),
          detail: document.name,
        });
        if (page === document.pages) world.markRead(kind, document.name);
      }),
    ],
    () => {
      world.emit(job, "build.progress", { percent: 100, key: null, label: null, detail: null });
      world.finish(job, { slot: kind, pages: cursor });
    },
  );
}

/** A build out of process: its phases in order, the overall bar moving by their weights. */
function build(
  world: World,
  job: Job,
  artifact: "knowledge_graph" | "exemplars_profile",
  plan: BuildPhase[],
  budget: number,
  after: () => void,
): void {
  world.emit(job, "step.started", { id: `build_${artifact}`, label: step("build", artifact) });
  // Thirty ticks across the plan, shared by weight, so the segmented bar moves phase by phase.
  const ticksOf = (phase: BuildPhase) => Math.max(2, Math.round((phase.weight / 100) * 30));
  const pace = every(plan.reduce((sum, phase) => sum + ticksOf(phase), 0), budget);
  let done = 0;
  const steps = plan.map((phase) => (next: () => void) => {
    world.emit(job, "build.progress", { percent: done, key: phase.key, label: phase.label, detail: null });
    const ticks = ticksOf(phase);
    ticking(world, job, phase.key, phase.label, ticks, pace, () => null, (index) => {
      world.emit(job, "build.progress", {
        percent: Math.min(99, Math.round(done + (phase.weight * index) / ticks)),
        key: phase.key,
        label: phase.label,
        detail: phase.key === "extract" ? `${word()} ${word()}` : null,
      });
    })(() => {
      done += phase.weight;
      next();
    });
  });
  sequence(job, steps, () => {
    world.emit(job, "build.progress", { percent: 100, key: null, label: null, detail: null });
    world.emit(job, "step.finished", { id: `build_${artifact}`, status: "ok" });
    after();
  });
}

/** Write every concept's description, one call per concept. */
function describe(world: World, job: Job): void {
  const names = world.conceptNames();
  sequence(
    job,
    [
      ticking(world, job, "describe", step("describe"), names.length, every(names.length, PACE.describe), (index) => names[index - 1] ?? null, (index) => {
        const name = names[index - 1];
        if (name) world.describe(name);
      }),
    ],
    () => world.finish(job, { described: names.length }),
  );
}

/** The head of the bank's collection: which concepts work as labels, unit by unit. */
function review(world: World, job: Job): void {
  const units = world.kg().domains.map((domain) => domain.name);
  sequence(
    job,
    [ticking(world, job, "taggable", step("taggable"), units.length, every(units.length, PACE.review), (index) => units[index - 1] ?? null)],
    () => world.finish(job, { skipped: false, non_taggable: SUBJECT.nonTaggable }, { kind: "build_bank", params: { head: job.id } }),
  );
}

/** Collect the bank: read the documents, then extract and tag the items, each one announced. */
function collect(world: World, job: Job): void {
  const documents = world.pagesOf("exemplars");
  const items = world.bank;
  const perDocument = Math.ceil(items.length / Math.max(1, documents.length));
  world.emit(job, "step.started", { id: "build_exemplars_bank", label: step("build", "exemplars_bank") });
  sequence(
    job,
    [
      (next) => {
        world.emit(job, "build.progress", { percent: 0, key: "convert", label: step("convert"), detail: null });
        ticking(world, job, "convert", step("convert"), documents.length, every(documents.length, PACE.convert), (index) => documents[index - 1]?.name ?? null, (index) => {
          world.emit(job, "build.progress", { percent: Math.round((30 * index) / documents.length), key: "convert", label: step("convert"), detail: documents[index - 1]?.name ?? null });
        })(next);
      },
      (next) => {
        ticking(world, job, "extract", step("extract"), items.length, every(items.length, PACE.extract), (index) => items[index - 1]?.id ?? null, (index) => {
          const item = items[index - 1];
          if (!item) return;
          announceTag(world, job, item);
          world.emit(job, "build.progress", {
            percent: 30 + Math.round((69 * index) / items.length),
            key: "extract",
            label: step("extract"),
            detail: documents[Math.min(documents.length - 1, Math.floor((index - 1) / perDocument))]?.name ?? null,
          });
        })(next);
      },
    ],
    () => {
      world.emit(job, "build.progress", { percent: 100, key: null, label: null, detail: null });
      world.emit(job, "step.finished", { id: "build_exemplars_bank", status: "ok" });
      world.built("exemplars_bank");
      world.finish(job, { items: items.length }, { kind: "index", params: { head: job.params.head } });
    },
  );
}

function announceTag(world: World, job: Job, item: BankItem): void {
  world.retag(item);
  world.emit(job, "item.tagged", {
    id: item.id,
    text: String(item.enunciado ?? ""),
    concepts: item.concepts ?? [],
    primary_concept: item.primary_concept ?? null,
    method: item._tagging?.method ?? "llm",
  });
}

/** Index the bank's items and the concepts' descriptions; the last link closes the bank. */
function index(world: World, job: Job): void {
  const items = world.bank.length;
  const concepts = world.conceptNames().length;
  sequence(
    job,
    [
      ticking(world, job, "index_concepts", step("index_concepts"), concepts, every(concepts, PACE.indexConcepts), () => null),
      ticking(world, job, "index_items", step("index_items"), items, every(items, PACE.indexItems), () => null),
    ],
    () => {
      // The collection closes the bank (`chain.CLOSES`) and, with it, the types it ran with.
      world.built("exemplars_bank", true);
      world.approve("exemplars_profile");
      world.finish(job, { indexed: items + concepts });
    },
  );
}

/** Tag the bank again, item by item, the way the bank's own «Re-etiquetar» does. */
function tag(world: World, job: Job): void {
  const items = world.bank;
  sequence(
    job,
    [
      ticking(world, job, "tagging", step("tagging"), items.length, every(items.length, PACE.tag), (index) => items[index - 1]?.id ?? null, (index) => {
        const item = items[index - 1];
        if (item) announceTag(world, job, item);
      }),
    ],
    () => world.finish(job, { tagged: items.length }),
  );
}

/* THE COMMISSION ---------------------------------------------------------------------------- */

/** Write `n` exercises: the screening, the exemplars, then each item streamed, checked and saved. */
function generate(world: World, job: Job): void {
  const params = job.params;
  const n = Math.max(1, Number(params.n ?? 1));
  const typeKey = String(params.item_type ?? Object.keys(world.profile.item_types)[0]);
  const spec = world.profile.item_types[typeKey] ?? Object.values(world.profile.item_types)[0];
  const targets = ((params.concepts as string[] | undefined) ?? []).filter(Boolean);
  const concepts = targets.length ? targets : ["Sit amet"];
  const fixed = (params.fixed as Record<string, unknown> | undefined) ?? {};
  const omit = new Set((params.omit as string[] | undefined) ?? []);
  const instructions = String(params.instructions ?? "").trim();
  const think = params.think ?? true;
  const model = String(params.model ?? "qwen3.8:27b-q8_0");
  const difficulty = SUBJECT.difficulty;

  const exemplars = fewShot(world, typeKey, concepts);
  const produced: Record<string, unknown>[] = [];
  const steps: ((done: () => void) => void)[] = [];

  steps.push((next) => {
    world.emit(job, "step.started", { id: "context", label: step("context") });
    world.later(job, PACE.context, () => {
      world.emit(job, "step.finished", { id: "context", status: "ok", ms: PACE.context });
      next();
    });
  });

  if (instructions) {
    steps.push((next) => {
      world.emit(job, "step.started", { id: "guardrail", label: step("guardrail") });
      world.later(job, PACE.guardrail, () => {
        // The one word the demo's guardrail refuses: it shows the refusal the real one makes.
        if (/\b(ignora|ignore)\b/i.test(instructions)) {
          world.emit(job, "guardrail", { ok: false, criteria: "prompt_injection", checked: true });
          world.emit(job, "step.finished", { id: "guardrail", status: "failed", ms: PACE.guardrail });
          world.fail(job, say("instructions_blocked"), "instructions_blocked");
          return;
        }
        world.emit(job, "guardrail", { ok: true, criteria: null, checked: true });
        world.emit(job, "step.finished", { id: "guardrail", status: "ok", ms: PACE.guardrail });
        world.emit(job, "step.started", { id: "admissibility", label: step("admissibility") });
        world.later(job, PACE.admissibility, () => {
          world.emit(job, "admissibility", { ok: true, checked: true, slots: ["ambito"], owner: null, term: null });
          world.emit(job, "step.finished", { id: "admissibility", status: "ok", ms: PACE.admissibility });
          next();
        });
      });
    });
  }

  steps.push((next) => {
    world.emit(job, "few_shot", {
      ids: exemplars.map((exemplar) => exemplar.id),
      items: exemplars,
      concepts,
      item_type: typeKey,
    });
    world.emit(job, "step.started", { id: "generate", label: step("generate"), total: n });
    next();
  });

  for (let index = 1; index <= n; index += 1) {
    steps.push((next) => {
      world.emit(job, "step.progress", { id: "generate", current: index - 1, total: n, detail: null });
      const item = writeItem(spec, concepts, fixed, omit, difficulty, index);
      world.emit(job, "prompt", { index, text: promptOf(spec.label ?? typeKey, concepts, instructions, exemplars) });
      const answer = JSON.stringify(item, null, 2);
      const thinking = think ? Array.from({ length: 6 }, () => `${sentence(8)} `) : [];
      stream(world, job, thinking, "thinking", () =>
        stream(world, job, chunks(answer, 36), "answer", () => {
          world.emit(job, "step.started", { id: "check", label: step("check") });
          world.later(job, PACE.check, () => {
            world.emit(job, "step.finished", { id: "check", status: "ok", ms: PACE.check });
            const checks = checksOf(concepts, exemplars);
            produced.push({ item, item_type: typeKey, thinking: think ? thinking.join("") : null, checks, retried: 0 });
            world.emit(job, "item.produced", { index, item, item_type: typeKey, thinking: think ? thinking.join("") : null, checks, retried: 0 });
            const id = `${new Date().toISOString().replace(/[-:]/g, "").slice(0, 15)}-${job.id}-${index}`;
            world.addGeneration(rowOf(world, job, id, typeKey, concepts, params, item, checks, model));
            produced[produced.length - 1].saved_id = id;
            world.emit(job, "item.saved", { index, id });
            world.emit(job, "step.progress", { id: "generate", current: index, total: n, detail: null });
            next();
          });
        }),
      );
    });
  }

  sequence(job, steps, () => {
    world.emit(job, "step.finished", { id: "generate", status: "ok" });
    world.finish(job, { items: produced, requested: n });
  });
}

/** Stream `pieces` as tokens on one channel, `PACE.token` apart. */
function stream(world: World, job: Job, pieces: string[], channel: "thinking" | "answer", done: () => void): void {
  const send = (index: number) => {
    if (index >= pieces.length) {
      done();
      return;
    }
    world.emit(job, "token", { channel, text: pieces[index] });
    world.later(job, PACE.token, () => send(index + 1));
  };
  send(0);
}

function chunks(text: string, size: number): string[] {
  const out: string[] = [];
  for (let at = 0; at < text.length; at += size) out.push(text.slice(at, at + size));
  return out;
}

/** The exemplars the generator would pick: of the type asked, on the concepts asked, three at most. */
function fewShot(world: World, typeKey: string, concepts: string[]): FewShotExemplar[] {
  if (world.stages.exemplars_bank.status === "missing") return [];
  const ofType = world.bank.filter((item) => item.item_type === typeKey);
  const primary = ofType.filter((item) => concepts.includes(item.primary_concept ?? ""));
  const secondary = ofType.filter((item) => !primary.includes(item) && (item.concepts ?? []).some((name) => concepts.includes(name)));
  const neighbour = ofType.filter((item) => !primary.includes(item) && !secondary.includes(item));
  const strip = (item: BankItem): Record<string, unknown> => {
    const { id: _id, _tagging, concepts: _concepts, primary_concept: _primary, source: _source, item_type: _type, ...fields } = item;
    return fields;
  };
  return [
    ...primary.map((item) => ({ id: item.id, item: strip(item), origin: "primary" as const })),
    ...secondary.map((item) => ({ id: item.id, item: strip(item), origin: "secondary" as const })),
    ...neighbour.map((item) => ({ id: item.id, item: strip(item), origin: "neighbour" as const })),
  ].slice(0, 3);
}

/** One exercise of the type asked: every field it declares, the pinned values kept, the omitted ones left out. */
function writeItem(
  spec: { fields: Record<string, { schema: Record<string, unknown> }> },
  concepts: string[],
  fixed: Record<string, unknown>,
  omit: Set<string>,
  difficulty: { field: string; levels: string[] },
  index: number,
): Record<string, unknown> {
  const item: Record<string, unknown> = {};
  for (const [name, field] of Object.entries(spec.fields)) {
    if (omit.has(name)) continue;
    if (fixed[name] !== undefined && fixed[name] !== null && fixed[name] !== "") {
      item[name] = fixed[name];
      continue;
    }
    const schema = field.schema;
    const kind = Array.isArray(schema.type) ? schema.type[0] : schema.type;
    if (name === difficulty.field) item[name] = difficulty.levels[(index + concepts.length) % difficulty.levels.length];
    else if (Array.isArray(schema.enum)) item[name] = schema.enum[index % schema.enum.length];
    else if (kind === "array") item[name] = Array.from({ length: 4 }, () => sentence(5));
    else if (name === "enunciado") item[name] = `${sentence(12)} ${concepts[0]} ${sentence(9)}`;
    else if (name === "solucion") item[name] = paragraph(3);
    else item[name] = sentence(8);
  }
  return item;
}

function promptOf(typeLabel: string, concepts: string[], instructions: string, exemplars: FewShotExemplar[]): string {
  return [
    `# ${typeLabel}`,
    "",
    `Conceptos objetivo: ${concepts.join(", ")}.`,
    instructions ? `Instrucciones adicionales: ${instructions}` : null,
    "",
    `Ejemplos (${exemplars.length}):`,
    ...exemplars.map((exemplar) => `- ${exemplar.id}: ${String(exemplar.item.enunciado ?? "").slice(0, 80)}…`),
    "",
    paragraph(3),
  ]
    .filter((line) => line !== null)
    .join("\n");
}

function checksOf(concepts: string[], exemplars: FewShotExemplar[]): GenerationRow["checks"] {
  return {
    forbidden: [],
    similarity: exemplars.length ? { to: exemplars[0].id, score: 0.27 + Math.random() * 0.1, high: false } : null,
    tagger: { primary: concepts[0], concepts: [...concepts], method: "llm", on_target: true, targets_found: [concepts[0]] },
    flags: [],
    verdict: "accept",
    reasons: [],
  };
}

function rowOf(
  world: World,
  job: Job,
  id: string,
  typeKey: string,
  concepts: string[],
  params: Record<string, unknown>,
  item: Record<string, unknown>,
  checks: GenerationRow["checks"],
  model: string,
): GenerationRow {
  return {
    id,
    created_at: Date.now() / 1000,
    job_id: job.id,
    item_type: typeKey,
    concepts,
    targets: concepts,
    curriculum: (params.curriculum as string[] | undefined) ?? [],
    fixed: (params.fixed as Record<string, unknown> | undefined) ?? {},
    omit: (params.omit as string[] | undefined) ?? [],
    instructions: String(params.instructions ?? ""),
    think: (params.think as boolean | string | undefined) ?? true,
    effort: (params.think as boolean | string | undefined) ?? true,
    model,
    author: { id: 1, name: world.options.teacherName(), username: "docente" },
    promoted_item_id: null,
    item,
    checks,
  };
}
