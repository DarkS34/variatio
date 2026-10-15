import { Pencil, Plus, Trash2, Users } from "lucide-react";
import { useId, useState } from "react";

import { Button } from "@/components/ui/button";
import { ChoicePill } from "@/components/ui/choice";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { useRadioGroup } from "@/components/ui/radio";
import { RowAction, RowGestures } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { SectionHeader } from "@/features/admin/Sections";
import { useT } from "@/lib/i18n";
import type { ClassGroup, Member } from "@/lib/types";
import { useGroupActions, useMemberActions } from "@/state/queries";

/** The line under «Grupos» in the section list: how many there are. */
export function groupsDetail(groups: ClassGroup[] | undefined, plural: ReturnType<typeof useT>["plural"]) {
  if (!groups) return null;
  return plural("class.groups.count", groups.length);
}

/**
 * «Grupos»: the parts of the class a teacher treats apart (the user's decision, 2026-10-14).
 *
 * With a group a teacher does what they do with the whole class — open or close each tool to
 * it, read its activity and its own digest, give it its own progress, its own link — from
 * each section of «Clase», whose scope chooses it. Here the groups are made, renamed and
 * deleted; a group opens «Alumnos» on itself. A student is in one group at most, for now.
 */
export function GroupsSection({
  groups,
  onOpen,
}: {
  groups: ClassGroup[];
  /** Opens «Alumnos» on one group. */
  onOpen: (group: number) => void;
}) {
  const { t, plural } = useT();
  const confirm = useConfirm();
  const toast = useToast();
  const actions = useGroupActions();
  const [naming, setNaming] = useState<ClassGroup | "new" | null>(null);

  const failed = (error: Error) =>
    toast({ title: t("class.failed"), description: error.message, tone: "danger" });

  const remove = async (group: ClassGroup) => {
    const asked = await confirm({
      title: t("class.groups.deleteConfirm", { name: group.name }),
      body: plural("class.groups.deleteConfirmBody", group.students),
      confirmLabel: t("class.groups.delete"),
      tone: "danger",
    });
    if (asked) actions.remove.mutate(group.id, { onError: failed });
  };

  return (
    <>
      <SectionHeader
        title={t("class.groups")}
        description={t("class.groups.lead")}
        action={
          <Button variant="outline" onClick={() => setNaming("new")}>
            <Plus />
            {t("class.groups.new")}
          </Button>
        }
      />
      <section className="surface p-5">
        {groups.length === 0 ? (
          <p className="text-small text-muted-foreground">{t("class.groups.none")}</p>
        ) : (
          <ul className="rows">
            {groups.map((group) => (
              <li key={group.id} className="group flex items-center gap-3">
                <Users className="size-4 shrink-0 text-muted-foreground" aria-hidden />
                <button
                  type="button"
                  className="min-w-0 flex-1 text-left"
                  onClick={() => onOpen(group.id)}
                  title={t("class.groups.open", { name: group.name })}
                >
                  <span className="block truncate font-medium hover:underline">{group.name}</span>
                  <span className="block text-small text-muted-foreground">
                    {plural("class.studentCount", group.students)}
                  </span>
                </button>
                <RowGestures>
                  <RowAction
                    label={t("class.groups.renameOne", { name: group.name })}
                    title={t("class.groups.rename")}
                    icon={<Pencil />}
                    onClick={() => setNaming(group)}
                  />
                  <RowAction
                    label={t("class.groups.deleteOne", { name: group.name })}
                    title={t("class.groups.delete")}
                    icon={<Trash2 />}
                    onClick={() => remove(group)}
                    danger
                  />
                </RowGestures>
              </li>
            ))}
          </ul>
        )}
      </section>

      {naming ? (
        <NameDialog
          group={naming === "new" ? null : naming}
          busy={actions.create.isPending || actions.rename.isPending}
          onClose={() => setNaming(null)}
          onSave={(name) => {
            const done = { onSuccess: () => setNaming(null), onError: failed };
            if (naming === "new") actions.create.mutate(name, done);
            else actions.rename.mutate({ id: naming.id, name }, done);
          }}
        />
      ) : null}
    </>
  );
}

/** A group's name, new or changed. */
function NameDialog({
  group,
  busy,
  onClose,
  onSave,
}: {
  group: ClassGroup | null;
  busy: boolean;
  onClose: () => void;
  onSave: (name: string) => void;
}) {
  const { t } = useT();
  const id = useId();
  const [name, setName] = useState(group?.name ?? "");
  return (
    <Dialog
      open
      onClose={onClose}
      title={group ? t("class.groups.renameTitle", { name: group.name }) : t("class.groups.new")}
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button disabled={busy || !name.trim()} onClick={() => onSave(name)}>
            {busy ? <Spinner /> : null}
            {t("common.save")}
          </Button>
        </>
      }
    >
      <form
        className="space-y-1.5"
        onSubmit={(event) => {
          event.preventDefault();
          if (name.trim()) onSave(name);
        }}
      >
        <Label htmlFor={id}>{t("class.groups.name")}</Label>
        <Input id={id} value={name} maxLength={80} autoFocus onChange={(event) => setName(event.target.value)} />
      </form>
    </Dialog>
  );
}

/**
 * «Cambiar de grupo» of one student or of the ones ticked: one of the groups, or none.
 *
 * Moving a student keeps everything else of theirs; a paused one keeps the group it is in.
 */
export function MoveDialog({
  people,
  groups,
  onClose,
}: {
  people: Member[];
  groups: ClassGroup[];
  onClose: () => void;
}) {
  const { t, plural } = useT();
  const toast = useToast();
  const { many } = useMemberActions();
  const shared = new Set(people.map((member) => member.group?.id ?? null));
  const [target, setTarget] = useState<number | null>(shared.size === 1 ? [...shared][0] : null);
  const values: (number | null)[] = [null, ...groups.map((group) => group.id)];
  const radios = useRadioGroup(values, target, setTarget);

  const move = () =>
    many.mutate(
      { action: "group", userIds: people.map((member) => member.user_id), group: target },
      {
        onSuccess: ({ done, refused }) => {
          if (done.length > 0) {
            const name = groups.find((group) => group.id === target)?.name;
            toast({
              title: name
                ? plural("class.groups.moved", done.length, { name })
                : plural("class.groups.takenOut", done.length),
            });
          }
          for (const refusal of refused) {
            const who = people.find((member) => member.user_id === refusal.user_id);
            toast({
              title: t("class.refused", { name: who?.name ?? String(refusal.user_id) }),
              description: refusal.reason,
              tone: "danger",
            });
          }
          onClose();
        },
        onError: (error: Error) =>
          toast({ title: t("class.failed"), description: error.message, tone: "danger" }),
      },
    );

  return (
    <Dialog
      open
      onClose={onClose}
      title={
        people.length === 1
          ? t("class.groups.moveOneTitle", { name: people[0].name })
          : plural("class.groups.moveTitle", people.length)
      }
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button disabled={many.isPending} onClick={move}>
            {many.isPending ? <Spinner /> : null}
            {t("class.groups.move")}
          </Button>
        </>
      }
    >
      <div role="radiogroup" aria-label={t("class.groups")} className="flex flex-wrap gap-2" {...radios.group}>
        {values.map((value) => (
          <ChoicePill key={value ?? "none"} {...radios.radio(value)} chosen={target === value} onClick={() => setTarget(value)}>
            {value === null ? t("class.groups.noGroup") : groups.find((group) => group.id === value)?.name}
          </ChoicePill>
        ))}
      </div>
    </Dialog>
  );
}
