import type { Job, JobStatus, LaneName, LaneState, Lanes, Pipeline } from "./types";

/**
 * Who is waiting for what, derived once from the payload and nowhere else.
 *
 * The queue used to be one deep, so «hay algo en marcha» and «lo tuyo va a esperar» were
 * the same sentence and every screen could count `queue_length`. With one lane per
 * inference backend they are different sentences: the GPU being busy says nothing about a
 * job that only calls the hosted API. That is the complaint this module exists to answer —
 * a button that announces a wait which is not going to happen.
 *
 * Everything here is a function of the payload, so the notice that appears on launching and
 * the state the button holds afterwards are two views of one truth rather than two rules
 * that drift. Nothing here estimates time: «2 por delante» is a count of jobs, and what a
 * job costs depends on models this project changes to find out what they do.
 */

const LANE_ORDER: LaneName[] = ["local", "remote"];

const LANE_LABELS: Record<LaneName, string> = {
  local: "el motor local",
  remote: "el motor remoto",
};

/**
 * Does this installation have two halves to tell apart?
 *
 * `cerebras+ollama` is a composite and its name says so, exactly as the «Motor» tab reads
 * it: with a single engine there is nothing to name, and «el motor local» beside no remote
 * one divides nothing.
 */
export function isSplitEngine(engine: string | null | undefined): boolean {
  return typeof engine === "string" && engine.includes("+");
}

function laneName(lane: LaneName | null, split: boolean): string {
  return lane && split ? LANE_LABELS[lane] : "el motor";
}

function readLane(value: unknown): LaneState | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  return {
    busy: raw.busy === true,
    mine: raw.mine === true,
    label: typeof raw.label === "string" && raw.label ? raw.label : null,
    queued: typeof raw.queued === "number" ? raw.queued : 0,
    ahead: typeof raw.ahead === "number" ? raw.ahead : null,
  };
}

/**
 * The lanes as the pipeline reports them, or `null` when it does not report them.
 *
 * Read defensively on purpose: an API older than this bundle sends no `lanes`, and a bare
 * `data.lanes.local.busy` is what blanked a whole tab once already. `null` is not an error
 * — it is «this server does not split the queue», and every caller has a flat fallback.
 */
export function readLanes(pipeline: Pipeline | null | undefined): Lanes | null {
  const value = pipeline?.lanes as unknown;
  if (!value || typeof value !== "object") return null;
  const local = readLane((value as Record<string, unknown>).local);
  const remote = readLane((value as Record<string, unknown>).remote);
  return local && remote ? { local, remote } : null;
}

/** The lanes a job reserves, or `null` when the API did not say. `[]` is an answer. */
export function backendsOf(job: Job | null | undefined): LaneName[] | null {
  const value = job?.backends;
  if (!Array.isArray(value)) return null;
  return value.filter((name): name is LaneName => name === "local" || name === "remote");
}

/** A wait is only ever built with `ahead > 0`: nothing in front is not a wait. */
export interface Wait {
  /** The lane that decides when it starts; null when the server did not name one. */
  lane: LaneName | null;
  /** Jobs it goes behind, the one already running included. */
  ahead: number;
  /** What holds that lane right now, whoever launched it. */
  label: string | null;
}

/**
 * How many jobs a queued job in this lane goes behind.
 *
 * `lane.ahead` is the server's own count and is preferred whenever it exists: it is
 * recomputed on every poll, while a `queue_position` travels once with the job and goes
 * stale as the queue drains under it. It is null only when this workspace has nothing
 * waiting in that lane — which is exactly the instant a job has just been submitted and
 * the position is the fresher of the two.
 */
function aheadIn(lane: LaneState, position: number | null): number {
  if (lane.ahead !== null) return lane.ahead;
  const place = position ?? lane.queued + 1;
  return (lane.busy ? 1 : 0) + Math.max(0, place - 1);
}

/**
 * What holds up a job on these lanes, or null when nothing does.
 *
 * A job on two lanes starts when the slower of the two frees up, so the lane reported is
 * the one with most work in front: that is the one somebody can do something about. Note
 * that for a job reserving BOTH lanes, each held by a different job, this is one short of
 * the server's own `queue_ahead` — it counts two holders, this counts the worse lane. It
 * errs downwards on purpose: overstating a wait is the defect this whole module replaces.
 */
export function waitFor(
  lanes: Lanes | null,
  backends: LaneName[] | null,
  position: number | null = null,
): Wait | null {
  if (!lanes || !backends) return null;
  let worst: Wait | null = null;
  for (const name of backends) {
    const lane = lanes[name];
    if (!lane) continue;
    const ahead = aheadIn(lane, position);
    if (ahead > 0 && (worst === null || ahead > worst.ahead)) {
      worst = { lane: name, ahead, label: lane.label };
    }
  }
  return worst;
}

/** Is this job waiting rather than working? `queue_position` is the direct answer; the
 *  status is the fallback for an API that does not send one. */
/**
 * Is this job the given account's own?
 *
 * The stream is filtered by WORKSPACE, never by user, so every browser of an instance
 * hears every colleague's jobs — and a screen that adopts «the most recent run of my
 * kind» adopts theirs. This is the one criterion for telling them apart, and it fails
 * OPEN: with either id unknown (an older API, an account deleted under the job) nobody's
 * run is hidden, because the failure this replaces is the second person's screen being
 * taken over, not a run showing to one person too many.
 */
export function ownedBy(job: Job | null | undefined, userId: number | null | undefined): boolean {
  if (!job) return false;
  if (typeof job.user_id !== "number" || typeof userId !== "number") return true;
  return job.user_id === userId;
}

export function isQueued(job: Job | null | undefined): boolean {
  if (!job) return false;
  if (typeof job.queue_position === "number") return job.queue_position > 0;
  return job.status === "queued";
}

/**
 * What a job that has already been submitted is waiting behind, or null when nothing is
 * in front of it — which includes the ordinary case of a job that started at once.
 *
 * The flat fallback matters: with no `lanes` the position alone still says how many are
 * ahead, and «en cola» is true whether or not the server can name the lane.
 */
export function waitOf(job: Job | null | undefined, lanes: Lanes | null): Wait | null {
  if (!isQueued(job)) return null;
  const position = typeof job!.queue_position === "number" ? job!.queue_position : null;
  const wait = waitFor(lanes, backendsOf(job), position);
  if (wait) return wait;
  const ahead = position !== null ? Math.max(0, position - 1) : 0;
  return ahead > 0 ? { lane: null, ahead, label: null } : null;
}

export function aheadLabel(ahead: number): string {
  return ahead === 1 ? "1 trabajo por delante" : `${ahead} trabajos por delante`;
}

/** What the button says about itself while it waits. */
export function queuedLabel(wait: Wait | null): string {
  return wait && wait.ahead > 0 ? `En cola (${wait.ahead} por delante)` : "En cola";
}

/** Why it is waiting: which half of the engine, holding what, with how many in front. */
export function waitReason(wait: Wait, split: boolean): string {
  const holder = wait.label ? ` con «${wait.label}»` : "";
  return `Está ocupado ${laneName(wait.lane, split)}${holder}: ${aheadLabel(wait.ahead)}.`;
}

/** The ephemeral notice, and only when there really is a wait — it is about the WAIT and
 *  not about the launch, so a job that starts at once announces nothing. */
export function queuedNotice(
  job: Job | null | undefined,
  lanes: Lanes | null,
  split: boolean,
): { title: string; description: string } | null {
  const wait = waitOf(job, lanes);
  if (!wait) return null;
  return {
    title: `En cola: ${job!.label}`,
    description: waitReason(wait, split),
  };
}

// `queued` is this workspace's own share of the lane, which is why it is said as «tienes».
function busyPhrase(lane: LaneState, name: LaneName, split: boolean): string {
  const where = laneName(name, split);
  const holder = lane.label ? ` con «${lane.label}»` : "";
  if (!lane.busy) return `en ${where} tienes ${aheadLabel(lane.queued)}`;
  if (lane.queued > 0) return `${where} está ocupado${holder} y tienes ${lane.queued} en cola`;
  return `${where} está ocupado${holder}`;
}

/**
 * What to add to the tooltip of a button whose job does not exist yet.
 *
 * With a single engine everything competes for the same thing, so the flat count IS what a
 * new job goes behind and the note can predict — which is what the button always did, and
 * on that installation it was never wrong. With two lanes it reports what the machine is
 * doing and states the condition out loud instead: which half a build needs is the
 * server's to decide when the job is accepted, and announcing a wait that then does not
 * happen is the whole defect this replaces. `null` means «nothing to add».
 */
export function prospectNote(
  lanes: Lanes | null,
  split: boolean,
  queueLength: number,
): string | null {
  if (!lanes || !split) {
    return queueLength > 0 ? ` Se pondrá en cola: ${aheadLabel(queueLength)}.` : null;
  }
  const busy = LANE_ORDER.filter((name) => lanes[name].busy || lanes[name].queued > 0);
  if (busy.length === 0) return null;
  const phrases = busy.map((name) => busyPhrase(lanes[name], name, split));
  return ` Ahora mismo ${phrases.join(" y ")}; este trabajo solo espera por el motor que necesite.`;
}

/**
 * Which run a screen without a job of its own should show.
 *
 * `currentJobId` alone stopped being an answer when two lanes made two jobs run at once:
 * it holds whichever of them last emitted an event, so the drawer flickered between them.
 * What the person asked for wins while it is still going; otherwise the newest one that is
 * still alive, and only with nothing alive the most recent finished run — an empty panel
 * would be worse than a record.
 */
export function pickActiveRun<
  T extends { job: { status: JobStatus } | null; startedAt: number | null },
>(runs: Record<string, T>, currentJobId: string | null): T | null {
  const all = Object.values(runs);
  if (all.length === 0) return null;
  const newest = (list: T[]) =>
    list.slice().sort((a, b) => (b.startedAt ?? 0) - (a.startedAt ?? 0))[0];
  const alive = all.filter(
    (run) => run.job?.status === "running" || run.job?.status === "queued",
  );
  const current = currentJobId ? runs[currentJobId] : undefined;
  if (current && alive.includes(current)) return current;
  return alive.length > 0 ? newest(alive) : newest(all);
}
