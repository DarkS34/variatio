import { Check, Copy, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
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
    <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-3">
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
        <code className="min-w-0 flex-1 truncate rounded bg-background px-2 py-1 font-mono text-small">
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
