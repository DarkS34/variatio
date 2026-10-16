/** Step 2: the syllabus and the course's progress. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, getCurriculum, getGroupCurriculum, putCurriculum } from "@/lib/api";
import { keys, scoped } from "./keys";

export function useKg(workspace?: string | null) {
  return useQuery({ queryKey: scoped(keys.kg, workspace), queryFn: () => api.kg(workspace) });
}

export function useKgGraph(workspace?: string | null) {
  return useQuery({
    queryKey: scoped(keys.kgGraph, workspace),
    queryFn: () => api.kgGraph(workspace),
  });
}

/**
 * What the course has covered («Avance de la asignatura»): a teacher sets it in «Clase», the
 * syllabus tints it, and a student's commission runs inside it.
 */
export function useCurriculum(enabled = true) {
  return useQuery({ queryKey: keys.curriculum, queryFn: () => getCurriculum(), enabled });
}

/** One group's progress, its own or the subject's it follows; the subject's with no group. */
export function useScopedCurriculum(group: number | null) {
  return useQuery({
    queryKey: group === null ? keys.curriculum : [...keys.curriculum, "group", group],
    queryFn: () => (group === null ? getCurriculum() : getGroupCurriculum(group)),
  });
}

/**
 * Save the course's progress, or a group's own, closed under its prerequisites, as the server
 * stores it; `followSubject` hands a group back to the subject's.
 */
export function useSaveCurriculum(group: number | null = null) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ concepts, followSubject = false }: { concepts: string[]; followSubject?: boolean }) =>
      putCurriculum(concepts, true, group === null ? null : { id: group, followSubject }),
    onSuccess: (state) => {
      client.setQueryData(group === null ? keys.curriculum : [...keys.curriculum, "group", group], state);
      if (group === null) client.invalidateQueries({ queryKey: [...keys.curriculum, "group"] });
    },
  });
}
