/** The queue: the live stream, one job's run, submitting and cancelling. */

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState, useSyncExternalStore } from "react";

import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { localeStore, translator } from "@/lib/i18n";
import { isLive, ownedBy, queuedNotice } from "@/lib/queue";
import type { ArtifactName, JobKind } from "@/lib/types";
import { useSession } from "../auth";
import { runStore, type RunView } from "../runStore";
import { keys } from "./keys";
import { useInvalidateChain, useLanes, useSplitEngine } from "./pipeline";

export function useStream() {
  return useSyncExternalStore(runStore.subscribe, runStore.getSnapshot, runStore.getSnapshot);
}

/** The most recent run that builds this artifact, running or not. */
export function useArtifactRun(artifact: ArtifactName | undefined): RunView | null {
  const stream = useStream();
  return useMemo(() => {
    if (!artifact) return null;
    const runs = Object.values(stream.runs).filter((run) => run.job?.artifact === artifact);
    if (runs.length === 0) return null;
    return runs.sort((a, b) => (b.startedAt ?? 0) - (a.startedAt ?? 0))[0];
  }, [stream, artifact]);
}

/**
 * The most recent run of a job of this kind, running or not.
 *
 * `useArtifactRun` cannot answer this: it keys on the artifact a build writes, and the jobs
 * with no artifact — describing, indexing, tagging — are exactly the ones with nowhere else
 * to say something is happening. With two lanes there is more than one run at a time, so a
 * screen asks for its own kind rather than for whatever the stream last heard from.
 * `accept` must be a module-level function, or the memo re-runs every render.
 */
export function useJobRun(
  kind: JobKind,
  accept?: (run: RunView) => boolean,
): RunView | null {
  const stream = useStream();
  return useMemo(() => {
    const runs = Object.values(stream.runs).filter(
      (run) => run.job?.kind === kind && (!accept || accept(run)),
    );
    if (runs.length === 0) return null;
    return runs.sort((a, b) => (b.startedAt ?? 0) - (a.startedAt ?? 0))[0];
  }, [stream, kind, accept]);
}

/**
 * The most recent run of this kind that THIS account launched.
 *
 * The stream carries the whole workspace, so `useJobRun` alone adopts a colleague's run.
 * A screen about a commission somebody made filters by author; a build screen stays on
 * `useJobRun`, an artifact under construction being under construction for everyone.
 * `ownedBy` fails open when either id is unknown, so an older API degrades to the shared
 * behaviour instead of hiding the run.
 */
export function useOwnJobRun(
  kind: JobKind,
  accept?: (run: RunView) => boolean,
): RunView | null {
  const me = useSession().data?.user.id;
  const stream = useStream();
  return useMemo(() => {
    const runs = Object.values(stream.runs).filter(
      (run) =>
        run.job?.kind === kind && ownedBy(run.job, me) && (!accept || accept(run)),
    );
    if (runs.length === 0) return null;
    return runs.sort((a, b) => (b.startedAt ?? 0) - (a.startedAt ?? 0))[0];
  }, [stream, kind, accept, me]);
}

/** True while a job of this kind is queued or running, whoever launched it. */
export function useJobRunning(kind: JobKind): boolean {
  const run = useJobRun(kind);
  return isLive(run?.job);
}

/** A wall clock that only ticks while something is running. */
export function useElapsed(startedAt: number | null | undefined, live: boolean) {
  const [now, setNow] = useState(() => Date.now() / 1000);
  useEffect(() => {
    if (!live) return;
    const timer = window.setInterval(() => setNow(Date.now() / 1000), 1000);
    return () => window.clearInterval(timer);
  }, [live]);
  if (!startedAt) return null;
  return Math.max(0, (now - startedAt) * 1000);
}

/**
 * Say, once and briefly, that what was just launched is going to wait.
 *
 * About the WAIT and not the launch: a job that starts straight away has nothing to
 * announce. Every launcher goes through here, so no screen keeps a second copy of the rule.
 */
export function useQueuedNotice() {
  const toast = useToast();
  const lanes = useLanes();
  const split = useSplitEngine();
  return (job: Parameters<typeof queuedNotice>[0]) => {
    const notice = queuedNotice(job, lanes, split, translator(localeStore.getSnapshot()));
    if (notice) toast(notice);
  };
}

export function useSubmitJob() {
  const client = useQueryClient();
  const invalidate = useInvalidateChain();
  const announce = useQueuedNotice();
  return useMutation({
    mutationFn: ({
      kind,
      params,
      force,
    }: {
      kind: string;
      params?: Record<string, unknown>;
      force?: boolean;
    }) => api.submitJob(kind, params ?? {}, force ?? false),
    onSuccess: ({ job }) => {
      runStore.setCurrentJob(job.id);
      announce(job);
      invalidate();
    },
    // A commission queued spends a student's day; one refused may have found it spent.
    onSettled: () => client.invalidateQueries({ queryKey: keys.allowance }),
  });
}

/** A generation writes a row, so the saved-variants list is part of the chain now. */

export function useCancelJob() {
  return useMutation({ mutationFn: (id: string) => api.cancelJob(id) });
}
