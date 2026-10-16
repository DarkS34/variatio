/** Step 3: the types of exercise and the bank's coverage. */

import { useQuery } from "@tanstack/react-query";

import { api } from "@/lib/api";
import { useIsStudent } from "../auth";
import { keys, scoped } from "./keys";

export function useProfile(workspace?: string | null) {
  return useQuery({
    queryKey: scoped(keys.profile, workspace),
    queryFn: () => api.profile(workspace),
  });
}

// Never asked for a student: the bank is the construction's (`auth.EDIT`), and its count is
// not on a student's syllabus.
export function useCoverage() {
  return useQuery({ queryKey: keys.coverage, queryFn: api.coverage, enabled: !useIsStudent() });
}
