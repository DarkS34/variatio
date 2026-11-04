import { ArrowRight, Lock } from "lucide-react";

import { FunctionMark } from "@/components/ui/function-mark";
import { FUNCTION_TONE } from "@/components/ui/tone";
import { useT, type Key } from "@/lib/i18n";
import { Link } from "@/lib/router";
import { usesFor, type Door } from "@/lib/steps";
import { cn } from "@/lib/utils";
import { useFeatures, useIsStudent } from "@/state/auth";
import { usePipeline } from "@/state/queries";

/** What each function does, in one sentence: the card says it under the name. */
const LEAD_KEYS: Record<Door["key"], Key> = {
  generate: "functions.lead.generate",
  compare: "functions.lead.compare",
  tutor: "functions.lead.tutor",
  chat: "functions.lead.chat",
};

/**
 * «Funciones»: every function open to the account, at full size, where the bar has one pill
 * for them (`lib/steps.doorsGrouped`, more than three).
 *
 * One block per function, in the bar's order, two to a row from `md`: the function's figure,
 * its name, one sentence of what it does and the way in. The whole block is the link, as a
 * door is. While the subject's construction is open every function waits for it, as the
 * bar's doors do: the block is dimmed, no link, and its line says why.
 */
export function FunctionsScreen() {
  const { t } = useT();
  const doors = usesFor(useFeatures());
  const pipeline = usePipeline();
  const student = useIsStudent();
  const open = pipeline.data?.generation_unlocked ?? false;
  const reason = student ? t("nav.subjectNotReady") : t("nav.needsApproved");

  return (
    <div className="space-y-5">
      <header className="space-y-1.5">
        <h1 className="font-display font-expanded text-display">{t("functions.title")}</h1>
        <p className="max-w-[74ch] text-body text-muted-foreground">{t("functions.lead")}</p>
      </header>

      <ul className="grid gap-7 md:grid-cols-2">
        {doors.map((door) => (
          <li key={door.key} className="flex">
            <FunctionCard door={door} open={open} reason={reason} />
          </li>
        ))}
      </ul>
    </div>
  );
}

/** One function as a block: the link to its screen, or, while it waits, why it does. */
function FunctionCard({ door, open, reason }: { door: Door; open: boolean; reason: string }) {
  const { t } = useT();
  const body = (
    <>
      <FunctionMark door={door.key} size="lg" locked={!open} />
      <span className="min-w-0 flex-1 space-y-1">
        <span className={cn("block text-heading", !open && "text-muted-foreground")}>
          {t(door.labelKey)}
        </span>
        <span className="block text-small text-muted-foreground">{t(LEAD_KEYS[door.key])}</span>
        <span
          className={cn(
            "flex items-center gap-1.5 pt-2 text-small font-medium",
            open ? FUNCTION_TONE.face : "text-muted-foreground",
          )}
        >
          {open ? (
            <>
              {t("functions.open")}
              <ArrowRight className="size-4 transition-transform group-hover:translate-x-0.5" />
            </>
          ) : (
            <>
              <Lock className="size-4" />
              {reason}
            </>
          )}
        </span>
      </span>
    </>
  );
  const frame = "surface flex w-full items-start gap-4 p-5";
  if (!open) {
    return (
      <div aria-disabled="true" className={cn(frame, "opacity-70")}>
        {body}
      </div>
    );
  }
  return (
    <Link
      to={door.path}
      className={cn(
        frame,
        "group transition-colors hover:bg-[color-mix(in_oklab,var(--function)_5%,var(--card))]",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
      )}
    >
      {body}
    </Link>
  );
}
