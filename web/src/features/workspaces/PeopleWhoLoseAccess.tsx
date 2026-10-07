import { useT } from "@/lib/i18n";
import type { SubjectPeople } from "@/lib/types";

/**
 * Who loses the subject with it: its active students and the OTHER teachers — the owner
 * deleting it is not counted. Nothing is said when nobody else is in it.
 */
export function PeopleWhoLoseAccess({
  people,
  others = 1,
}: {
  people?: SubjectPeople;
  /** The people counted among the teachers who are not losing anything: the one deleting. */
  others?: number;
}) {
  const { t, plural } = useT();
  if (!people) return null;
  const teachers = Math.max(0, people.teachers - others);
  if (people.students === 0 && teachers === 0) return null;
  return (
    <p className="font-medium">
      {t("ws.peopleLose", {
        students: plural("class.studentCount", people.students),
        teachers: plural("class.teacherCount", teachers),
      })}
    </p>
  );
}
