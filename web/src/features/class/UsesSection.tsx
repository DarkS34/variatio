import { LoadError, Skeleton, Switch } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { SectionHeader } from "@/features/admin/Sections";
import { useT, type Key } from "@/lib/i18n";
import type { StudentUses } from "@/lib/types";
import { useSetStudentUses, useStudentUses } from "@/state/queries";

type Use = "generate" | "tutor";

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
];

/** The line under «Qué usan los alumnos» in the section list: what is closed to them, if anything. */
export function usesDetail(
  uses: StudentUses | undefined,
  t: ReturnType<typeof useT>["t"],
): string | null {
  if (!uses) return null;
  const tutor = uses.tutor_offered ? uses.tutor : true;
  if (uses.generate && tutor) return t("class.uses.allOpen");
  if (!uses.generate && !tutor) return t("class.uses.bothClosed");
  return t(uses.generate ? "class.uses.tutorClosed" : "class.uses.generateClosed");
}

/**
 * «Qué usan los alumnos»: whether the subject's students generate exercises and use the tutor.
 *
 * Two switches that act at once — during an exam a teacher closes generating and opens it
 * again after — and bind the students alone (`server/features.refusal`): the teachers keep
 * both. The tutor's switch is drawn only where the administrator opened the tutor to one of
 * the students (`tutor_offered`): elsewhere it would switch nothing.
 */
export function UsesSection() {
  const { t } = useT();
  const toast = useToast();
  const uses = useStudentUses();
  const change = useSetStudentUses();

  const header = <SectionHeader title={t("class.uses")} description={t("class.uses.lead")} />;

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

  const shown = USES.filter((use) => use.key !== "tutor" || uses.data.tutor_offered);
  const flip = (use: (typeof USES)[number], on: boolean) =>
    change.mutate(
      { [use.key]: on },
      {
        onSuccess: () => toast({ title: t(on ? use.opened : use.shut) }),
        onError: (error: Error) =>
          toast({ title: t("class.failed"), description: error.message, tone: "danger" }),
      },
    );

  return (
    <>
      {header}
      <section className="surface p-5">
        <ul className="rows">
          {shown.map((use) => {
            const on = uses.data[use.key];
            return (
              <li key={use.key} className="flex items-start justify-between gap-4 py-3">
                <div className="min-w-0 space-y-0.5">
                  <p className="font-medium">{t(use.label)}</p>
                  <p className="text-small text-muted-foreground">{t(on ? use.open : use.closed)}</p>
                </div>
                <Switch
                  checked={on}
                  label={t(use.label)}
                  disabled={change.isPending}
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
