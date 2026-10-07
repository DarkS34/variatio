import {
  Activity,
  CalendarX,
  GraduationCap,
  MessagesSquare,
  Play,
  Search,
  SlidersHorizontal,
  Spline,
  UserCheck,
  UserPlus,
  UserRoundCog,
  UserMinus,
  UserX,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Checkbox, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { SectionHeader, Sections, type SectionEntry } from "@/features/admin/Sections";
import { when } from "@/lib/format";
import { useT } from "@/lib/i18n";
import {
  inFilter,
  matchesMember,
  studentsOf,
  type MemberFilter,
} from "@/lib/members";
import type { Member, MemberAction } from "@/lib/types";
import { useIsOwner, useSession } from "@/state/auth";
import {
  useActiveWorkspace,
  useActivityWeeks,
  useClassLink,
  useCurriculum,
  useMemberActions,
  useMemberInvites,
  useMembers,
  useStudentUses,
} from "@/state/queries";

import { ActivitySection, activityDetail, type ActivityView } from "./ActivitySection";
import { EndCourseSection } from "./EndCourseSection";
import { InviteSection, inviteDetail } from "./InviteSection";
import { PeopleList, PersonRow, RowAction } from "./PersonRow";
import { ProgressSection, progressDetail } from "./ProgressSection";
import { TeachersSection, teachersOf } from "./TeachersSection";
import { UsesSection, usesDetail } from "./UsesSection";

type ClassSection = ActivityView | "students" | "teachers" | "invite" | "progress" | "uses" | "end";

const ACTIVITY_VIEWS: readonly string[] = ["exercises", "tutor"] satisfies ActivityView[];

/**
 * The class of the subject in use: its people, for whoever teaches it.
 *
 * Drawn as the administrator's panel draws a tab (`admin/Sections`): the list of its sections
 * beside the section open, each section one subject of its own so a page is read without
 * scrolling past another (user's requests, 2026-10-07). The list goes in three groups, each
 * named by a caption: «Miembros» (students, teachers, and «Invitar», the two ways in), then
 * «Actividad» (one page for each thing a student uses: the exercises, and the tutor where it
 * is installed), then «Curso» (the subject's progress, what its students may use); the
 * owner's «Fin de curso» stands apart under the list, tinted as damage is. The two pages of
 * the activity share the scope and the week chosen, held here. It opens on «Alumnos», or on
 * «Invitar» while there is nobody to list yet. A student never reaches it: the route is a
 * teacher's (`App`), and so is every read behind it (`/api/members`, `auth.EDIT`).
 */
export function ClassScreen() {
  const tr = useT();
  const { t, plural } = tr;
  const session = useSession();
  const members = useMembers();
  const classLink = useClassLink();
  const invites = useMemberInvites();
  const progress = useCurriculum();
  const uses = useStudentUses();
  const activity = useActivityWeeks(null);
  // The student the activity reads, or the whole class, and the week open: kept here so the
  // activity's two pages share them and «Alumnos» can open them on one student.
  const [activityOf, setActivityOf] = useState<number | null>(null);
  const [activityWeek, setActivityWeek] = useState<string | null>(null);
  const owner = useIsOwner();
  // Null until somebody picks: the section to open on depends on the list, which arrives later.
  const [picked, setPicked] = useState<ClassSection | null>(null);
  // The tab's subject, which is the one `/api/members` answered for, and not necessarily the
  // account's last choice that the session flags as active.
  const slug = useActiveWorkspace() ?? session.data?.active_workspace ?? null;
  const subject = session.data?.workspaces.find((row) => row.slug === slug)?.name ?? "";
  const students = studentsOf(members.data?.members ?? []);
  const teachers = teachersOf(members.data?.members ?? []);
  const paused = students.filter((member) => member.disabled_at !== null).length;
  const tutorInstalled = activity.data?.tutor === true;
  const fallback: ClassSection = students.length === 0 ? "invite" : "students";
  const section: ClassSection = picked === "tutor" && !tutorInstalled ? fallback : (picked ?? fallback);

  const items: SectionEntry[] = [
    {
      key: "students",
      group: t("class.group.members"),
      label: t("class.students"),
      mark: <GraduationCap className="size-4" />,
      detail: paused
        ? `${plural("class.studentCount", students.length - paused)} · ${plural("class.pausedCount", paused)}`
        : plural("class.studentCount", students.length),
    },
    {
      key: "teachers",
      label: t("class.teachers"),
      mark: <UserRoundCog className="size-4" />,
      detail: plural("class.teachers.count", teachers.length),
    },
    {
      key: "invite",
      label: t("class.invite"),
      mark: <UserPlus className="size-4" />,
      detail:
        classLink.isSuccess && invites.isSuccess
          ? inviteDetail(classLink.data.class_link, invites.data.invites, tr)
          : null,
    },
    {
      key: "exercises",
      group: t("class.group.activity"),
      label: t("class.activity.exercises"),
      mark: <Play className="size-4" />,
      detail: activityDetail(activity.data, "exercises", tr),
    },
    // Where the tutor is not installed there is nothing of it to count.
    ...(tutorInstalled
      ? [
          {
            key: "tutor",
            label: t("class.activity.tutor"),
            mark: <MessagesSquare className="size-4" />,
            detail: activityDetail(activity.data, "tutor", tr),
          },
        ]
      : []),
    {
      key: "progress",
      group: t("class.group.course"),
      label: t("class.progress"),
      mark: <Spline className="size-4" />,
      detail: progressDetail(progress.data, t),
    },
    {
      key: "uses",
      label: t("class.uses"),
      mark: <SlidersHorizontal className="size-4" />,
      detail: usesDetail(uses.data, t),
    },
    // The owner's alone: ending a course takes every student out at once, so it stands apart.
    ...(owner
      ? [
          {
            key: "end",
            label: t("class.end"),
            mark: <CalendarX className="size-4" />,
            apart: true,
            tone: "danger" as const,
          },
        ]
      : []),
  ];

  return (
    <div className="space-y-5">
      <header className="space-y-1.5">
        <h1 className="font-display font-expanded text-display">{t("class.title")}</h1>
        <p className="max-w-[74ch] text-body text-muted-foreground">
          {t("class.lead", { subject })}
        </p>
      </header>

      {members.isError ? (
        <LoadError
          title={t("class.unreadable")}
          error={members.error}
          onRetry={() => members.refetch()}
        />
      ) : members.isLoading ? (
        <Skeleton className="h-96" />
      ) : (
        <Sections
          label={t("class.sections")}
          items={items}
          value={section}
          onChange={(key) => setPicked(key as ClassSection)}
        >
          {ACTIVITY_VIEWS.includes(section) ? (
            <ActivitySection
              view={section as ActivityView}
              student={activityOf}
              onStudent={setActivityOf}
              week={activityWeek}
              onWeek={setActivityWeek}
            />
          ) : section === "invite" ? (
            <InviteSection subject={subject} slug={slug} />
          ) : section === "teachers" ? (
            <TeachersSection teachers={teachers} />
          ) : section === "progress" ? (
            <ProgressSection />
          ) : section === "uses" ? (
            <UsesSection />
          ) : section === "end" && owner ? (
            <EndCourseSection subject={subject} />
          ) : (
            <StudentsSection
              students={students}
              onActivity={(id) => {
                setActivityOf(id);
                setPicked("exercises");
              }}
            />
          )}
        </Sections>
      )}
    </div>
  );
}

/**
 * The students of the subject, active or paused: who they are, how and when they came in,
 * and the three gestures, over one student or over the ones ticked.
 *
 * Drawn as `/raw` draws its documents: one compact row per person in a well, a strip over
 * them with the box that ticks the whole list and the gestures over what is ticked, and on
 * each row the same gestures as small icons, shown on hover or focus. A table with a column
 * per fact left most of its width empty. Each filter holds one kind of student, so its
 * strip offers one way to change them (pause the active, open the paused) plus removing,
 * which says it is final and offers to pause instead. Each confirmation names how many it is
 * about; what the server refuses comes back person by person.
 */
function StudentsSection({
  students,
  onActivity,
}: {
  students: Member[];
  onActivity: (id: number) => void;
}) {
  const { t, plural } = useT();
  const confirm = useConfirm();
  const toast = useToast();
  const { many } = useMemberActions();
  const [filter, setFilter] = useState<MemberFilter>("active");
  const [query, setQuery] = useState("");
  const [ticked, setTicked] = useState<Set<number>>(new Set());
  const [removing, setRemoving] = useState<Member[] | null>(null);

  const counts = useMemo(
    () => ({
      active: students.filter((member) => inFilter(member, "active")).length,
      disabled: students.filter((member) => inFilter(member, "disabled")).length,
    }),
    [students],
  );
  const shown = students.filter((member) => inFilter(member, filter) && matchesMember(member, query));
  const chosen = shown.filter((member) => ticked.has(member.user_id));
  const allTicked = shown.length > 0 && chosen.length === shown.length;

  const tick = (member: Member, on: boolean) =>
    setTicked((held) => {
      const next = new Set(held);
      if (on) next.add(member.user_id);
      else next.delete(member.user_id);
      return next;
    });

  const run = (action: MemberAction, people: Member[]) =>
    many.mutate(
      { action, userIds: people.map((member) => member.user_id) },
      {
        onSuccess: ({ done, refused }) => {
          setTicked((held) => {
            const next = new Set(held);
            for (const member of people) next.delete(member.user_id);
            return next;
          });
          if (done.length > 0) {
            toast({ title: plural(DONE_KEYS[action], done.length) });
          }
          for (const refusal of refused) {
            const who = people.find((member) => member.user_id === refusal.user_id);
            toast({
              title: t("class.refused", { name: who?.name ?? String(refusal.user_id) }),
              description: refusal.reason,
              tone: "danger",
            });
          }
        },
        onError: (error: Error) =>
          toast({ title: t("class.failed"), description: error.message, tone: "danger" }),
      },
    );

  const pause = async (people: Member[]) => {
    const asked = await confirm({
      title: plural("class.pauseConfirm", people.length),
      body: t("class.pauseConfirmBody"),
      confirmLabel: t("class.pause"),
    });
    if (asked) run("disable", people);
  };

  const open = async (people: Member[]) => {
    const asked = await confirm({
      title: plural("class.openConfirm", people.length),
      body: t("class.openConfirmBody"),
      confirmLabel: t("class.open"),
    });
    if (asked) run("enable", people);
  };

  // The gesture that changes access, for the kind of student this filter holds.
  const change = (people: Member[]) => (filter === "active" ? pause(people) : open(people));

  return (
    <>
      <SectionHeader title={t("class.students")} description={t("class.students.lead")} />

      <section className="surface space-y-4 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <Tabs
            value={filter}
            onChange={(next) => {
              setFilter(next as MemberFilter);
              setTicked(new Set());
            }}
            items={[
              { value: "active", label: t("class.filter.active"), badge: <Count n={counts.active} /> },
              { value: "disabled", label: t("class.filter.paused"), badge: <Count n={counts.disabled} /> },
            ]}
          />
          <div className="relative ml-auto w-full sm:w-72">
            <Search className="pointer-events-none absolute left-2.5 top-2.5 size-4 text-muted-foreground" />
            <Input
              type="search"
              value={query}
              aria-label={t("class.search")}
              placeholder={t("class.search")}
              className="pl-8"
              onChange={(event) => setQuery(event.target.value)}
            />
          </div>
        </div>

        {students.length === 0 ? (
          <p className="text-small text-muted-foreground">{t("class.students.none")}</p>
        ) : shown.length === 0 ? (
          <p className="text-small text-muted-foreground">
            {query.trim() ? t("class.students.noMatch") : t(EMPTY_KEYS[filter])}
          </p>
        ) : (
          <PeopleList
            strip={
              <>
                <Checkbox
                  checked={allTicked}
                  indeterminate={chosen.length > 0 && !allTicked}
                  label={t("class.tickAll")}
                  onCheckedChange={(on) =>
                    setTicked(on ? new Set(shown.map((member) => member.user_id)) : new Set())
                  }
                />
                <span className="min-w-0 flex-1 truncate text-muted-foreground">
                  {chosen.length > 0 ? plural("class.ticked", chosen.length) : t("class.tickAll")}
                </span>
                {chosen.length > 0 ? (
                  <span className="flex items-center gap-1">
                    {many.isPending ? <Spinner /> : null}
                    <Button
                      size="sm"
                      variant="ghost"
                      className="-my-1 h-7"
                      disabled={many.isPending}
                      onClick={() => change(chosen)}
                    >
                      {filter === "active" ? <UserX /> : <UserCheck />}
                      {t(filter === "active" ? "class.pauseN" : "class.openN", { n: chosen.length })}
                    </Button>
                    <Button
                      size="sm"
                      variant="ghost"
                      className="-my-1 h-7 text-destructive hover:text-destructive"
                      disabled={many.isPending}
                      onClick={() => setRemoving(chosen)}
                    >
                      <UserMinus />
                      {t("class.removeN", { n: chosen.length })}
                    </Button>
                  </span>
                ) : null}
              </>
            }
          >
            {shown.map((member) => {
              const paused = member.disabled_at !== null;
              return (
                <PersonRow
                  key={member.user_id}
                  member={member}
                  tick={{ checked: ticked.has(member.user_id), onChange: (on) => tick(member, on) }}
                  badges={
                    paused ? (
                      <Badge variant="outline" className="shrink-0">
                        {t("class.pausedSince", { date: when(member.disabled_at) })}
                      </Badge>
                    ) : null
                  }
                  actions={
                    <>
                      <RowAction
                        label={t("class.viewActivity", { name: member.name })}
                        title={t("class.viewActivityShort")}
                        icon={<Activity />}
                        onClick={() => onActivity(member.user_id)}
                      />
                      <RowAction
                        label={t(paused ? "class.openOne" : "class.pauseOne", { name: member.name })}
                        title={t(paused ? "class.open" : "class.pause")}
                        icon={paused ? <UserCheck /> : <UserX />}
                        disabled={many.isPending}
                        onClick={() => change([member])}
                      />
                      <RowAction
                        label={t("class.removeOne", { name: member.name })}
                        title={t("class.remove")}
                        icon={<UserMinus />}
                        disabled={many.isPending}
                        onClick={() => setRemoving([member])}
                        danger
                      />
                    </>
                  }
                />
              );
            })}
          </PeopleList>
        )}
      </section>

      <RemoveDialog
        people={removing}
        busy={many.isPending}
        onClose={() => setRemoving(null)}
        onRemove={(people) => {
          setRemoving(null);
          run("remove", people);
        }}
        onPause={(people) => {
          setRemoving(null);
          run("disable", people);
        }}
      />
    </>
  );
}

const DONE_KEYS = {
  disable: "class.paused",
  enable: "class.opened",
  remove: "class.removed",
} as const;

const EMPTY_KEYS = {
  active: "class.students.noneActive",
  disabled: "class.students.nonePaused",
} as const;

function Count({ n }: { n: number }) {
  return <span className="nums text-small text-muted-foreground">{n}</span>;
}

/**
 * Removing, said for what it is: final, with the way that can be undone offered beside it.
 *
 * A dialog of its own and not the shared confirmation, because it has two answers besides
 * «no»: remove, or pause instead.
 */
function RemoveDialog({
  people,
  busy,
  onClose,
  onRemove,
  onPause,
}: {
  people: Member[] | null;
  busy: boolean;
  onClose: () => void;
  onRemove: (people: Member[]) => void;
  onPause: (people: Member[]) => void;
}) {
  const { t, plural } = useT();
  const pausable = (people ?? []).filter((member) => member.disabled_at === null);
  return (
    <Dialog
      open={people !== null}
      onClose={onClose}
      title={plural("class.removeConfirm", people?.length ?? 0)}
      className="max-w-lg"
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          {pausable.length > 0 ? (
            <Button variant="outline" disabled={busy} onClick={() => onPause(pausable)}>
              <UserX />
              {t("class.pauseInstead")}
            </Button>
          ) : null}
          <Button variant="destructive" disabled={busy} onClick={() => people && onRemove(people)}>
            <UserMinus />
            {t("class.remove")}
          </Button>
        </>
      }
    >
      <p className="text-body">{t("class.removeConfirmBody")}</p>
    </Dialog>
  );
}
