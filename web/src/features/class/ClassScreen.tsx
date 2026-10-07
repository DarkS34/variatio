import { CalendarX, GraduationCap, Link2, Search, UserCheck, UserMinus, UserX } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Checkbox, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { SectionHeader, Sections, type SectionEntry } from "@/features/admin/Sections";
import { when } from "@/lib/format";
import { useT } from "@/lib/i18n";
import {
  inFilter,
  matchesMember,
  studentsOf,
  viaKey,
  type MemberFilter,
} from "@/lib/members";
import type { Member, MemberAction } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useIsOwner, useSession } from "@/state/auth";
import { useActiveWorkspace, useClassLink, useMemberActions, useMembers } from "@/state/queries";

import { EndCourseSection } from "./EndCourseSection";
import { InviteSection, classLinkDetail } from "./InviteSection";

type ClassSection = "students" | "invite" | "end";

/**
 * The class of the subject in use: its people, for whoever teaches it.
 *
 * Drawn as the administrator's panel draws a tab (`admin/Sections`): the list of its sections
 * beside the section open, one column of blocks under the section's header, rows parted by
 * rules. It opens on «Alumnos», or on «Invitar» while there is nobody to list yet; the
 * others of the plan join the list as they arrive. A student never reaches it: the route is
 * a teacher's (`App`), and so is every read behind it (`/api/members`, `auth.EDIT`).
 */
export function ClassScreen() {
  const { t, plural } = useT();
  const session = useSession();
  const members = useMembers();
  const classLink = useClassLink();
  const owner = useIsOwner();
  // Null until somebody picks: the section to open on depends on the list, which arrives later.
  const [picked, setPicked] = useState<ClassSection | null>(null);
  // The tab's subject, which is the one `/api/members` answered for, and not necessarily the
  // account's last choice that the session flags as active.
  const slug = useActiveWorkspace() ?? session.data?.active_workspace ?? null;
  const subject = session.data?.workspaces.find((row) => row.slug === slug)?.name ?? "";
  const students = studentsOf(members.data?.members ?? []);
  const paused = students.filter((member) => member.disabled_at !== null).length;
  const section: ClassSection = picked ?? (students.length === 0 ? "invite" : "students");

  const items: SectionEntry[] = [
    {
      key: "students",
      label: t("class.students"),
      mark: <GraduationCap className="size-4" />,
      detail: paused
        ? `${plural("class.studentCount", students.length - paused)} · ${plural("class.pausedCount", paused)}`
        : plural("class.studentCount", students.length),
    },
    {
      key: "invite",
      label: t("class.invite"),
      mark: <Link2 className="size-4" />,
      detail: classLink.isSuccess ? classLinkDetail(classLink.data.class_link, t) : null,
    },
    // The owner's alone: ending a course takes every student out at once.
    ...(owner
      ? [{ key: "end", label: t("class.end"), mark: <CalendarX className="size-4" /> }]
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
          {section === "invite" ? (
            <InviteSection subject={subject} slug={slug} />
          ) : section === "end" && owner ? (
            <EndCourseSection subject={subject} />
          ) : (
            <StudentsSection students={students} />
          )}
        </Sections>
      )}
    </div>
  );
}

/**
 * The students of the subject, active and paused: who they are, since when and how they
 * came in, and the three gestures over the ones ticked.
 *
 * Pausing is offered over the active ones ticked and opening over the paused ones; removing
 * over any, and it says it is final and offers to pause instead. Each confirmation names
 * how many it is about. What the server refuses comes back person by person.
 */
function StudentsSection({ students }: { students: Member[] }) {
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
      all: students.length,
    }),
    [students],
  );
  const shown = students.filter((member) => inFilter(member, filter) && matchesMember(member, query));
  const chosen = shown.filter((member) => ticked.has(member.user_id));
  const toPause = chosen.filter((member) => member.disabled_at === null);
  const toOpen = chosen.filter((member) => member.disabled_at !== null);
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
          setTicked(new Set());
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
              { value: "all", label: t("class.filter.all"), badge: <Count n={counts.all} /> },
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

        {/* The gestures stand over the list only while something is ticked: with nothing
            chosen they would answer a press with nothing at all. */}
        {chosen.length > 0 ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-small text-muted-foreground">
              {plural("class.ticked", chosen.length)}
            </span>
            {toPause.length > 0 ? (
              <Button size="sm" variant="outline" disabled={many.isPending} onClick={() => pause(toPause)}>
                <UserX />
                {t("class.pauseN", { n: toPause.length })}
              </Button>
            ) : null}
            {toOpen.length > 0 ? (
              <Button size="sm" variant="outline" disabled={many.isPending} onClick={() => open(toOpen)}>
                <UserCheck />
                {t("class.openN", { n: toOpen.length })}
              </Button>
            ) : null}
            <Button
              size="sm"
              variant="ghost"
              className="text-destructive hover:bg-destructive/10"
              disabled={many.isPending}
              onClick={() => setRemoving(chosen)}
            >
              <UserMinus />
              {t("class.removeN", { n: chosen.length })}
            </Button>
            {many.isPending ? <Spinner /> : null}
          </div>
        ) : null}

        {students.length === 0 ? (
          <p className="text-small text-muted-foreground">{t("class.students.none")}</p>
        ) : shown.length === 0 ? (
          <p className="text-small text-muted-foreground">{t("class.students.noMatch")}</p>
        ) : (
          <Table minWidth="40rem" className="table-fixed">
            <THead>
              <TR>
                <TH className="w-10">
                  <Checkbox
                    checked={allTicked}
                    indeterminate={chosen.length > 0 && !allTicked}
                    label={t("class.tickAll")}
                    onCheckedChange={(on) =>
                      setTicked(on ? new Set(shown.map((member) => member.user_id)) : new Set())
                    }
                  />
                </TH>
                <TH>{t("class.col.student")}</TH>
                <TH className="w-[8rem]">{t("class.col.joined")}</TH>
                <TH className="w-[11rem]">{t("class.col.via")}</TH>
              </TR>
            </THead>
            <TBody>
              {shown.map((member) => (
                <StudentRow
                  key={member.user_id}
                  member={member}
                  ticked={ticked.has(member.user_id)}
                  onTick={(on) => tick(member, on)}
                />
              ))}
            </TBody>
          </Table>
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

function Count({ n }: { n: number }) {
  return <span className="nums text-small text-muted-foreground">{n}</span>;
}

/** One student: who, since when, how they came in, and whether a teacher paused them. */
function StudentRow({
  member,
  ticked,
  onTick,
}: {
  member: Member;
  ticked: boolean;
  onTick: (on: boolean) => void;
}) {
  const { t } = useT();
  const via = viaKey(member.via);
  const paused = member.disabled_at !== null;
  return (
    <TR className={cn(paused && "text-muted-foreground")}>
      <TD className="align-top">
        <Checkbox checked={ticked} label={t("class.tick", { name: member.name })} onCheckedChange={onTick} />
      </TD>
      <TD className="align-top">
        <span className="flex flex-wrap items-center gap-1.5">
          <span className={cn("truncate font-medium", paused ? "text-muted-foreground" : "text-foreground")}>
            {member.name}
          </span>
          {paused ? (
            <Badge variant="outline">
              {t("class.pausedSince", { date: when(member.disabled_at) })}
            </Badge>
          ) : null}
        </span>
        <span className="block truncate font-mono text-small text-muted-foreground">
          {member.username}
        </span>
      </TD>
      <TD className="whitespace-nowrap align-top text-muted-foreground">{when(member.joined_at)}</TD>
      <TD className="align-top text-muted-foreground">
        {via ? t(via) : "—"}
        {member.invited_by ? (
          <span className="block truncate text-small">{t("class.invitedBy", { name: member.invited_by })}</span>
        ) : null}
      </TD>
    </TR>
  );
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
