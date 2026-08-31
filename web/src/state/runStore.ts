import { describeEvent, type ActivityLine } from "@/lib/explain";
import type { FewShotExemplar, ItemChecks, Job, VgEvent } from "@/lib/types";
import { activeWorkspace } from "./workspace";
import type { Translate } from "@/lib/i18n";

/**
 * One live view of what the system is doing, fed by a single WebSocket.
 *
 * Reconnects carry `?since=<lastSeq>` so a reload replays what was missed instead of
 * leaving a hole in the timeline. Everything derived from events lives here; screens
 * subscribe and never touch the socket.
 */

export type StepStatus = "running" | "ok" | "failed" | "cancelled" | "skipped";

export interface StepView {
  key: string;
  id: string;
  label: string;
  status: StepStatus;
  total?: number | null;
  current?: number;
  detail?: string | null;
  ms?: number;
  startedAt: number;
  error?: string | null;
}

export interface ProducedItem {
  index: number;
  item: Record<string, unknown>;
  item_type?: string;
  thinking?: string | null;
  checks?: ItemChecks | null;
  retried?: number;
  /** The `generations` row this item became, once the server says so. */
  saved_id?: number | null;
}

/**
 * One bank item the tagger has just annotated.
 *
 * The count alone answered «cuántos van» and nothing else. Re-tagging is minutes of a
 * screen with nothing on it, and the event already carries what was decided; keeping the
 * last few is what lets the bank draw the same live feed a build draws.
 */
export interface TaggedItem {
  id: string;
  text: string;
  concepts: string[];
  primary_concept: string | null;
  method: string;
}

/** Which side of the stream the model is writing on right now. */
export type StreamPhase = "idle" | "thinking" | "answering";

/**
 * How far the whole build is, not just the running step.
 *
 * Steps nest and each one only knows its own total, so no step can answer "how much is
 * left". The builders declare what each phase costs and the core turns that into one
 * 0-100 number; this is where it lands.
 */
export interface OverallProgress {
  percent: number;
  /** Which phase of the plan is running: what tells the segmented bar where it is. */
  key: string | null;
  label: string | null;
  detail: string | null;
}

export interface RunView {
  jobId: string;
  job: Job | null;
  steps: StepView[];
  overall: OverallProgress | null;
  answer: string;
  thinking: string;
  phase: StreamPhase;
  activity: ActivityLine[];
  items: ProducedItem[];
  repairs: { attempt: number; max_attempts: number; error: string; where: string }[];
  retrieval: { query: string; candidates: [string, number][] } | null;
  guardrail: { ok: boolean; criteria: string | null; checked: boolean } | null;
  /** null until the run says which exemplars it picked; [] means it fell back to zero-shot. */
  fewShot: FewShotExemplar[] | null;
  prompt: string | null;
  taggedCount: number;
  tagged: TaggedItem[];
  startedAt: number | null;
  finishedAt: number | null;
  /**
   * A stop was asked for and the job has not reacted yet.
   *
   * `runner.cancel` publishes `job.cancelling` the moment the request lands, but the job
   * itself only notices at its next `progress.checkpoint()` — between two pages of a
   * transcription that is up to a whole model call away. Without this the screen showed
   * nothing at all in between: same badge, same live bar, and the stop button pressable
   * again, so the only evidence the click had been heard was a line in a log drawer that
   * no longer exists.
   */
  cancelling: boolean;
}

const MAX_TOKENS = 120_000;
// Whether an event deserves a line does not depend on the language, so the reducer asks
// with a translator that answers nothing: what it needs is the null, never the words.
const SILENT: Translate = { t: () => "", plural: () => "" };

const MAX_ACTIVITY = 600;
const MAX_RUNS = 12;
const MAX_TAGGED = 24;

/** The close code `server/routers/ws.py` uses when the handshake carries no session. */
const UNAUTHORISED = 4401;

export interface StreamState {
  connected: boolean;
  /** The server refused the handshake: the cookie is gone, revoked or expired. */
  unauthorised: boolean;
  lastSeq: number;
  currentJobId: string | null;
  runs: Record<string, RunView>;
  gap: boolean;
}

function emptyRun(jobId: string): RunView {
  return {
    jobId,
    job: null,
    steps: [],
    overall: null,
    answer: "",
    thinking: "",
    phase: "idle",
    activity: [],
    items: [],
    repairs: [],
    retrieval: null,
    guardrail: null,
    fewShot: null,
    prompt: null,
    taggedCount: 0,
    tagged: [],
    startedAt: null,
    finishedAt: null,
    cancelling: false,
  };
}

function tail(text: string, limit: number) {
  return text.length > limit ? text.slice(text.length - limit) : text;
}

class RunStore {
  private state: StreamState = {
    connected: false,
    unauthorised: false,
    lastSeq: 0,
    currentJobId: null,
    runs: {},
    gap: false,
  };
  private listeners = new Set<() => void>();
  private socket: WebSocket | null = null;
  private retry = 0;
  private timer: number | null = null;
  private notifyScheduled = false;
  /** Which workspace the open socket is subscribed to, so a switch can be noticed. */
  private subscribedTo: string | null = null;

  subscribe = (listener: () => void) => {
    this.listeners.add(listener);
    return () => {
      this.listeners.delete(listener);
    };
  };

  getSnapshot = () => this.state;

  // A streaming model emits tens of tokens per second. State is updated immediately so
  // no event is lost, but subscribers are woken once per frame: rendering the timeline
  // and the token pane 40 times a second buys nothing the eye can see.
  private commit(next: Partial<StreamState>) {
    this.state = { ...this.state, ...next };
    if (this.notifyScheduled) return;
    this.notifyScheduled = true;
    requestAnimationFrame(() => {
      this.notifyScheduled = false;
      for (const listener of this.listeners) listener();
    });
  }

  /* CONNECTION ------------------------------------------------------------------- */

  connect() {
    const workspace = activeWorkspace();
    if (this.socket && this.socket.readyState <= WebSocket.OPEN) {
      if (this.subscribedTo === workspace) return;
      // The socket is subscribed to the instance we have just left. Everything it would
      // deliver from here on belongs to somebody else's screen.
      this.disconnect();
    }
    if (this.state.unauthorised) this.commit({ unauthorised: false });

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const query = new URLSearchParams({ since: String(this.state.lastSeq) });
    if (workspace) query.set("workspace", workspace);
    const socket = new WebSocket(`${protocol}//${window.location.host}/ws?${query}`);
    this.socket = socket;
    this.subscribedTo = workspace;

    socket.onopen = () => {
      this.retry = 0;
      this.commit({ connected: true });
    };

    socket.onmessage = (message) => {
      const payload = JSON.parse(message.data) as VgEvent & { events?: VgEvent[] };
      if (payload.kind === "stream.ready") {
        this.commit({ gap: Boolean((payload as any).gap) });
        // `apply` advances lastSeq to the last replayed event. The bus's own last_seq can
        // already be ahead of that replay, and adopting it here would make the reducer
        // discard the live events in between — the tokens produced while we connected.
        // One unreadable historical event must not cost the rest of the replay, so each
        // is applied on its own; a live event failing later fails alone anyway.
        for (const event of payload.events ?? []) {
          try {
            this.apply(event);
          } catch {
            /* keep replaying */
          }
        }
        // After the events, because the snapshot is the fresher of the two: the replay is
        // bounded and its `job.queued`/`job.started` may have been evicted from the ring,
        // which used to leave this tab with runs whose `job` was null for ever — no
        // screen could claim them, and the finish never invalidated anything.
        this.adoptJobs((payload as any).jobs ?? []);
        return;
      }
      if (payload.kind === "stream.heartbeat") return;
      this.apply(payload);
    };

    // 4401 is not a network hiccup: reconnecting on a loop would hammer the server with
    // a cookie it has already rejected. Stop, and let the gate re-ask who we are.
    socket.onclose = (event) => {
      if (event.code === UNAUTHORISED) {
        this.socket = null;
        this.subscribedTo = null;
        this.commit({ connected: false, unauthorised: true });
        return;
      }
      this.commit({ connected: false });
      this.scheduleReconnect();
    };

    socket.onerror = () => socket.close();
  }

  private scheduleReconnect() {
    if (this.timer !== null) return;
    const delay = Math.min(1000 * 2 ** this.retry, 10_000);
    this.retry += 1;
    this.timer = window.setTimeout(() => {
      this.timer = null;
      this.connect();
    }, delay);
  }

  /** Drop the socket on the way out, so a logout does not leave it retrying. */
  disconnect() {
    if (this.timer !== null) {
      window.clearTimeout(this.timer);
      this.timer = null;
    }
    const socket = this.socket;
    this.socket = null;
    this.subscribedTo = null;
    socket?.close();
    this.commit({ connected: false });
  }

  /**
   * Forget everything the previous workspace put here and resubscribe.
   *
   * Not a nicety: `runs` and `currentJobId` are both that workspace's, and leaving
   * them on screen after a switch would show one instance's generated statements under
   * another instance's header. `lastSeq` goes back to 0 because the sequence is the bus's
   * and replaying from it would only ask for events this workspace is not entitled to.
   */
  reset() {
    this.forget();
    this.connect();
  }

  /** The same wipe without the resubscription: what a logout wants, since there is no
   *  longer anything this browser is entitled to hear. */
  forget() {
    this.disconnect();
    this.state = {
      connected: false,
      unauthorised: false,
      lastSeq: 0,
      currentJobId: null,
      runs: {},
      gap: false,
    };
    this.commit({});
  }

  /** Seed the store from REST when a job is discovered outside the socket. */
  ingest(events: VgEvent[]) {
    for (const event of events) this.apply(event);
    this.commit({});
  }

  setCurrentJob(jobId: string | null) {
    if (jobId && !this.state.runs[jobId]) {
      this.commit({ runs: { ...this.state.runs, [jobId]: emptyRun(jobId) } });
    }
    if (this.state.currentJobId !== jobId) this.commit({ currentJobId: jobId });
  }

  /**
   * The server's own account of this workspace's jobs, from `stream.ready`.
   *
   * The replay reconstructs runs from whatever events survive the ring buffer, and the
   * `job.queued`/`job.started` that carry the job body are the OLDEST events of a run —
   * the first to be evicted. The snapshot is taken at connect time, so it wins over
   * whatever the replayed events said, and a run always knows its job.
   */
  private adoptJobs(jobs: Job[]) {
    if (!Array.isArray(jobs) || jobs.length === 0) return;
    const runs = { ...this.state.runs };
    let currentJobId = this.state.currentJobId;
    for (const job of jobs) {
      if (!job?.id) continue;
      const run = runs[job.id] ?? emptyRun(job.id);
      runs[job.id] = {
        ...run,
        job,
        startedAt: run.startedAt ?? job.started_at ?? job.created_at,
        finishedAt: run.finishedAt ?? job.finished_at,
      };
      if (job.status === "running" || job.status === "queued") currentJobId = job.id;
    }
    this.commit({ runs: this.prune(runs), currentJobId });
  }

  /* REDUCER ---------------------------------------------------------------------- */

  private apply(event: VgEvent) {
    if (event.seq && event.seq <= this.state.lastSeq) return;

    const runs = { ...this.state.runs };
    let currentJobId = this.state.currentJobId;

    if (event.job_id) {
      const run = runs[event.job_id] ?? emptyRun(event.job_id);
      runs[event.job_id] = this.reduce(run, event);
      if (event.kind === "job.started" || event.kind === "job.queued") currentJobId = event.job_id;
      if (["job.finished", "job.failed", "job.cancelled"].includes(event.kind)) {
        if (currentJobId === event.job_id) currentJobId = null;
      }
    }

    this.commit({
      runs: this.prune(runs),
      currentJobId,
      lastSeq: Math.max(this.state.lastSeq, event.seq ?? 0),
    });
  }

  private prune(runs: Record<string, RunView>) {
    const ids = Object.keys(runs);
    if (ids.length <= MAX_RUNS) return runs;
    const ordered = ids.sort((a, b) => (runs[a].startedAt ?? 0) - (runs[b].startedAt ?? 0));
    const next = { ...runs };
    for (const id of ordered.slice(0, ids.length - MAX_RUNS)) delete next[id];
    return next;
  }

  private reduce(run: RunView, event: VgEvent): RunView {
    return this.withActivity(this.reduceRun(run, event), event);
  }

  // The event stream is written for the code; this is the running commentary a human
  // reads instead. Kept next to the reducer so a new event kind is described once.
  private withActivity(run: RunView, event: VgEvent): RunView {
    // Only whether it is worth a line is decided here; the words are the reader's.
    if (!describeEvent(event, SILENT)) return run;
    const activity = [...run.activity, { seq: event.seq, ts: event.ts, event }];
    return {
      ...run,
      activity: activity.length > MAX_ACTIVITY ? activity.slice(-MAX_ACTIVITY) : activity,
    };
  }

  private reduceRun(run: RunView, event: VgEvent): RunView {
    switch (event.kind) {
      case "job.queued":
      case "job.started":
        return { ...run, job: event.job ?? run.job, startedAt: event.ts };
      case "job.cancelling":
        return { ...run, cancelling: true };
      case "job.finished":
      case "job.failed":
      case "job.cancelled":
        return {
          ...run,
          job: event.job ?? run.job,
          finishedAt: event.ts,
          phase: "idle",
          cancelling: false,
          overall: null,
          steps: run.steps.map((s) =>
            s.status === "running"
              ? { ...s, status: event.kind === "job.finished" ? "ok" : "cancelled" }
              : s,
          ),
        };

      case "build.progress":
        return {
          ...run,
          overall: {
            percent: event.percent ?? 0,
            key: event.key ?? run.overall?.key ?? null,
            label: event.label ?? run.overall?.label ?? null,
            detail: event.detail ?? null,
          },
        };

      case "step.started": {
        const key = `${event.id}#${run.steps.filter((s) => s.id === event.id).length}`;
        return {
          ...run,
          steps: [
            ...run.steps,
            {
              key,
              id: event.id,
              label: event.label,
              status: "running",
              total: event.total ?? null,
              current: 0,
              startedAt: event.ts,
            },
          ],
        };
      }
      case "step.progress":
        return {
          ...run,
          steps: this.patchLast(run.steps, event.id, (step) => ({
            ...step,
            current: event.current ?? step.current,
            total: event.total ?? step.total,
            detail: event.detail ?? step.detail,
          })),
        };
      case "step.total":
        return {
          ...run,
          steps: this.patchLast(run.steps, event.id, (step) => ({ ...step, total: event.total })),
        };
      case "step.finished":
        return {
          ...run,
          steps: this.patchLast(run.steps, event.id, (step) => ({
            ...step,
            status: (event.status ?? "ok") as StepStatus,
            ms: event.ms,
            error: event.error ?? null,
            current: step.total ?? step.current,
          })),
        };

      case "token":
        if (event.channel === "thinking") {
          return {
            ...run,
            phase: "thinking",
            thinking: tail(run.thinking + event.text, MAX_TOKENS),
          };
        }
        return {
          ...run,
          phase: "answering",
          answer: tail(run.answer + event.text, MAX_TOKENS),
        };

      case "retrieval":
        return { ...run, retrieval: { query: event.query, candidates: event.candidates ?? [] } };
      case "guardrail":
        return {
          ...run,
          guardrail: {
            ok: Boolean(event.ok),
            criteria: event.criteria ?? null,
            checked: Boolean(event.checked),
          },
        };
      // Older events carried only the ids; an id with no body still renders as a row.
      case "few_shot":
        return {
          ...run,
          fewShot:
            (event.items as FewShotExemplar[] | undefined) ??
            ((event.ids ?? []) as string[]).map((id) => ({ id, item: {} })),
        };
      // A new prompt is a new item: the panes start empty rather than appending the
      // next item's tokens to the previous one's.
      case "prompt":
        return { ...run, prompt: event.text ?? null, answer: "", thinking: "", phase: "idle" };
      case "repair":
        return {
          ...run,
          repairs: [
            ...run.repairs,
            {
              attempt: event.attempt,
              max_attempts: event.max_attempts,
              error: event.error,
              where: event.where,
            },
          ],
        };
      case "item.produced":
        return {
          ...run,
          phase: "idle",
          items: [
            ...run.items,
            {
              index: event.index,
              item: event.item,
              item_type: event.item_type,
              thinking: event.thinking,
              checks: event.checks,
              retried: event.retried ?? 0,
            },
          ],
        };
      case "item.saved":
        return {
          ...run,
          items: run.items.map((i) =>
            i.index === event.index ? { ...i, saved_id: event.id } : i,
          ),
        };
      case "item.tagged":
        return {
          ...run,
          taggedCount: run.taggedCount + 1,
          tagged: [
            {
              id: event.id,
              text: event.text ?? "",
              concepts: event.concepts ?? [],
              primary_concept: event.primary_concept ?? null,
              method: event.method,
            },
            ...run.tagged,
          ].slice(0, MAX_TAGGED),
        };

      default:
        return run;
    }
  }

  private patchLast(steps: StepView[], id: string, update: (step: StepView) => StepView) {
    for (let i = steps.length - 1; i >= 0; i -= 1) {
      if (steps[i].id === id) {
        const next = [...steps];
        next[i] = update(steps[i]);
        return next;
      }
    }
    return steps;
  }
}

export const runStore = new RunStore();
