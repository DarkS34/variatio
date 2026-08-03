import type { Job, VgEvent } from "@/lib/types";

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
  kind: "step" | "model";
  status: StepStatus;
  total?: number | null;
  current?: number;
  detail?: string | null;
  ms?: number;
  startedAt: number;
  error?: string | null;
}

export interface LogLine {
  seq: number;
  ts: number;
  level: string;
  module: string;
  message: string;
}

export interface ProducedItem {
  index: number;
  item: Record<string, unknown>;
  thinking?: string | null;
}

export interface RunView {
  jobId: string;
  job: Job | null;
  steps: StepView[];
  answer: string;
  thinking: string;
  logs: LogLine[];
  items: ProducedItem[];
  repairs: { attempt: number; max_attempts: number; error: string; where: string }[];
  retrieval: { query: string; candidates: [string, number][] } | null;
  fewShot: string[];
  prompt: string | null;
  model: string | null;
  taggedCount: number;
  startedAt: number | null;
  finishedAt: number | null;
}

const MAX_TOKENS = 120_000;
const MAX_LOGS = 3_000;
const MAX_RUNS = 12;

export interface StreamState {
  connected: boolean;
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
    answer: "",
    thinking: "",
    logs: [],
    items: [],
    repairs: [],
    retrieval: null,
    fewShot: [],
    prompt: null,
    model: null,
    taggedCount: 0,
    startedAt: null,
    finishedAt: null,
  };
}

function tail(text: string, limit: number) {
  return text.length > limit ? text.slice(text.length - limit) : text;
}

class RunStore {
  private state: StreamState = {
    connected: false,
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
    if (this.socket && this.socket.readyState <= WebSocket.OPEN) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${window.location.host}/ws?since=${this.state.lastSeq}`;
    const socket = new WebSocket(url);
    this.socket = socket;

    socket.onopen = () => {
      this.retry = 0;
      this.commit({ connected: true });
    };

    socket.onmessage = (message) => {
      const payload = JSON.parse(message.data) as VgEvent & { events?: VgEvent[] };
      if (payload.kind === "stream.ready") {
        this.commit({ gap: Boolean((payload as any).gap) });
        for (const event of payload.events ?? []) this.apply(event);
        this.commit({ lastSeq: Math.max(this.state.lastSeq, (payload as any).last_seq ?? 0) });
        return;
      }
      if (payload.kind === "stream.heartbeat") return;
      this.apply(payload);
    };

    socket.onclose = () => {
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
    switch (event.kind) {
      case "job.queued":
      case "job.started":
        return { ...run, job: event.job ?? run.job, startedAt: event.ts };
      case "job.finished":
      case "job.failed":
      case "job.cancelled":
        return {
          ...run,
          job: event.job ?? run.job,
          finishedAt: event.ts,
          steps: run.steps.map((s) =>
            s.status === "running"
              ? { ...s, status: event.kind === "job.finished" ? "ok" : "cancelled" }
              : s,
          ),
        };

      case "step.started": {
        const key = `${event.id}#${run.steps.filter((s) => s.id === event.id).length}`;
        return {
          ...run,
          steps: [
            ...this.settleModel(run.steps),
            {
              key,
              id: event.id,
              label: event.label,
              kind: "step",
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

      // Swapping weights on one GPU costs real seconds. Showing it as a step is the
      // difference between "working" and "frozen".
      case "model.loading":
        if (run.model === event.model) return run;
        return {
          ...run,
          model: event.model,
          steps: [
            ...this.settleModel(run.steps),
            {
              key: `model:${event.model}#${run.steps.length}`,
              id: `model:${event.model}`,
              label: `Cargando modelo ${event.model}`,
              kind: "model",
              status: "running",
              startedAt: event.ts,
            },
          ],
        };

      case "token": {
        const steps = this.settleModel(run.steps);
        if (event.channel === "thinking") {
          return { ...run, steps, thinking: tail(run.thinking + event.text, MAX_TOKENS) };
        }
        return { ...run, steps, answer: tail(run.answer + event.text, MAX_TOKENS) };
      }

      case "retrieval":
        return { ...run, retrieval: { query: event.query, candidates: event.candidates ?? [] } };
      case "few_shot":
        return { ...run, fewShot: event.ids ?? [] };
      case "prompt":
        return { ...run, prompt: event.text ?? null, answer: "", thinking: "" };
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
          items: [...run.items, { index: event.index, item: event.item, thinking: event.thinking }],
        };
      case "item.tagged":
        return { ...run, taggedCount: run.taggedCount + 1 };

      case "log": {
        const line: LogLine = {
          seq: event.seq,
          ts: event.ts,
          level: event.level,
          module: event.module,
          message: event.message,
        };
        const logs = [...run.logs, line];
        return { ...run, logs: logs.length > MAX_LOGS ? logs.slice(-MAX_LOGS) : logs };
      }

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

  private settleModel(steps: StepView[]) {
    if (!steps.some((s) => s.kind === "model" && s.status === "running")) return steps;
    return steps.map((s) =>
      s.kind === "model" && s.status === "running"
        ? { ...s, status: "ok" as StepStatus, ms: Date.now() - s.startedAt * 1000 }
        : s,
    );
  }
}

export const runStore = new RunStore();
