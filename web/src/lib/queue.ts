import type { Job, JobStatus, LaneName, LaneState, Lanes, Pipeline } from "./types";
import type { Key, Translate } from "@/lib/i18n";

/**
 * Who is waiting for what, derived once from the payload and nowhere else.
 *
 * With one lane per inference backend, "something is running" and "yours will wait" are
 * different sentences: the GPU being busy says nothing about a job that only calls the
 * hosted API. A button that announces a wait which will not happen is what this answers.
 *
 * A lane has ROOM — local is one because the GPU is one, remote is
 * `CEREBRAS_MAX_CONCURRENT_JOBS` — so `busy` means FULL and the arithmetic is "those
 * holding a slot, plus those in front, less the room". At capacity 1 that reduces to the
 * old single-slot rule, which is what lets an older API degrade into it.
 *
 * Everything is a function of the payload, so the launch notice and the state the button
 * holds afterwards are two views of one truth. Nothing here estimates time.
 */

const LANE_ORDER: LaneName[] = ["local", "remote"];

const LANE_KEYS: Record<LaneName, Key> = {
  local: "lane.local",
  remote: "lane.remote",
};

/**
 * Does this installation have two halves to tell apart?
 *
 * Read off the engine's own name, as the "Motor" tab reads it: "el motor local" beside no
 * remote one divides nothing.
 */
export function isSplitEngine(engine: string | null | undefined): boolean {
  return typeof engine === "string" && engine.includes("+");
}

function laneName(lane: LaneName | null, split: boolean, tr: Translate): string {
  return tr.t(lane && split ? LANE_KEYS[lane] : "lane.any");
}

function readLane(value: unknown): LaneState | null {
  if (!value || typeof value !== "object") return null;
  const raw = value as Record<string, unknown>;
  const busy = raw.busy === true;
  return {
    busy,
    // An API older than this bundle sends neither, and this degrades to the shape it had:
    // one slot, held or free.
    running: typeof raw.running === "number" ? raw.running : busy ? 1 : 0,
    capacity: typeof raw.capacity === "number" && raw.capacity > 0 ? raw.capacity : 1,
    mine: raw.mine === true,
    label: typeof raw.label === "string" && raw.label ? raw.label : null,
    queued: typeof raw.queued === "number" ? raw.queued : 0,
    ahead: typeof raw.ahead === "number" ? raw.ahead : null,
  };
}

/**
 * The lanes as the pipeline reports them, or `null` when it does not report them.
 *
 * Read defensively: an API older than this bundle sends no `lanes`, and a bare
 * `data.lanes.local.busy` blanks the whole tab. `null` is "this server does not split the
 * queue" and never an error, and every caller has a flat fallback.
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
  // How many have to finish before mine starts: everything holding a slot, plus everything
  // in front of it, less the room the lane has. The same arithmetic the server does, and at
  // capacity 1 the same "one if the lane is held, plus those in front" it always did.
  return Math.max(0, lane.running + place - lane.capacity);
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
 * hears every colleague's jobs — and a screen that adopts "the most recent run of my
 * kind" adopts theirs. This is the one criterion for telling them apart, and it fails
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
 * Is this job still going?
 *
 * Waiting counts, for the same reason every screen here reads `isQueued` rather than the
 * status alone: a queued commission is a made commission. Structural in its argument so
 * that `pickActiveRun`, which only ever sees a status, and a screen holding a whole `Job`
 * ask the one question of the one function.
 */
export function isLive(job: { status: JobStatus } | null | undefined): boolean {
  return job?.status === "running" || job?.status === "queued";
}

/**
 * What a job that has already been submitted is waiting behind, or null when nothing is
 * in front of it — which includes the ordinary case of a job that started at once.
 *
 * The flat fallback matters: with no `lanes` the position alone still says how many are
 * ahead, and "en cola" is true whether or not the server can name the lane.
 */
export function waitOf(job: Job | null | undefined, lanes: Lanes | null): Wait | null {
  if (!isQueued(job)) return null;
  const position = typeof job!.queue_position === "number" ? job!.queue_position : null;
  const wait = waitFor(lanes, backendsOf(job), position);
  if (wait) return wait;
  const ahead = position !== null ? Math.max(0, position - 1) : 0;
  return ahead > 0 ? { lane: null, ahead, label: null } : null;
}

export function aheadLabel(ahead: number, tr: Translate): string {
  return tr.plural("queue.ahead", ahead);
}

/** What the button says about itself while it waits. */
export function queuedLabel(wait: Wait | null, tr: Translate): string {
  return wait && wait.ahead > 0
    ? tr.t("queue.queuedAhead", { n: wait.ahead })
    : tr.t("queue.queued");
}

/** Why it is waiting: which half of the engine, holding what, with how many in front. */
export function waitReason(wait: Wait, split: boolean, tr: Translate): string {
  const holder = wait.label ? tr.t("queue.withHolder", { label: wait.label }) : "";
  return tr.t("queue.busyReason", {
    where: laneName(wait.lane, split, tr),
    holder,
    ahead: aheadLabel(wait.ahead, tr),
  });
}

/** The ephemeral notice, and only when there really is a wait — it is about the WAIT and
 *  not about the launch, so a job that starts at once announces nothing. */
export function queuedNotice(
  job: Job | null | undefined,
  lanes: Lanes | null,
  split: boolean,
  tr: Translate,
): { title: string; description: string } | null {
  const wait = waitOf(job, lanes);
  if (!wait) return null;
  return {
    title: tr.t("queue.noticeTitle", { label: job!.label }),
    description: waitReason(wait, split, tr),
  };
}

// `queued` is this workspace's own share of the lane, which is why it is said as "tienes".
function busyPhrase(lane: LaneState, name: LaneName, split: boolean, tr: Translate): string {
  const where = laneName(name, split, tr);
  const holder = lane.label ? tr.t("queue.withHolder", { label: lane.label }) : "";
  // Not full is not "free", it is "there is still room": on a remote lane holding two of
  // four, saying it is busy would announce a wait that is not going to happen, and saying
  // nothing is running there would be false. Only the full case names what holds it.
  if (!lane.busy) {
    return lane.running > 0
      ? tr.t("queue.laneRoom", { where, n: lane.running, capacity: lane.capacity })
      : tr.t("queue.laneFree", { where, ahead: aheadLabel(lane.queued, tr) });
  }
  if (lane.queued > 0) {
    return tr.t("queue.laneBusyWithYours", { where, holder, n: lane.queued });
  }
  return tr.t("queue.laneBusy", { where, holder });
}

/**
 * What to add to the tooltip of a button whose job does not exist yet.
 *
 * With a single engine everything competes for the same thing, so the flat count IS what a
 * new job goes behind and the note can predict — which is what the button always did, and
 * on that installation it was never wrong. With two lanes it reports what the machine is
 * doing and states the condition out loud instead: which half a build needs is the
 * server's to decide when the job is accepted, and announcing a wait that then does not
 * happen is the whole defect this replaces. `null` means "nothing to add".
 */
export function prospectNote(
  lanes: Lanes | null,
  split: boolean,
  queueLength: number,
  tr: Translate,
): string | null {
  if (!lanes || !split) {
    return queueLength > 0
      ? tr.t("queue.willQueue", { ahead: aheadLabel(queueLength, tr) })
      : null;
  }
  const busy = LANE_ORDER.filter((name) => lanes[name].busy || lanes[name].queued > 0);
  if (busy.length === 0) return null;
  const phrases = busy.map((name) => busyPhrase(lanes[name], name, split, tr));
  return tr.t("queue.rightNow", { phrases: phrases.join(tr.t("queue.and")) });
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
  const alive = all.filter((run) => isLive(run.job));
  const current = currentJobId ? runs[currentJobId] : undefined;
  if (current && alive.includes(current)) return current;
  return alive.length > 0 ? newest(alive) : newest(all);
}
