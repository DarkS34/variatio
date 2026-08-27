import { Brain, ChevronRight, CornerDownLeft } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { StreamPhase } from "@/state/runStore";
import { useT } from "@/lib/i18n";

/** Follows the tail of a growing pane until the reader scrolls away from it. */
function useAutoScroll<T extends HTMLElement>(content: string, enabled = true) {
  const ref = useRef<T>(null);
  const [pinned, setPinned] = useState(true);

  useEffect(() => {
    if (!pinned || !enabled) return;
    ref.current?.scrollTo({ top: ref.current.scrollHeight });
  }, [content, pinned, enabled]);

  const onScroll = () => {
    const el = ref.current;
    if (el) setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 40);
  };

  return { ref, pinned, setPinned, onScroll };
}

/**
 * The answer as it is written, with the reasoning that led to it.
 *
 * Reasoning is four times longer than the answer, so it does not get the same room:
 * it opens by itself while the model is thinking — the only moment it is the whole
 * story — and folds away as soon as the answer starts. Clicking pins that choice
 * until the next item.
 *
 * The raw answer pane lives only while the model is writing. Once the run ends the same
 * text is on screen twice, once as tokens and once as the parsed item, and the parsed
 * one is strictly better; what survives here is the reasoning, which the result cards
 * only carry per item.
 */
export function TokenStream({
  answer,
  thinking,
  phase = "idle",
  active,
  className,
  height = "16rem",
}: {
  answer: string;
  thinking: string;
  phase?: StreamPhase;
  active: boolean;
  className?: string;
  height?: string;
}) {
  const { t } = useT();
  const [override, setOverride] = useState<boolean | null>(null);
  const thinkingLive = active && phase === "thinking";
  const showThinking = override ?? thinkingLive;

  const answerPane = useAutoScroll<HTMLPreElement>(answer);
  const thinkingPane = useAutoScroll<HTMLPreElement>(thinking, showThinking);

  // Each item restarts the panes; so does the reader's choice about the reasoning.
  useEffect(() => {
    if (!thinking) setOverride(null);
  }, [thinking]);

  if (!active && !thinking) return null;

  if (active && !answer && !thinking) {
    return (
      <p className={cn("flex items-center gap-2 text-body text-muted-foreground", className)}>
        <span className="size-1.5 animate-pulse-soft rounded-full bg-primary" />
        {t("token.waiting")}
      </p>
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      {thinking ? (
        <div className="overflow-hidden rounded-lg border border-border">
          <button
            type="button"
            onClick={() => setOverride(!showThinking)}
            aria-expanded={showThinking}
            className={cn(
              "flex w-full items-center gap-2 px-3 py-2 text-left text-small font-medium transition-colors",
              thinkingLive ? "text-foreground" : "text-muted-foreground hover:text-foreground",
            )}
          >
            <ChevronRight className={cn("size-3.5 transition-transform", showThinking && "rotate-90")} />
            <Brain className={cn("size-3.5", thinkingLive && "animate-pulse-soft")} />
            {t("stream.reasoning")}
            {thinkingLive ? (
              <span className="text-muted-foreground">{t("stream.inProgress")}</span>
            ) : null}
            <span className="ml-auto nums text-muted-foreground">
              {thinking.length.toLocaleString("es-ES")}
            </span>
          </button>
          {showThinking ? (
            <pre
              ref={thinkingPane.ref}
              onScroll={thinkingPane.onScroll}
              className="thin-scroll max-h-48 overflow-auto border-t border-border bg-muted/30 p-3 font-mono text-small leading-relaxed whitespace-pre-wrap text-muted-foreground"
            >
              {thinking}
              {thinkingLive ? <Caret /> : null}
            </pre>
          ) : null}
        </div>
      ) : null}

      {active ? (
        <div className="relative">
          <pre
            ref={answerPane.ref}
            onScroll={answerPane.onScroll}
            className="thin-scroll overflow-auto rounded-lg border border-border bg-muted/40 p-3 font-mono text-small leading-relaxed whitespace-pre-wrap"
            style={{ height }}
          >
            {answer || (
              <span className="text-muted-foreground italic">
                {thinkingLive ? t("stream.stillReasoning") : t("stream.noAnswer")}
              </span>
            )}
            {phase === "answering" ? <Caret /> : null}
          </pre>
          {!answerPane.pinned ? (
            <Button
              size="sm"
              variant="secondary"
              className="absolute bottom-2 right-2 shadow"
              onClick={() => answerPane.setPinned(true)}
            >
              <CornerDownLeft />
              {t("token.toEnd")}
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function Caret() {
  return <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse-soft bg-primary align-middle" />;
}
