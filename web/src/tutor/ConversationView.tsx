import { ArrowUp, BookOpen, RotateCcw, Square } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";

import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { Alert, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { when } from "@/lib/format";
import { useT, type Key } from "@/lib/i18n";

import type { TutorDraft } from "./draft";
import { NotesReader } from "./NotesReader";
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

// The panel is one fixed height, so a long conversation scrolls inside it instead of
// pushing the box to write in below the fold: the window less what sits above it (the bar,
// the title and the tabs, about 18rem), never under 24rem. Shared with the list beside it.
export const PANEL_HEIGHT = "h-[max(24rem,calc(100dvh-18rem))]";

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
  draft,
  onOpened,
}: {
  id: string | null;
  ready: boolean;
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
  const [reading, setReading] = useState<Place | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  const data = conversation.data;
  const pending = data?.pending ?? null;
  const turns = data?.turns ?? [];
  // The panel's own scroll, never the page's: the newest turn is at its foot.
  useEffect(() => {
    const node = scroller.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [turns.length, pending?.status]);

  const sending = open.isPending || send.isPending;
  const error = open.error ?? send.error ?? retry.error;
  const canSend = ready && !sending && !pending && message.trim().length > 0;

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

  if (id !== null && conversation.isLoading) return <Skeleton className={PANEL_HEIGHT} />;
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
    <section className={`flex flex-col rounded-lg border border-border bg-card ${PANEL_HEIGHT}`}>
      <div ref={scroller} className="thin-scroll min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        {id === null ? <Welcome fromExercise={Boolean(draft?.generationId)} /> : null}
        {data ? <Opened conversation={data} /> : null}
        {turns.map((turn, index) => (
          <TurnBubble key={`${index}-${turn.at}`} turn={turn} onRead={setReading} />
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
      </div>

      <div className="space-y-2 border-t border-border p-3">
        {error ? (
          <Alert tone="danger" title={t("tutor.sendFailed")}>
            <p>{error.message}</p>
          </Alert>
        ) : null}
        <Composer
          value={message}
          onChange={setMessage}
          onSubmit={submit}
          disabled={!ready}
          canSend={canSend}
          sending={sending}
        />
      </div>
      <NotesReader place={reading} onClose={() => setReading(null)} />
    </section>
  );
}

// The box grows with what is written up to this height, then scrolls inside itself.
const COMPOSER_MAX_PX = 192;

/**
 * The box to write in, with its send button inside it on the right.
 *
 * Enter sends and Shift+Enter breaks the line, as in every chat. A key pressed while an input
 * method is composing a character belongs to that character, so it never sends.
 */
function Composer({
  value,
  onChange,
  onSubmit,
  disabled,
  canSend,
  sending,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled: boolean;
  canSend: boolean;
  sending: boolean;
}) {
  const { t } = useT();
  const box = useRef<HTMLTextAreaElement>(null);

  useLayoutEffect(() => {
    const node = box.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, COMPOSER_MAX_PX)}px`;
  }, [value]);

  const onKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== "Enter" || event.shiftKey || event.nativeEvent.isComposing) return;
    event.preventDefault();
    onSubmit();
  };

  return (
    <div className="flex items-end gap-2 rounded-lg border border-input bg-background p-1.5 transition-colors focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1 focus-within:ring-offset-background">
      <textarea
        ref={box}
        aria-label={t("tutor.composer.label")}
        rows={1}
        value={value}
        placeholder={t("tutor.composer.placeholder")}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={onKey}
        disabled={disabled}
        className="thin-scroll min-h-9 flex-1 resize-none overflow-y-auto bg-transparent px-2 py-1.5 text-body leading-relaxed placeholder:text-muted-foreground focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50"
      />
      <Button
        variant="attention"
        size="icon"
        className="shrink-0"
        aria-label={t("tutor.composer.send")}
        title={t("tutor.composer.send")}
        disabled={!canSend}
        onClick={onSubmit}
      >
        {sending ? <Spinner className="size-4" /> : <ArrowUp />}
      </Button>
    </div>
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

function TurnBubble({ turn, onRead }: { turn: Turn; onRead: (place: Place) => void }) {
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
        <References places={turn.references} onRead={onRead} />
      ) : null}
      <p className="text-micro text-muted-foreground">
        {t("tutor.tutor")} · {when(turn.at)}
      </p>
    </div>
  );
}

/**
 * Where in the notes to look, each place opening the reader at it. The places are the card's,
 * never the model's, chosen by which ones the reply names.
 */
function References({ places, onRead }: { places: Place[]; onRead: (place: Place) => void }) {
  const { t } = useT();
  return (
    <div className="flex flex-wrap items-center gap-1.5 text-small text-muted-foreground">
      <BookOpen className="size-3.5" aria-hidden />
      <span>{t("tutor.references")}</span>
      {places.map((place) => {
        const label = lastPart(place.location) || place.document;
        return (
          <button
            key={`${place.document}|${place.location}`}
            type="button"
            onClick={() => onRead(place)}
            title={t("tutor.notes.open", { place: place.location || place.document })}
            className="max-w-full truncate rounded-full border border-border px-2 py-0.5 text-foreground underline-offset-2 transition-colors hover:bg-accent hover:underline"
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}

/** The section a heading path ends in, which is what a reply names. */
function lastPart(location: string): string {
  const parts = location.split(" > ");
  return parts[parts.length - 1] ?? "";
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
