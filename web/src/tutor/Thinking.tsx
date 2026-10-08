import { Square } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";

import { QuestionMark } from "./QuestionMark";
import type { Pending } from "./types";

/**
 * THE REPLY ON ITS WAY: A QUESTION BEING WRITTEN.
 *
 * What the student waits for is a question — the tutor answers with one every time — so the
 * sign of waiting is the tutor's own mark (`QuestionMark`) being written square by square,
 * and unwritten again while the reply is not there.
 *
 * Beside it, one line says what is happening and one says why it takes a moment and arrives
 * whole: a reply is checked against the method before anybody reads it. Nothing here claims
 * a step the screen does not know — a turn's job tells the workspace's stream no detail —
 * so the text is the same from start to end.
 *
 * A queued reply is not a running one: its mark is hollow and still.
 */
export function Thinking({ pending, onStop }: { pending: Pending; onStop: () => void }) {
  const { t } = useT();
  const queued = pending.status === "queued";
  return (
    <div role="status" className="flex flex-wrap items-center gap-x-4 gap-y-2 py-1">
      <QuestionMark tone={queued ? "queued" : "writing"} />
      <div className="min-w-0 flex-1 basis-56 space-y-0.5">
        <p className="font-medium">{t(queued ? "tutor.pending.queued" : "tutor.pending.running")}</p>
        <p className="max-w-prose text-small text-muted-foreground">
          {queued
            ? pending.queue_position > 1
              ? t("tutor.pending.queuedAhead", { n: pending.queue_position - 1 })
              : t("tutor.pending.queuedNext")
            : t("tutor.pending.runningWhy")}
        </p>
      </div>
      <Button variant="ghost" size="sm" onClick={onStop}>
        <Square />
        {t("tutor.pending.stop")}
      </Button>
    </div>
  );
}
