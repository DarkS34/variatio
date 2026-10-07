import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/misc";
import { when } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { viaKey } from "@/lib/members";
import type { Member } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * THE ONE WAY «CLASE» DRAWS A PERSON, a student or a teacher (user's request, 2026-10-07: the
 * two lists looked like two applications).
 *
 * A list is a well of compact rows, as `/raw` draws its documents, under a strip that says what
 * the list holds and, where people can be ticked, carries the box that ticks them all and the
 * gestures over the ticked ones. A row is one line: the box (where there is one), the name and
 * its badges, the username, how and when the person came in, and the row's gestures as small
 * icons, shown on hover or focus.
 */
export function PeopleList({ strip, children }: { strip: ReactNode; children: ReactNode }) {
  return (
    <ul className="well px-1 py-1.5">
      <li className="mx-2 flex min-h-9 flex-wrap items-center gap-2 px-2 py-1.5 text-small">{strip}</li>
      {children}
    </ul>
  );
}

/** One person on one line; see `PeopleList`. */
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
    <li className="mx-2 border-t border-border">
      <div className="group flex min-h-11 items-center gap-2 px-2 py-1.5 text-small">
        {tick ? (
          <Checkbox
            checked={tick.checked}
            label={t("class.tick", { name: member.name })}
            onCheckedChange={tick.onChange}
          />
        ) : null}
        <span className="flex min-w-0 flex-1 items-center gap-2">
          <span
            className={cn("truncate text-body font-medium", paused ? "text-muted-foreground" : "text-foreground")}
            title={member.name}
          >
            {member.name}
          </span>
          <span className="hidden truncate font-mono text-muted-foreground sm:inline">{member.username}</span>
          {badges}
        </span>
        <span className="hidden w-52 shrink-0 truncate text-muted-foreground md:block" title={how || undefined}>
          {how || "—"}
        </span>
        <span className="nums hidden w-40 shrink-0 text-muted-foreground sm:block">
          {member.joined_at ? t("class.joinedOn", { date: when(member.joined_at) }) : "—"}
        </span>
        {/* The gestures keep their room when hidden, so the rows' columns never move. */}
        <span className="flex w-28 shrink-0 items-center justify-end gap-0.5 opacity-0 transition-opacity focus-within:opacity-100 group-focus-within:opacity-100 group-hover:opacity-100">
          {actions}
        </span>
      </div>
    </li>
  );
}

/** One gesture of a row: a small icon named for a screen reader and, on hover, for the eye. */
export function RowAction({
  label,
  title,
  icon,
  onClick,
  disabled,
  danger,
}: {
  label: string;
  title: string;
  icon: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  danger?: boolean;
}) {
  return (
    <Button
      size="icon-sm"
      variant="ghost"
      aria-label={label}
      title={title}
      disabled={disabled}
      onClick={onClick}
      className={danger ? "hover:text-destructive" : undefined}
    >
      {icon}
    </Button>
  );
}
