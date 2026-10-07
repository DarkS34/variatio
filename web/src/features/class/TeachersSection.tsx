import { Crown, UserCheck, UserMinus, UserRoundCog } from "lucide-react";
import { useId } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { SectionHeader } from "@/features/admin/Sections";
import { when } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { viaKey } from "@/lib/members";
import type { Member, Role } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ROLE_LABEL_KEYS, useIsOwner, useSession } from "@/state/auth";
import { useChangeRole, useMemberActions } from "@/state/queries";

/** A subject's teachers — its owners first, then by name — active and paused. */
export function teachersOf(members: Member[]): Member[] {
  return members
    .filter((member) => member.role !== "viewer")
    .sort(
      (a, b) =>
        Number(b.role === "owner") - Number(a.role === "owner") ||
        a.name.localeCompare(b.name) ||
        a.username.localeCompare(b.username),
    );
}

/**
 * «Docentes»: who teaches the subject, and — for its owner — what each of them may do.
 *
 * An owner names other owners, lowers them to teacher, opens a paused teacher, removes one, and
 * hands the ownership over: the other becomes owner and the owner's own role drops to teacher,
 * two role changes in that order, so the subject has an owner at every moment and the server's
 * guard (`last_owner`) never has to refuse. Every gesture is asked first. A teacher reads the
 * list and changes nothing; nobody acts on their own row here. Teachers come in through an
 * owner's personal invitation, in «Invitar».
 */
export function TeachersSection({ teachers }: { teachers: Member[] }) {
  const { t } = useT();
  const id = useId();
  const owner = useIsOwner();
  const me = useSession().data?.user.id;
  const confirm = useConfirm();
  const toast = useToast();
  const role = useChangeRole();
  const { one } = useMemberActions();
  const busy = role.isPending || one.isPending;

  const failed = (error: Error) =>
    toast({ title: t("class.failed"), description: error.message, tone: "danger" });

  const setRole = async (member: Member, next: Role) => {
    const promote = next === "owner";
    const asked = await confirm({
      title: t(promote ? "class.teachers.promoteConfirm" : "class.teachers.demoteConfirm", {
        name: member.name,
      }),
      body: t(promote ? "class.teachers.promoteConfirmBody" : "class.teachers.demoteConfirmBody"),
      confirmLabel: t(promote ? "class.teachers.promote" : "class.teachers.demote"),
    });
    if (!asked) return;
    role.mutate(
      { userId: member.user_id, role: next },
      {
        onSuccess: () => toast({ title: t("class.teachers.changed", { name: member.name }) }),
        onError: failed,
      },
    );
  };

  const handOver = async (member: Member) => {
    if (me === undefined) return;
    const asked = await confirm({
      title: t("class.teachers.handOverConfirm", { name: member.name }),
      body: t("class.teachers.handOverConfirmBody", { name: member.name }),
      confirmLabel: t("class.teachers.handOver"),
      tone: "danger",
    });
    if (!asked) return;
    // The other becomes owner FIRST: lowering one's own role while being the only owner is
    // what the server refuses.
    role.mutate(
      { userId: member.user_id, role: "owner" },
      {
        onSuccess: () =>
          role.mutate(
            { userId: me, role: "editor" },
            {
              onSuccess: () => toast({ title: t("class.teachers.handedOver", { name: member.name }) }),
              onError: failed,
            },
          ),
        onError: failed,
      },
    );
  };

  const remove = async (member: Member) => {
    const asked = await confirm({
      title: t("class.teachers.removeConfirm", { name: member.name }),
      body: t("class.teachers.removeConfirmBody"),
      confirmLabel: t("class.remove"),
      tone: "danger",
    });
    if (!asked) return;
    one.mutate(
      { userId: member.user_id, action: "remove" },
      { onSuccess: () => toast({ title: t("class.teachers.removed", { name: member.name }) }), onError: failed },
    );
  };

  const open = (member: Member) =>
    one.mutate(
      { userId: member.user_id, action: "enable" },
      { onSuccess: () => toast({ title: t("class.teachers.opened", { name: member.name }) }), onError: failed },
    );

  return (
    <>
      <SectionHeader title={t("class.teachers")} description={t("class.teachers.lead")} />
      <section aria-labelledby={id} className="surface space-y-4 p-5">
        <h3 id={id} className="sr-only">
          {t("class.teachers")}
        </h3>
        <ul className="rows">
          {teachers.map((member) => {
            const self = member.user_id === me;
            const paused = member.disabled_at !== null;
            const via = viaKey(member.via);
            return (
              <li key={member.user_id} className="flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
                <div className="min-w-0 flex-1">
                  <p className="flex flex-wrap items-center gap-1.5">
                    <span className={cn("truncate font-medium", paused && "text-muted-foreground")}>
                      {member.name}
                    </span>
                    <Badge variant={member.role === "owner" ? "settled" : "outline"}>
                      {t(ROLE_LABEL_KEYS[member.role])}
                    </Badge>
                    {self ? <Badge variant="outline">{t("acc.badge.you")}</Badge> : null}
                    {paused ? <Badge variant="outline">{t("activity.paused")}</Badge> : null}
                  </p>
                  <p className="truncate text-small text-muted-foreground">
                    <span className="font-mono">{member.username}</span>
                    {member.joined_at ? ` · ${t("class.joinedOn", { date: when(member.joined_at) })}` : ""}
                    {via ? ` · ${t(via)}` : ""}
                  </p>
                </div>
                {owner && !self ? (
                  <div className="flex flex-wrap items-center gap-1">
                    {paused ? (
                      <Button size="sm" variant="ghost" disabled={busy} onClick={() => open(member)}>
                        <UserCheck />
                        {t("class.open")}
                      </Button>
                    ) : member.role === "editor" ? (
                      <>
                        <Button size="sm" variant="ghost" disabled={busy} onClick={() => setRole(member, "owner")}>
                          <Crown />
                          {t("class.teachers.promote")}
                        </Button>
                        <Button size="sm" variant="ghost" disabled={busy} onClick={() => handOver(member)}>
                          <UserRoundCog />
                          {t("class.teachers.handOver")}
                        </Button>
                      </>
                    ) : (
                      <Button size="sm" variant="ghost" disabled={busy} onClick={() => setRole(member, "editor")}>
                        <UserRoundCog />
                        {t("class.teachers.demote")}
                      </Button>
                    )}
                    <Button
                      size="sm"
                      variant="ghost"
                      className="text-destructive hover:text-destructive"
                      disabled={busy}
                      onClick={() => remove(member)}
                    >
                      <UserMinus />
                      {t("class.remove")}
                    </Button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
        <p className="text-small text-muted-foreground">
          {t(owner ? "class.teachers.inviteHint" : "class.teachers.readOnly")}
        </p>
      </section>
    </>
  );
}
