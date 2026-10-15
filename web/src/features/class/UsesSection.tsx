import type { ReactNode } from "react";

import { ChoicePill } from "@/components/ui/choice";
import { LoadError, Skeleton, Switch } from "@/components/ui/misc";
import { useRadioGroup } from "@/components/ui/radio";
import { useToast } from "@/components/ui/toast";
import { SectionHeader } from "@/features/admin/Sections";
import { useT, type Key } from "@/lib/i18n";
import type { GroupTool, StudentUses } from "@/lib/types";
import { useSetStudentUses, useStudentUses } from "@/state/queries";

type Use = "generate" | "tutor" | "chat";

const USES: { key: Use; label: Key; open: Key; closed: Key; opened: Key; shut: Key }[] = [
  {
    key: "generate",
    label: "class.uses.generate",
    open: "class.uses.generate.open",
    closed: "class.uses.generate.closed",
    opened: "class.uses.generate.opened",
    shut: "class.uses.generate.shut",
  },
  {
    key: "tutor",
    label: "class.uses.tutor",
    open: "class.uses.tutor.open",
    closed: "class.uses.tutor.closed",
    opened: "class.uses.tutor.opened",
    shut: "class.uses.tutor.shut",
  },
  // The free chat (2026-10-15): closed until a teacher opens it.
  {
    key: "chat",
    label: "class.uses.chat",
    open: "class.uses.chat.open",
    closed: "class.uses.chat.closed",
    opened: "class.uses.chat.opened",
    shut: "class.uses.chat.shut",
  },
];

// What the line under the section says when one tool alone is closed.
const CLOSED_ONE: Record<Use, Key> = {
  generate: "class.uses.generateClosed",
  tutor: "class.uses.tutorClosed",
  chat: "class.uses.chatClosed",
};

/** The line under «Funcionalidades permitidas» in the section list: what is closed to them, if anything. */
export function usesDetail(
  uses: StudentUses | undefined,
  { t, plural }: Pick<ReturnType<typeof useT>, "t" | "plural">,
): string | null {
  if (!uses) return null;
  // A group's own value wins over the subject's; null follows the subject's. The tutor counts
  // only where it is offered; the chat only where the API knows it.
  const open: Partial<Record<Use, boolean>> = {
    generate: uses.group?.generate ?? uses.generate,
    tutor: uses.tutor_offered ? (uses.group?.tutor ?? uses.tutor) : true,
    ...(typeof uses.chat === "boolean" ? { chat: uses.group?.chat ?? uses.chat } : {}),
  };
  const closed = (Object.keys(open) as Use[]).filter((use) => open[use] === false);
  if (closed.length === 0) return t("class.uses.allOpen");
  if (closed.length === 1) return t(CLOSED_ONE[closed[0]]);
  return plural("class.uses.someClosed", closed.length);
}

/**
 * «Funcionalidades permitidas»: whether the subject's students generate exercises, use the tutor
 * and, since 2026-10-15, the free chat — which starts closed.
 *
 * Two switches that act at once — during an exam a teacher closes generating and opens it
 * again after — and bind the students alone (`server/features.refusal`): the teachers keep
 * both. The tutor's switch is drawn wherever the tutor is installed (`tutor_installed`; user's
 * request, 2026-10-07: a teacher looked for it and did not find it); where the administrator
 * has not opened the tutor to any of the students (`tutor_offered`) it is drawn off and still,
 * with the reason, since it would switch nothing.
 */
export function UsesSection({ group = null, scope }: { group?: number | null; scope?: ReactNode }) {
  const { t } = useT();
  const toast = useToast();
  const uses = useStudentUses(group);
  const change = useSetStudentUses(group);
  const named = uses.data?.group?.name;

  const header = (
    <SectionHeader
      title={t("class.uses")}
      description={named ? t("class.uses.groupLead", { name: named }) : t("class.uses.lead")}
      action={scope}
    />
  );

  if (uses.isError) {
    return (
      <>
        {header}
        <LoadError title={t("class.uses.unreadable")} error={uses.error} onRetry={() => uses.refetch()} />
      </>
    );
  }
  if (!uses.data) {
    return (
      <>
        {header}
        <Skeleton className="h-32" />
      </>
    );
  }

  // An older API says nothing of the install: then the tutor is drawn where it is offered; and
  // nothing of the chat, which is then not drawn.
  const installed = uses.data.tutor_installed ?? uses.data.tutor_offered;
  const shown = USES.filter(
    (use) => (use.key !== "tutor" || installed) && (use.key !== "chat" || typeof uses.data.chat === "boolean"),
  );
  const flip = (use: (typeof USES)[number], on: boolean) =>
    change.mutate(
      { [use.key]: on },
      {
        onSuccess: () => toast({ title: t(on ? use.opened : use.shut) }),
        onError: (error: Error) =>
          toast({ title: t("class.failed"), description: error.message, tone: "danger" }),
      },
    );

  // A group's three values: its own open or closed, or the subject's (null).
  const scoped = uses.data.group;
  if (scoped) {
    const set = (use: (typeof USES)[number], value: GroupTool) =>
      change.mutate(
        { [use.key]: value },
        {
          onError: (error: Error) =>
            toast({ title: t("class.failed"), description: error.message, tone: "danger" }),
        },
      );
    return (
      <>
        {header}
        <section className="surface p-5">
          <ul className="rows">
            {shown.map((use) => (
              <GroupToolRow
                key={use.key}
                label={t(use.label)}
                value={scoped[use.key]}
                subjectOpen={Boolean(uses.data[use.key])}
                still={use.key === "tutor" && !uses.data.tutor_offered}
                busy={change.isPending}
                onChange={(value) => set(use, value)}
              />
            ))}
          </ul>
        </section>
      </>
    );
  }

  return (
    <>
      {header}
      <section className="surface p-5">
        <ul className="rows">
          {shown.map((use) => {
            // The tutor's switch is still where the administrator has not opened the tutor here.
            const still = use.key === "tutor" && !uses.data.tutor_offered;
            const on = still ? false : Boolean(uses.data[use.key]);
            return (
              <li key={use.key} className="flex items-start justify-between gap-4">
                <div className="min-w-0 space-y-0.5">
                  <p className="font-medium">{t(use.label)}</p>
                  <p className="text-small text-muted-foreground">
                    {t(still ? "class.uses.tutor.notOffered" : on ? use.open : use.closed)}
                  </p>
                </div>
                <Switch
                  checked={on}
                  label={t(use.label)}
                  disabled={still || change.isPending}
                  onCheckedChange={(next) => flip(use, next)}
                />
              </li>
            );
          })}
        </ul>
      </section>
    </>
  );
}

/** One tool of a group: «Como la asignatura», «Abierto» or «Cerrado», and what the subject says. */
function GroupToolRow({
  label,
  value,
  subjectOpen,
  still,
  busy,
  onChange,
}: {
  label: string;
  value: GroupTool;
  subjectOpen: boolean;
  /** The tutor where the administrator has not offered it: nothing to switch. */
  still: boolean;
  busy: boolean;
  onChange: (value: GroupTool) => void;
}) {
  const { t } = useT();
  const values: GroupTool[] = [null, true, false];
  const radios = useRadioGroup(values, value, onChange);
  const word = (option: GroupTool) =>
    t(option === null ? "class.uses.asSubject" : option ? "class.uses.yes" : "class.uses.no");
  return (
    <li className="flex flex-wrap items-start justify-between gap-4">
      <div className="min-w-0 space-y-0.5">
        <p className="font-medium">{label}</p>
        <p className="text-small text-muted-foreground">
          {t(still ? "class.uses.tutor.notOffered" : subjectOpen ? "class.uses.subjectOpen" : "class.uses.subjectClosed")}
        </p>
      </div>
      <div role="radiogroup" aria-label={label} className="flex flex-wrap gap-2" {...radios.group}>
        {values.map((option) => (
          <ChoicePill
            key={String(option)}
            {...radios.radio(option)}
            chosen={value === option}
            disabled={still || busy}
            onClick={() => onChange(option)}
          >
            {word(option)}
          </ChoicePill>
        ))}
      </div>
    </li>
  );
}
