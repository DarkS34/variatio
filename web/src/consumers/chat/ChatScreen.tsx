import { ArrowUp, MessageSquarePlus, RotateCcw, Square, Trash2 } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";

import { Markdown } from "@/components/Markdown";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Alert } from "@/components/ui/alert";
import { LoadError } from "@/components/ui/load-error";
import { Skeleton } from "@/components/ui/skeleton";
import { Spinner } from "@/components/ui/spinner";
import { ApiError } from "@/lib/api";
import { takeChatDraft, type ChatDraft } from "@/lib/chatDraft";
import { relative, when } from "@/lib/format";
import { useT, type Key } from "@/lib/i18n";
import { waitInWords } from "@/lib/limit";
import { cn } from "@/lib/utils";
import { useEngineOffline } from "@/state/queries";

import {
  useCancelChat,
  useChatConversation,
  useChatConversations,
  useDeleteChat,
  useOpenChat,
  useRetryChat,
  useSendChat,
} from "./queries";
import type { ChatConversation, ChatPending, ChatTurn } from "./types";

/** What the server puts in `X-Error-Code` when the chat's messages of the day are spent. */
const DAILY_LIMIT = "chat_daily_limit";

const FAILED_KEYS: Record<string, Key> = {
  failed: "chat.failed.failed",
  cancelled: "chat.failed.cancelled",
  interrupted: "chat.failed.interrupted",
};

// One fixed height, as the tutor's panel: the window less what sits above it, never under 24rem.
const PANEL_HEIGHT = "h-[max(24rem,calc(100dvh-18rem))]";

// The box grows with what is written up to this height, then scrolls inside itself.
const COMPOSER_MAX_PX = 192;

/**
 * THE FREE CHAT (the user's decision, 2026-10-14): an assistant that explains, solves and
 * writes code, as the student asks, within the subject.
 *
 * The tutor's screen without the tutor's method: the conversations beside the one open, the
 * turns in the same two materials — the student's message a block of ink on the right, the
 * reply open text on the left — and the box to write in. No concept map, no question set
 * apart, no concept to choose. A reply arrives whole, polled from the author's own route.
 */
export function ChatScreen() {
  const { t } = useT();
  const offline = useEngineOffline();
  const [selected, setSelected] = useState<string | null>(null);
  // Taken once, on the first render: a draft handed over by «Llevar al chat libre».
  const [draft, setDraft] = useState<ChatDraft | null>(() => takeChatDraft());

  return (
    <div className="space-y-5">
      <header className="space-y-1.5">
        <h1 className="font-display font-expanded text-display">{t("nav.chat")}</h1>
        <p className="max-w-[74ch] text-body text-muted-foreground">{t("chat.lead")}</p>
      </header>

      {offline ? (
        <Alert tone="attention" title={t("generate.noEngine")}>
          <p>{t("generate.noEngineBody", { reason: t(offline) })}</p>
        </Alert>
      ) : null}

      <div className="grid gap-7 lg:grid-cols-[18rem_minmax(0,1fr)]">
        <ChatList
          selected={selected}
          onSelect={(id) => {
            setDraft(null);
            setSelected(id);
          }}
        />
        <ChatView
          key={selected ?? "new"}
          id={selected}
          ready={!offline}
          draft={selected === null ? draft : null}
          onOpened={(id) => {
            setDraft(null);
            setSelected(id);
          }}
        />
      </div>
    </div>
  );
}

/** One's own conversations in this subject, the most recently active first, and a new one. */
function ChatList({ selected, onSelect }: { selected: string | null; onSelect: (id: string | null) => void }) {
  const { t, plural } = useT();
  const list = useChatConversations();
  const remove = useDeleteChat();
  const confirm = useConfirm();

  const drop = async (id: string) => {
    const ok = await confirm({
      title: t("chat.delete"),
      body: t("chat.deleteConfirm"),
      confirmLabel: t("chat.delete"),
      tone: "danger",
    });
    if (!ok) return;
    remove.mutate(id, { onSuccess: () => selected === id && onSelect(null) });
  };

  return (
    <aside className="flex flex-col gap-3 lg:h-[max(24rem,calc(100dvh-18rem))]">
      <Button className="w-full" variant={selected === null ? "default" : "outline"} onClick={() => onSelect(null)}>
        <MessageSquarePlus />
        {t("chat.new")}
      </Button>

      {list.isLoading ? <Skeleton className="h-40" /> : null}
      {list.isError ? (
        <LoadError title={t("chat.list.unreadable")} error={list.error} onRetry={list.refetch} />
      ) : null}
      {list.data && list.data.conversations.length === 0 ? (
        <p className="px-1 text-small text-muted-foreground">{t("chat.list.empty")}</p>
      ) : null}

      <ul className="thin-scroll min-h-0 flex-1 space-y-1 overflow-y-auto">
        {(list.data?.conversations ?? []).map((row) => (
          <li key={row.id} className="group flex items-start gap-1">
            <button
              type="button"
              onClick={() => onSelect(row.id)}
              aria-current={selected === row.id ? "true" : undefined}
              className={cn(
                "min-w-0 flex-1 rounded-lg px-3 py-2 text-left transition-colors hover:bg-accent",
                selected === row.id && "bg-accent",
              )}
            >
              <span className="line-clamp-2 text-body">{row.title || t("chat.untitled")}</span>
              <span className="mt-0.5 flex min-w-0 items-center gap-1.5 whitespace-nowrap text-small text-muted-foreground">
                {row.pending ? (
                  <>
                    <Spinner className="size-3 shrink-0" />
                    <span className="truncate">{t("chat.list.waiting")}</span>
                  </>
                ) : (
                  <>
                    <span className="shrink-0">{plural("chat.list.turns", row.turns, { n: row.turns })}</span>
                    {row.updated_at ? <span aria-hidden>·</span> : null}
                    {row.updated_at ? <span className="truncate">{relative(row.updated_at)}</span> : null}
                  </>
                )}
              </span>
            </button>
            <Button
              variant="ghost"
              size="icon-sm"
              className="mt-1.5 opacity-60 group-hover:opacity-100"
              aria-label={t("chat.delete")}
              onClick={() => void drop(row.id)}
            >
              <Trash2 />
            </Button>
          </li>
        ))}
      </ul>
    </aside>
  );
}

/** One conversation: the turns, the reply on its way, and the box to write the next message. */
function ChatView({
  id,
  ready,
  draft,
  onOpened,
}: {
  id: string | null;
  ready: boolean;
  draft: ChatDraft | null;
  onOpened: (id: string) => void;
}) {
  const { t } = useT();
  const conversation = useChatConversation(id);
  const open = useOpenChat();
  const send = useSendChat(id);
  const retry = useRetryChat(id);
  const cancel = useCancelChat(id);
  const [message, setMessage] = useState(draft?.message ?? "");
  const scroller = useRef<HTMLDivElement>(null);

  const data = conversation.data;
  const pending = data?.pending ?? null;
  const turns = data?.turns ?? [];
  // The panel's own scroll, to the START of the newest turn: a long reply is read from its
  // first line.
  useEffect(() => {
    const node = scroller.current;
    if (!node) return;
    const shown = node.querySelectorAll<HTMLElement>("[data-turn]");
    const last = shown[shown.length - 1];
    node.scrollTop = last
      ? last.getBoundingClientRect().top - node.getBoundingClientRect().top + node.scrollTop - 16
      : node.scrollHeight;
  }, [turns.length, pending?.status]);

  const sending = open.isPending || send.isPending;
  const error = open.error ?? send.error ?? retry.error;
  const canSend = ready && !sending && !pending && message.trim().length > 0;
  const clearError = () => {
    open.reset();
    send.reset();
    retry.reset();
  };

  const submit = () => {
    if (!canSend) return;
    const text = message.trim();
    clearError();
    if (id === null) {
      open.mutate(
        { message: text, generationId: draft?.generationId ?? null, bankId: draft?.bankId ?? null },
        { onSuccess: (queued) => onOpened(queued.conversation.id) },
      );
    } else {
      send.mutate(text, { onSuccess: () => setMessage("") });
    }
  };

  if (id !== null && conversation.isLoading) return <Skeleton className={PANEL_HEIGHT} />;
  if (id !== null && !data) {
    return <LoadError title={t("chat.unreadable")} error={conversation.error} onRetry={conversation.refetch} />;
  }

  const last = turns[turns.length - 1];
  const unanswered = last?.role === "student" && last.failed ? last.failed : null;

  return (
    <section className={`surface flex min-w-0 flex-col overflow-hidden ${PANEL_HEIGHT}`}>
      <div ref={scroller} className="thin-scroll min-h-0 flex-1 space-y-6 overflow-y-auto p-5 sm:px-6">
        {id === null ? <Welcome fromExercise={Boolean(draft?.generationId || draft?.bankId)} /> : null}
        {data ? <Opened conversation={data} /> : null}
        {turns.map((turn, index) => (
          <TurnBlock key={`${index}-${turn.at}`} turn={turn} />
        ))}
        {pending ? <Waiting pending={pending} onStop={() => cancel.mutate()} /> : null}
        {unanswered ? (
          <div className="flex flex-wrap items-center gap-2 text-small text-muted-foreground">
            <span>{t(FAILED_KEYS[unanswered] ?? "chat.failed.failed")}</span>
            <Button
              variant="outline"
              size="sm"
              disabled={!ready || retry.isPending}
              onClick={() => {
                clearError();
                retry.mutate();
              }}
            >
              <RotateCcw />
              {t("chat.retry")}
            </Button>
          </div>
        ) : null}
      </div>

      <div className="space-y-2 px-5 pb-5 pt-3">
        {error ? <SendError error={error} /> : null}
        <Composer value={message} onChange={setMessage} onSubmit={submit} disabled={!ready} canSend={canSend} sending={sending} />
      </div>
    </section>
  );
}

/** The empty conversation: what the chat is, or that the exercise is already in the box. */
function Welcome({ fromExercise }: { fromExercise: boolean }) {
  const { t } = useT();
  return (
    <div className="mx-auto max-w-2xl space-y-2 py-4">
      <p className="text-title font-semibold">{t("chat.start.title")}</p>
      <p className="max-w-prose text-muted-foreground">
        {fromExercise ? t("chat.start.fromExercise") : t("chat.start.body")}
      </p>
    </div>
  );
}

/** One line over a conversation opened on an exercise, saying which kind. */
function Opened({ conversation }: { conversation: ChatConversation }) {
  const { t } = useT();
  const kind = conversation.opened_from?.kind;
  if (kind !== "generation" && kind !== "bank") return null;
  return (
    <p className="text-small text-muted-foreground">
      {t(kind === "bank" ? "chat.openedFromBank" : "chat.openedFromGeneration")}
    </p>
  );
}

// Who is speaking, written over every turn: the name in ink, the rest quiet.
const SPEAKER = "text-micro font-condensed uppercase text-muted-foreground";

/** One turn, in the tutor's two materials: the student's ink on the right, the reply open text. */
function TurnBlock({ turn }: { turn: ChatTurn }) {
  const { t } = useT();
  if (turn.role === "student") {
    return (
      <div data-turn className="flex flex-col items-end gap-1.5">
        <p className={`${SPEAKER} text-right`}>
          <span className="font-semibold text-foreground">{t("chat.you")}</span> · {when(turn.at)}
        </p>
        <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-[18px_18px_6px_18px] bg-ink px-4.5 py-3.5 text-body text-ink-foreground shadow-drop">
          {turn.text}
        </div>
      </div>
    );
  }
  return (
    <div data-turn className="space-y-3">
      <p className={SPEAKER}>
        <span className="font-semibold text-foreground">{t("nav.chat")}</span> · {when(turn.at)}
      </p>
      <Markdown className="max-w-[72ch]">{turn.text}</Markdown>
    </div>
  );
}

/** The reply on its way: queued, or being written, and the way to stop it. */
function Waiting({ pending, onStop }: { pending: ChatPending; onStop: () => void }) {
  const { t } = useT();
  const queued = pending.status === "queued";
  return (
    <div role="status" className="flex flex-wrap items-center gap-x-4 gap-y-2 py-1">
      {queued ? <span aria-hidden className="size-3 border-[1.5px] border-input" /> : <Spinner className="size-4" />}
      <div className="min-w-0 flex-1 basis-56 space-y-0.5">
        <p className="font-medium">{t(queued ? "chat.pending.queued" : "chat.pending.running")}</p>
        <p className="max-w-prose text-small text-muted-foreground">
          {queued
            ? pending.queue_position > 1
              ? t("chat.pending.queuedAhead", { n: pending.queue_position - 1 })
              : t("chat.pending.queuedNext")
            : t("chat.pending.runningWhy")}
        </p>
      </div>
      <Button variant="ghost" size="sm" onClick={onStop}>
        <Square />
        {t("chat.pending.stop")}
      </Button>
    </div>
  );
}

/** Why a message did not go: the day's limit said alone, anything else under «No se pudo enviar». */
function SendError({ error }: { error: Error }) {
  const tr = useT();
  const { t } = tr;
  if (error instanceof ApiError && error.code === DAILY_LIMIT) {
    const sentence =
      error.retryAfter == null ? error.message : t("chat.limit.reached", { wait: waitInWords(error.retryAfter, tr) });
    return <Alert tone="info" title={sentence} />;
  }
  return (
    <Alert tone="danger" title={t("chat.sendFailed")}>
      <p>{error.message}</p>
    </Alert>
  );
}

/** The box to write in: Enter sends, Shift+Enter breaks the line, as in every chat. */
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
    if (event.nativeEvent.isComposing) return;
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="well flex items-end gap-2 p-1.5 transition-colors focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1 focus-within:ring-offset-background">
      <textarea
        ref={box}
        aria-label={t("chat.composer.label")}
        rows={1}
        value={value}
        placeholder={t("chat.composer.placeholder")}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={onKey}
        disabled={disabled}
        // The frame draws the focus once (`focus-within` above).
        style={{ outline: "none" }}
        className="thin-scroll min-h-9 flex-1 resize-none overflow-y-auto bg-transparent px-2 py-1.5 text-body leading-relaxed placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
      />
      <Button
        variant="attention"
        size="icon"
        className="shrink-0"
        aria-label={t("chat.composer.send")}
        title={t("chat.composer.send")}
        disabled={!canSend}
        onClick={onSubmit}
      >
        {sending ? <Spinner className="size-4" /> : <ArrowUp />}
      </Button>
    </div>
  );
}
