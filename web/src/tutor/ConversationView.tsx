import { BookOpen, RotateCcw, Send, Square } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/input";
import { Alert, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { when } from "@/lib/format";
import { useT, type Key } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import type { TutorDraft } from "./draft";
import {
  useCancelTurn,
  useConversation,
  useOpenConversation,
  useRetryTurn,
  useSendMessage,
} from "./queries";
import type { Conversation, Pending, Place, Turn } from "./types";

const FAILED_KEYS: Record<string, Key> = {
  failed: "tutor.failed.failed",
  cancelled: "tutor.failed.cancelled",
  interrupted: "tutor.failed.interrupted",
};

/**
 * One conversation: the turns, the reply on its way, and the box to write the next message.
 *
 * With no conversation chosen it is the start of a new one, which the first message creates.
 * A reply arrives WHOLE, never token by token: the server checks it against the method before
 * anybody reads it, and a stream would show the very text a check may withdraw.
 */
export function ConversationView({
  id,
  ready,
  maxChars,
  draft,
  onOpened,
}: {
  id: string | null;
  ready: boolean;
  maxChars: number;
  draft: TutorDraft | null;
  onOpened: (id: string) => void;
}) {
  const { t } = useT();
  const conversation = useConversation(id);
  const open = useOpenConversation();
  const send = useSendMessage(id);
  const retry = useRetryTurn(id);
  const cancel = useCancelTurn(id);
  const [message, setMessage] = useState(draft?.message ?? "");
  const end = useRef<HTMLDivElement>(null);

  const data = conversation.data;
  const pending = data?.pending ?? null;
  const turns = data?.turns ?? [];
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [turns.length, pending?.status]);

  const sending = open.isPending || send.isPending;
  const error = open.error ?? send.error ?? retry.error;
  const tooLong = message.trim().length > maxChars;
  const canSend = ready && !sending && !pending && message.trim().length > 0 && !tooLong;

  const submit = () => {
    if (!canSend) return;
    const text = message.trim();
    const done = { onSuccess: () => setMessage("") };
    if (id === null) {
      open.mutate(
        { message: text, generationId: draft?.generationId ?? null },
        { onSuccess: (queued) => onOpened(queued.conversation.id) },
      );
    } else {
      send.mutate(text, done);
    }
  };

  const onKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      submit();
    }
  };

  if (id !== null && conversation.isLoading) return <Skeleton className="h-96" />;
  if (id !== null && !data) {
    return (
      <LoadError
        title={t("tutor.unreadable")}
        error={conversation.error}
        onRetry={conversation.refetch}
      />
    );
  }

  const last = turns[turns.length - 1];
  const unanswered = last?.role === "student" && last.failed ? last.failed : null;

  return (
    <section className="flex min-h-[32rem] flex-col rounded-lg border border-border bg-card">
      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {id === null ? <Welcome fromExercise={Boolean(draft?.generationId)} /> : null}
        {data ? <Opened conversation={data} /> : null}
        {turns.map((turn, index) => (
          <TurnBubble key={`${index}-${turn.at}`} turn={turn} />
        ))}
        {pending ? <OnItsWay pending={pending} onStop={() => cancel.mutate()} /> : null}
        {unanswered ? (
          <div className="flex flex-wrap items-center gap-2 text-small text-muted-foreground">
            <span>{t(FAILED_KEYS[unanswered] ?? "tutor.failed.failed")}</span>
            <Button
              variant="outline"
              size="sm"
              disabled={!ready || retry.isPending}
              onClick={() => retry.mutate()}
            >
              <RotateCcw />
              {t("tutor.retry")}
            </Button>
          </div>
        ) : null}
        <div ref={end} />
      </div>

      <div className="space-y-2 border-t border-border p-3">
        {error ? (
          <Alert tone="danger" title={t("tutor.sendFailed")}>
            <p>{error.message}</p>
          </Alert>
        ) : null}
        <Textarea
          aria-label={t("tutor.composer.label")}
          autoGrow
          rows={3}
          value={message}
          placeholder={t("tutor.composer.placeholder")}
          onChange={(event) => setMessage(event.target.value)}
          onKeyDown={onKey}
          disabled={!ready}
          className="max-h-64"
        />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className={cn("text-small", tooLong ? "text-destructive" : "text-muted-foreground")}>
            {t("tutor.composer.count", { n: message.trim().length, max: maxChars })} ·{" "}
            {t("tutor.composer.hint")}
          </span>
          <Button variant="attention" disabled={!canSend} onClick={submit}>
            {sending ? <Spinner className="size-4" /> : <Send />}
            {t("tutor.composer.send")}
          </Button>
        </div>
      </div>
    </section>
  );
}

function Welcome({ fromExercise }: { fromExercise: boolean }) {
  const { t } = useT();
  return (
    <div className="mx-auto max-w-prose space-y-2 py-6 text-center">
      <p className="font-display font-expanded text-title">{t("tutor.start.title")}</p>
      <p className="text-muted-foreground">
        {fromExercise ? t("tutor.start.fromExercise") : t("tutor.start.body")}
      </p>
    </div>
  );
}

function Opened({ conversation }: { conversation: Conversation }) {
  const { t } = useT();
  if (conversation.opened_from?.kind !== "generation") return null;
  return <p className="text-small text-muted-foreground">{t("tutor.openedFrom")}</p>;
}

function TurnBubble({ turn }: { turn: Turn }) {
  const { t } = useT();
  if (turn.role === "student") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] space-y-1">
          <div className="whitespace-pre-wrap break-words rounded-lg bg-accent px-3 py-2 text-body">
            {turn.text}
          </div>
          <p className="text-right text-micro text-muted-foreground">
            {t("tutor.you")} · {when(turn.at)}
          </p>
        </div>
      </div>
    );
  }
  return (
    <div className="max-w-[92%] space-y-1.5">
      <div className="rounded-lg border border-border bg-background px-3 py-2">
        <Markdown>{turn.text}</Markdown>
      </div>
      {turn.references && turn.references.length > 0 ? (
        <References places={turn.references} />
      ) : null}
      <p className="text-micro text-muted-foreground">
        {t("tutor.tutor")} · {when(turn.at)}
      </p>
    </div>
  );
}

/** Where in the notes the reply's material came from: the card's places, never the model's. */
function References({ places }: { places: Place[] }) {
  const { t } = useT();
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-small text-muted-foreground">
      <BookOpen className="size-3.5" aria-hidden />
      <span>{t("tutor.references")}</span>
      {places.map((place) => (
        <span
          key={`${place.document}|${place.location}`}
          title={place.document}
          className="max-w-full truncate rounded-full border border-border px-2 py-0.5"
        >
          {place.location || place.document}
        </span>
      ))}
    </div>
  );
}

function OnItsWay({ pending, onStop }: { pending: Pending; onStop: () => void }) {
  const { t } = useT();
  const queued = pending.status === "queued";
  return (
    <div className="flex flex-wrap items-center gap-2 text-small text-muted-foreground">
      <Spinner className="size-4" />
      <span>
        {queued
          ? pending.queue_position > 1
            ? t("tutor.pending.queuedAhead", { n: pending.queue_position - 1 })
            : t("tutor.pending.queued")
          : t("tutor.pending.running")}
      </span>
      <Button variant="ghost" size="sm" onClick={onStop}>
        <Square />
        {t("tutor.pending.stop")}
      </Button>
    </div>
  );
}
