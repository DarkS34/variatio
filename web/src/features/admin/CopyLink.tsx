import { Check, Copy, X } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useT } from "@/lib/i18n";

/** A credential handed over by hand: the link, the warning, and a copy button. */
export function CopyLink({
  link,
  onDismiss,
  children,
}: {
  link: string;
  /** Put the link away. A credential stays on screen only while it is wanted. */
  onDismiss?: () => void;
  children: React.ReactNode;
}) {
  const { t } = useT();
  return (
    // Held in a well, as everything a block holds that is not a row of data: a frame of its
    // own here was the panel's last bordered box (2026-10-07).
    <div className="well space-y-2 p-4">
      <div className="flex items-start gap-2">
        <p className="min-w-0 flex-1 text-body">{children}</p>
        {onDismiss ? (
          <Button
            variant="ghost"
            size="icon-sm"
            title={t("common.close")}
            aria-label={t("common.close")}
            onClick={onDismiss}
          >
            <X />
          </Button>
        ) : null}
      </div>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded-md bg-sunk px-2.5 py-2 font-mono text-small">
          {link}
        </code>
        <CopyButton text={link} />
      </div>
    </div>
  );
}

/**
 * Put some text on the clipboard and say so for a moment.
 *
 * `compact` drops the word for the rows of a batch, where twenty «Copiar» one under another
 * are a column of noise and the icon already says it; the name stays for the screen reader.
 */
export function CopyButton({
  text,
  label,
  compact = false,
}: {
  text: string;
  label?: string;
  compact?: boolean;
}) {
  const { t } = useT();
  const [copied, setCopied] = useState(false);
  const name = copied ? t("acc.copied") : (label ?? t("acc.copy"));
  return (
    <Button
      type="button"
      size={compact ? "icon-sm" : "sm"}
      variant={compact ? "ghost" : "outline"}
      title={compact ? name : undefined}
      aria-label={compact ? name : undefined}
      onClick={() => {
        navigator.clipboard.writeText(text);
        setCopied(true);
        window.setTimeout(() => setCopied(false), 1500);
      }}
    >
      {copied ? <Check /> : <Copy />}
      {compact ? null : name}
    </Button>
  );
}

/** One link just made, as `LinkTable` lists it. */
export interface MintedLink {
  id: number;
  label?: string | null;
  link: string;
  /** A teacher's invitation, marked beside the name. */
  teacher?: boolean;
  /** Whether it went by mail, where mail was asked for. */
  sent?: boolean;
}

/**
 * THE LINKS A BATCH JUST MADE, one table for the administrator's batch and the teacher's
 * (user's request, 2026-10-07: the same thing was a well of rows in «Clase» and a framed box in
 * «Administración»): the name, the link, whether it was mailed, and its copy button.
 */
export function LinkTable({ label, rows }: { label: string; rows: MintedLink[] }) {
  const { t } = useT();
  const mailed = rows.some((row) => row.sent !== undefined);
  return (
    <Table aria-label={label} minWidth="0" className="table-fixed">
      <THead>
        <tr>
          <TH className="w-48">{t("class.col.invitee")}</TH>
          <TH>{t("class.col.link")}</TH>
          {mailed ? <TH className="w-28">{t("class.col.mail")}</TH> : null}
          <TH className="w-12">
            <span className="sr-only">{t("acc.copy")}</span>
          </TH>
        </tr>
      </THead>
      <TBody>
        {rows.map((row) => (
          <TR key={row.id} className="h-11">
            <TD>
              <span className="flex min-w-0 items-center gap-2">
                <span className="truncate text-body font-medium" title={row.label ?? undefined}>
                  {row.label || "—"}
                </span>
                {row.teacher ? (
                  <Badge variant="outline" className="shrink-0">
                    {t("class.invites.teacherBadge")}
                  </Badge>
                ) : null}
              </span>
            </TD>
            <TD className="truncate font-mono text-muted-foreground" title={row.link}>
              {row.link}
            </TD>
            {mailed ? (
              <TD className={row.sent === false ? "text-destructive" : "text-muted-foreground"}>
                {row.sent === undefined ? "—" : t(row.sent ? "class.invites.sent" : "class.invites.notSent")}
              </TD>
            ) : null}
            <TD className="py-1.5 text-right">
              <CopyButton text={row.link} compact />
            </TD>
          </TR>
        ))}
      </TBody>
    </Table>
  );
}
