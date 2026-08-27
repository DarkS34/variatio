import { Check, Pencil } from "lucide-react";
import type { ReactNode } from "react";

import { InfoHint } from "@/components/ui/hint";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

/**
 * One question of the form: open while it is being answered, one line once it is.
 *
 * The collapsed line is not decoration — it is what keeps four questions on screen at
 * once without four cards' worth of chrome, so going back to change the concepts costs
 * one click and no scrolling.
 */
export function FormStep({
  index,
  title,
  hint,
  optional = false,
  open,
  answered,
  summary,
  onOpen,
  children,
}: {
  index: number;
  title: string;
  hint?: ReactNode;
  optional?: boolean;
  open: boolean;
  answered: boolean;
  summary: ReactNode;
  onOpen: () => void;
  children: ReactNode;
}) {
  const { t } = useT();
  return (
    <section
      className={cn(
        "animate-slide-up rounded-xl border transition-colors",
        open ? "border-border bg-card shadow-sm" : "border-transparent",
      )}
    >
      <button
        type="button"
        onClick={onOpen}
        aria-expanded={open}
        className={cn(
          "group flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-left transition-colors",
          !open && "hover:bg-accent/40",
        )}
      >
        <span
          className={cn(
            "flex size-6 shrink-0 items-center justify-center rounded-full text-small font-semibold nums transition-colors",
            answered
              ? "bg-primary/12 text-primary"
              : open
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground",
          )}
        >
          {answered && !open ? <Check className="size-3.5" /> : index}
        </span>

        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-1.5">
            <span className={cn("text-body font-medium", !open && !answered && "text-muted-foreground")}>
              {title}
            </span>
            {optional ? (
              <span className="rounded bg-muted px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-muted-foreground uppercase">
                {t("common.optional")}
              </span>
            ) : null}
            {hint ? <InfoHint label={title}>{hint}</InfoHint> : null}
          </span>
          {!open ? (
            <span className="mt-0.5 block truncate text-small text-muted-foreground">{summary}</span>
          ) : null}
        </span>

        {!open ? (
          <Pencil className="size-3.5 shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100" />
        ) : null}
      </button>

      {open ? <div className="animate-fade-in space-y-3 px-3 pb-3">{children}</div> : null}
    </section>
  );
}
