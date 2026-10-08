import type { ReactNode } from "react";

import { Checkbox } from "@/components/ui/misc";
import { RowGestures, Table, TableBulk, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { when } from "@/lib/format";
import { PersonName } from "@/components/ui/person";
import { useT } from "@/lib/i18n";
import { viaKey } from "@/lib/members";
import type { Member } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * THE ONE WAY «CLASE» DRAWS A LIST OF PEOPLE — students, teachers, unused invitations — and it
 * is the way «Administración» draws its tables (user's request, 2026-10-07: «Clase» sank its
 * lists into a `.well` while the panel's tables lay flat on their block, and the two read as
 * two applications).
 *
 * A table flat on its block: a head of small captions, rows parted by rules that stop short of
 * the block's edge, the name column where the block's title starts. Where people can be ticked,
 * the box that ticks them all is the head's first cell, and once anybody is ticked the head
 * says how many and carries the gestures over them in place of its captions — the same line,
 * so ticking moves nothing.
 *
 * A row is one line of 44 px: the box (where there is one), the name and its badges, the
 * username, how and when the person came in, and the row's gestures as small icons, shown on
 * hover or focus, in a column that keeps its width whatever the row holds.
 */
export const PEOPLE_COLUMNS = {
  how: "hidden w-52 md:table-cell",
  since: "hidden w-40 sm:table-cell",
  gestures: "w-28",
} as const;

export function PeopleTable({
  label,
  captions,
  tick,
  bulk,
  children,
}: {
  /** The table's name for a screen reader. */
  label: string;
  /** The head's three captions: who, how they came in, since when (or until when). */
  captions: { name: string; how: string; since: string };
  /** The head's box, on a list that acts over several. */
  tick?: { checked: boolean; indeterminate: boolean; label: string; onChange: (on: boolean) => void };
  /** In place of the first caption while somebody is ticked: the count and its gestures. */
  bulk?: { count: ReactNode; gestures: ReactNode };
  children: ReactNode;
}) {
  return (
    <Table aria-label={label} minWidth="0" className="table-fixed">
      <THead>
        <tr>
          {tick ? (
            <TH className="w-10 pr-0">
              <Checkbox
                checked={tick.checked}
                indeterminate={tick.indeterminate}
                label={tick.label}
                onCheckedChange={tick.onChange}
              />
            </TH>
          ) : null}
          <TH>
            {bulk ? <TableBulk count={bulk.count}>{bulk.gestures}</TableBulk> : captions.name}
          </TH>
          <TH className={PEOPLE_COLUMNS.how}>{captions.how}</TH>
          <TH className={PEOPLE_COLUMNS.since}>{captions.since}</TH>
          <TH className={PEOPLE_COLUMNS.gestures}>
            <span className="sr-only">{label}</span>
          </TH>
        </tr>
      </THead>
      <TBody>{children}</TBody>
    </Table>
  );
}

/** One person on one line; see `PeopleTable`. */
export function PersonRow({
  member,
  badges,
  tick,
  actions,
}: {
  member: Member;
  /** Beside the name: the role, «Tú», since when the person is paused. */
  badges?: ReactNode;
  /** The box that ticks the row, on a list that acts over several. */
  tick?: { checked: boolean; onChange: (on: boolean) => void };
  /** The row's gestures, as `RowAction`s. */
  actions?: ReactNode;
}) {
  const { t } = useT();
  const via = viaKey(member.via);
  const paused = member.disabled_at !== null;
  const how = [via ? t(via) : null, member.invited_by ? t("class.invitedBy", { name: member.invited_by }) : null]
    .filter(Boolean)
    .join(" ");
  return (
    <TR className="group h-11">
      {tick ? (
        <TD className="pr-0">
          <Checkbox
            checked={tick.checked}
            label={t("class.tick", { name: member.name })}
            onCheckedChange={tick.onChange}
          />
        </TD>
      ) : null}
      <TD>
        <PersonName name={member.name} username={member.username} muted={paused} badges={badges} />
      </TD>
      <TD className={cn(PEOPLE_COLUMNS.how, "truncate text-muted-foreground")} title={how || undefined}>
        {how || "—"}
      </TD>
      <TD className={cn(PEOPLE_COLUMNS.since, "nums text-muted-foreground")}>
        {member.joined_at ? when(member.joined_at) : "—"}
      </TD>
      <TD className="py-1.5">
        <RowGestures>{actions}</RowGestures>
      </TD>
    </TR>
  );
}

