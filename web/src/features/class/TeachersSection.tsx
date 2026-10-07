import { ArrowRightLeft, Crown, UserCheck, UserMinus, UserRoundCog } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useConfirm } from "@/components/ui/confirm";
import { RowAction } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { SectionHeader } from "@/features/admin/Sections";
import { useT } from "@/lib/i18n";
import type { Member, Role } from "@/lib/types";
import { ROLE_LABEL_KEYS, useIsOwner, useSession } from "@/state/auth";
import { useChangeRole, useMemberActions } from "@/state/queries";

import { PeopleTable, PersonRow } from "./PersonRow";

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
 * owner's personal invitation, in «Invitar», which this list does not repeat. Drawn as the students are (`PersonRow`), the
 * gestures as icons on the row.
 */
export function TeachersSection({ teachers }: { teachers: Member[] }) {
  const { t } = useT();
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
      <section aria-label={t("class.teachers")} className="surface space-y-4 p-5">
        <PeopleTable
          label={t("class.teachers")}
          captions={{ name: t("class.col.teacher"), how: t("class.col.how"), since: t("class.col.joined") }}
        >
          {teachers.map((member) => {
            const self = member.user_id === me;
            const paused = member.disabled_at !== null;
            return (
              <PersonRow
                key={member.user_id}
                member={member}
                badges={
                  <>
                    <Badge variant={member.role === "owner" ? "settled" : "outline"} className="shrink-0">
                      {t(ROLE_LABEL_KEYS[member.role])}
                    </Badge>
                    {self ? (
                      <Badge variant="outline" className="shrink-0">
                        {t("acc.badge.you")}
                      </Badge>
                    ) : null}
                    {paused ? (
                      <Badge variant="outline" className="shrink-0">
                        {t("activity.paused")}
                      </Badge>
                    ) : null}
                  </>
                }
                actions={
                  owner && !self ? (
                    <>
                      {paused ? (
                        <RowAction
                          label={t("class.teachers.openOne", { name: member.name })}
                          title={t("class.open")}
                          icon={<UserCheck />}
                          disabled={busy}
                          onClick={() => open(member)}
                        />
                      ) : member.role === "editor" ? (
                        <>
                          <RowAction
                            label={t("class.teachers.promoteOne", { name: member.name })}
                            title={t("class.teachers.promote")}
                            icon={<Crown />}
                            disabled={busy}
                            onClick={() => setRole(member, "owner")}
                          />
                          <RowAction
                            label={t("class.teachers.handOverOne", { name: member.name })}
                            title={t("class.teachers.handOver")}
                            icon={<ArrowRightLeft />}
                            disabled={busy}
                            onClick={() => handOver(member)}
                          />
                        </>
                      ) : (
                        <RowAction
                          label={t("class.teachers.demoteOne", { name: member.name })}
                          title={t("class.teachers.demote")}
                          icon={<UserRoundCog />}
                          disabled={busy}
                          onClick={() => setRole(member, "editor")}
                        />
                      )}
                      <RowAction
                        label={t("class.teachers.removeOne", { name: member.name })}
                        title={t("class.remove")}
                        icon={<UserMinus />}
                        disabled={busy}
                        onClick={() => remove(member)}
                        danger
                      />
                    </>
                  ) : null
                }
              />
            );
          })}
        </PeopleTable>
        {owner ? null : <p className="text-small text-muted-foreground">{t("class.teachers.readOnly")}</p>}
      </section>
    </>
  );
}
