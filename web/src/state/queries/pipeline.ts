/** The chain: its stages and lanes, the build plans, the scope of a commission. */

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo } from "react";

import { api, getScope } from "@/lib/api";
import { useT, type Key } from "@/lib/i18n";
import { phaseName } from "@/lib/names";
import { isSplitEngine, readLanes } from "@/lib/queue";
import type { ArtifactName, BuildPhase, CommissionScope, JobKind, Lanes } from "@/lib/types";
import { useHasWorkspace } from "../auth";
import { useHealth } from "./core";
import { keys, scoped, stageReviewKeys } from "./keys";

export function usePipeline() {
  return useQuery({
    queryKey: keys.pipeline,
    queryFn: api.pipeline,
    refetchInterval: (query) => (query.state.data?.queue_length ? 5_000 : false),
    enabled: useHasWorkspace(),
  });
}

/**
 * The state of the two queues, one per inference backend, or null.
 *
 * Null is "this server does not split the queue" and not a failure: an API older than this
 * bundle sends no `lanes`, and reading `data.lanes.local` straight would blank the screen
 * on that skew.
 */
export function useLanes(): Lanes | null {
  const pipeline = usePipeline();
  return useMemo(() => readLanes(pipeline.data), [pipeline.data]);
}

/** Whether "el motor" is two halves worth telling apart, as the engine's own name says. */
export function useSplitEngine(): boolean {
  return isSplitEngine(useHealth().data?.engine);
}

export function useContentContext(workspace?: string | null) {
  return useQuery({
    queryKey: scoped(keys.context, workspace),
    queryFn: () => api.context(workspace),
  });
}

/** The phase plan of every builder: what the segmented bar is a drawing of. */
export function useBuildPlans() {
  return useQuery({
    queryKey: keys.phases,
    queryFn: api.buildPhases,
    staleTime: Infinity,
  });
}

/**
 * A plan with every phase named in the reader's language.
 *
 * Named here rather than in `PhaseBar`: a phase key only means something inside its own
 * plan — `convert` is three different phases across the three builders — and the bar is
 * handed a plan with no idea which one it is.
 */
function namedPhases(
  plan: string,
  phases: BuildPhase[] | undefined,
  t: (key: Key) => string,
): BuildPhase[] {
  if (!phases) return [];
  return phases.map((phase) => ({ ...phase, label: phaseName(plan, phase.key, t, phase.label) }));
}

/** The phases of one build, in order. Empty until the plan has arrived, which is what
 *  makes the bar fall back to the plain one instead of drawing a single wrong segment. */
export function useBuildPhases(artifact: ArtifactName | undefined): BuildPhase[] {
  const plans = useBuildPlans();
  const { t } = useT();
  if (!artifact) return [];
  return namedPhases(artifact, plans.data?.artifacts?.[artifact], t);
}

/**
 * What the commission's free-text field may ask for, for one modality.
 *
 * `staleTime: Infinity`: it is derived from artifacts a generation run cannot change, and
 * switching workspace clears the whole cache anyway.
 */
export function useScope(itemType: string | null, workspace?: string | null) {
  return useQuery<CommissionScope>({
    queryKey: scoped(keys.scope(itemType ?? ""), workspace),
    queryFn: () => getScope(itemType!, workspace),
    enabled: Boolean(itemType),
    staleTime: Infinity,
  });
}

/** The same for a job that writes no artifact and still has phases. */
export function useJobPhases(kind: JobKind): BuildPhase[] {
  const plans = useBuildPlans();
  const { t } = useT();
  return namedPhases(kind, plans.data?.jobs?.[kind], t);
}

/**
 * Everything an artifact write can invalidate, in one place.
 *
 * The stage questionnaire belongs here because it goes with the artifact: its read answers
 * whether there is anything built to judge and under which hash the answer is filed, and
 * both stop being true the moment a build ends. With `refetchOnWindowFocus: false` nothing
 * else would refresh it short of a reload.
 */
export function useInvalidateChain() {
  const client = useQueryClient();
  return () => {
    client.invalidateQueries({ queryKey: keys.pipeline });
    client.invalidateQueries({ queryKey: keys.kg });
    client.invalidateQueries({ queryKey: keys.kgGraph });
    client.invalidateQueries({ queryKey: ["bank"] });
    client.invalidateQueries({ queryKey: keys.profile });
    client.invalidateQueries({ queryKey: ["generations"] });
    client.invalidateQueries({ queryKey: stageReviewKeys });
  };
}
