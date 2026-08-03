import { Brain, ChevronRight } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

/**
 * The answer as it is written, with the model's reasoning one click away.
 *
 * The `<think>` block is genuinely useful but four times longer than the answer; putting
 * it behind a toggle keeps it available without letting it drown the result.
 */
export function TokenStream({
  answer,
  thinking,
  active,
  className,
  height = "16rem",
}: {
  answer: string;
  thinking: string;
  active: boolean;
  className?: string;
  height?: string;
}) {
  const [showThinking, setShowThinking] = useState(false);
  const answerRef = useRef<HTMLPreElement>(null);
  const thinkingRef = useRef<HTMLPreElement>(null);
  const [pinned, setPinned] = useState(true);

  useEffect(() => {
    if (!pinned) return;
    answerRef.current?.scrollTo({ top: answerRef.current.scrollHeight });
    thinkingRef.current?.scrollTo({ top: thinkingRef.current.scrollHeight });
  }, [answer, thinking, pinned]);

  if (!answer && !thinking) {
    return (
      <p className={cn("text-sm text-muted-foreground", className)}>
        {active ? "Esperando la respuesta del modelo…" : "Sin salida del modelo todavía."}
      </p>
    );
  }

  return (
    <div className={cn("space-y-2", className)}>
      {thinking ? (
        <div className="rounded-lg border border-border">
          <button
            type="button"
            onClick={() => setShowThinking((value) => !value)}
            className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
          >
            <ChevronRight className={cn("size-3.5 transition-transform", showThinking && "rotate-90")} />
            <Brain className="size-3.5" />
            Ver razonamiento
            <span className="ml-auto tabular-nums">{thinking.length.toLocaleString("es-ES")} car.</span>
          </button>
          {showThinking ? (
            <pre
              ref={thinkingRef}
              className="thin-scroll max-h-48 overflow-auto border-t border-border p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap text-muted-foreground"
            >
              {thinking}
            </pre>
          ) : null}
        </div>
      ) : null}

      <div className="relative">
        <pre
          ref={answerRef}
          onScroll={(event) => {
            const el = event.currentTarget;
            setPinned(el.scrollHeight - el.scrollTop - el.clientHeight < 40);
          }}
          className="thin-scroll overflow-auto rounded-lg border border-border bg-muted/40 p-3 font-mono text-xs leading-relaxed whitespace-pre-wrap"
          style={{ height }}
        >
          {answer}
          {active ? <span className="ml-0.5 inline-block h-3.5 w-1.5 animate-pulse-soft bg-primary align-middle" /> : null}
        </pre>
        {!pinned ? (
          <Button
            size="sm"
            variant="secondary"
            className="absolute bottom-2 right-2 shadow"
            onClick={() => setPinned(true)}
          >
            Seguir al final
          </Button>
        ) : null}
      </div>
    </div>
  );
}
