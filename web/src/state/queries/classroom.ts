/** «Clase»: people, groups, what the students use, links, invitations and the activity. */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type { ClassLinkTerms, MemberAction, Role } from "@/lib/types";
import { authKeys } from "../auth";
import { keys } from "./keys";

/** The people of the subject in use, for its teachers. Asked only where the list is drawn. */
export function useMembers() {
  return useQuery({ queryKey: keys.members, queryFn: () => api.members() });
}

/**
 * The groups of the class in use, for a teacher choosing who sees an exercise of the bank.
 * `enabled` false where the API has no marks (the demo's), which answers no such route.
 */
export function useClassGroups(enabled = true) {
  return useQuery({
    queryKey: [...keys.members, "groups"],
    queryFn: () => api.memberGroups(),
    enabled,
    select: (data) => data.groups,
  });
}

/**
 * Making, renaming and deleting the groups of the class; every answer moves the people too,
 * and deleting one hides again what of the bank it alone saw.
 */
export function useGroupActions() {
  const client = useQueryClient();
  const refresh = () => {
    client.invalidateQueries({ queryKey: keys.members });
    client.invalidateQueries({ queryKey: ["bank"] });
  };
  return {
    create: useMutation({ mutationFn: (name: string) => api.createGroup(name), onSettled: refresh }),
    rename: useMutation({
      mutationFn: ({ id, name }: { id: number; name: string }) => api.renameGroup(id, name),
      onSettled: refresh,
    }),
    remove: useMutation({ mutationFn: (id: number) => api.deleteGroup(id), onSettled: refresh }),
  };
}

/**
 * Pausing, opening and removing people, one or several at once. Each answer moves the
 * counts «Mis asignaturas» shows, so the listing is asked again with the class.
 */
export function useMemberActions() {
  const client = useQueryClient();
  const refresh = () => {
    client.invalidateQueries({ queryKey: keys.members });
    client.invalidateQueries({ queryKey: keys.workspaces });
  };
  return {
    one: useMutation({
      mutationFn: ({ userId, action }: { userId: number; action: MemberAction }) =>
        api.memberAction(userId, action),
      onSettled: refresh,
    }),
    many: useMutation({
      mutationFn: ({
        userIds,
        action,
        group = null,
      }: {
        userIds: number[];
        action: MemberAction;
        group?: number | null;
      }) => api.membersBulk(action, userIds, group),
      onSettled: refresh,
    }),
  };
}

/**
 * An owner changes a member's role. Its own session reads again too: handing the ownership over
 * ends with the owner's own role lowered, and the screen must stop offering what it no longer may.
 */
export function useChangeRole() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: Role }) => api.changeMemberRole(userId, role),
    onSettled: () => {
      client.invalidateQueries({ queryKey: keys.members });
      client.invalidateQueries({ queryKey: keys.workspaces });
      client.invalidateQueries({ queryKey: authKeys.me });
    },
  });
}

/** The class's weeks, or a group's, the newest first; `student` narrows the figures. */
export function useActivityWeeks(student: number | null, group: number | null = null) {
  return useQuery({
    queryKey: [...keys.activity, "weeks", student, group],
    queryFn: () => api.activityWeeks(student, group),
  });
}

/** One week of the class, of a group, or of one student. */
export function useActivityWeek(week: string | null, student: number | null, group: number | null = null) {
  return useQuery({
    queryKey: [...keys.activity, "week", week, student, group],
    queryFn: () => api.activityWeek(week!, student, group),
    enabled: week !== null,
  });
}

/** Ask for a week's digest; the screen follows its job and reads the week again when it ends. */
export function useWriteDigest() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: ({ week, group = null }: { week: string; group?: number | null }) =>
      api.writeDigest(week, group),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.activity }),
  });
}

/** What the subject's students may use, or one group's, as its teachers set it. */
export function useStudentUses(group: number | null = null) {
  return useQuery({
    queryKey: group === null ? keys.studentUses : [...keys.studentUses, group],
    queryFn: () => api.studentUses(group),
  });
}

/** Open or close a tool to the subject's students, or to one group. */
export function useSetStudentUses(group: number | null = null) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (changes: Partial<Record<"generate" | "tutor" | "chat", boolean | null>>) =>
      api.setStudentUses(changes, group),
    onSuccess: (uses) => {
      client.setQueryData(group === null ? keys.studentUses : [...keys.studentUses, group], uses);
      client.invalidateQueries({ queryKey: keys.members });
    },
  });
}

/** The live link of the class, or of one group, its terms only: how full and until when. */
export function useClassLink(group: number | null = null) {
  return useQuery({
    queryKey: [...keys.classLink, group],
    queryFn: () => api.classLink(group),
  });
}

/**
 * The class link itself, or a group's, opened from its sealed copy. A read of its own, which
 * the server logs, so it is asked only while a link exists to be read and kept for the visit.
 */
export function useClassLinkUrl(enabled: boolean, group: number | null = null) {
  return useQuery({
    queryKey: [...keys.classLinkUrl, group],
    queryFn: () => api.classLinkUrl(group),
    enabled,
    staleTime: Infinity,
    retry: false,
  });
}

/**
 * Minting, renewing, changing and deleting the link of the class, or of one group. A mint's
 * answer carries the new link, so it goes straight into the link's query and nobody asks for
 * it again; a change leaves the link as it was; a deletion leaves that destination with none.
 */
export function useClassLinkActions(group: number | null = null) {
  const client = useQueryClient();
  const terms = [...keys.classLink, group];
  const url = [...keys.classLinkUrl, group];
  return {
    mint: useMutation({
      mutationFn: (body: { max_uses: number; expires_at: string | null }) => api.mintClassLink(body, group),
      onSuccess: ({ class_link, link }) => {
        client.setQueryData(terms, { class_link });
        client.setQueryData(url, { link });
      },
    }),
    edit: useMutation({
      mutationFn: (changes: ClassLinkTerms) => api.editClassLink(changes, group),
      onSuccess: ({ class_link }) => client.setQueryData(terms, { class_link }),
    }),
    revoke: useMutation({
      mutationFn: () => api.revokeClassLink(group),
      onSuccess: () => {
        client.setQueryData(terms, { class_link: null });
        client.removeQueries({ queryKey: url });
      },
    }),
  };
}

/** The personal invitations nobody has used yet: the subject's, or one group's. */
export function useMemberInvites(group: number | null = null) {
  return useQuery({
    queryKey: [...keys.memberInvites, group],
    queryFn: () => api.memberInvites(group),
  });
}

/** Minting personal invitations, one per name, and withdrawing one before anybody uses it. */
export function useMemberInviteActions() {
  const client = useQueryClient();
  const refresh = () => client.invalidateQueries({ queryKey: keys.memberInvites });
  return {
    mint: useMutation({ mutationFn: api.mintMemberInvites, onSettled: refresh }),
    revoke: useMutation({ mutationFn: api.revokeMemberInvite, onSettled: refresh }),
  };
}
