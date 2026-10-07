import { Hourglass } from "lucide-react";

import { EmptyState } from "@/components/ui/misc";
import { useT } from "@/lib/i18n";

/**
 * What a student sees of a subject whose construction is not closed yet.
 *
 * Not the stage in the way and not a way to it: the construction is the teacher's, and a
 * student could act on neither. Nothing on it is a button — there is nothing to do but come
 * back — and it stands for every screen of the subject, so a student never reads a syllabus
 * half corrected.
 */
export function SubjectNotReady() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <EmptyState icon={<Hourglass />} title={t("subject.notReady")} titleAs="h1">
        <p>{t("subject.notReady.body")}</p>
      </EmptyState>
    </div>
  );
}
