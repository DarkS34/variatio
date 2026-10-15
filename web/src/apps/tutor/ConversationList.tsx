import { MessageSquarePlus, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { relative } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import { useConversations, useDeleteConversation } from "./queries";

/**
 * One's own conversations in this subject, the most recently active first, and the way to a new
 * one. A row says how long it is and whether a reply is on its way; nothing else, because what
 * a conversation is about is its title, which the model writes once the conversation is about
 * something (until then, its first line). Beside the conversation it is as tall as it, and
 * scrolls inside itself.
 */
export function ConversationList({
  selected,
  onSelect,
}: {
  selected: string | null;
  onSelect: (id: string | null) => void;
}) {
  const { t, plural } = useT();
  const list = useConversations();
  const remove = useDeleteConversation();
  const confirm = useConfirm();

  const drop = async (id: string) => {
    const ok = await confirm({
      title: t("tutor.delete"),
      body: t("tutor.deleteConfirm"),
      confirmLabel: t("tutor.delete"),
      tone: "danger",
    });
    if (!ok) return;
    remove.mutate(id, { onSuccess: () => selected === id && onSelect(null) });
  };

  return (
    // Beside the conversation from `lg` up, as tall as its panel (`PANEL_HEIGHT`, written out
    // because Tailwind only builds the classes it finds whole in the source).
    <aside className="flex flex-col gap-3 lg:h-[max(24rem,calc(100dvh-18rem))]">
      <Button
        className="w-full"
        variant={selected === null ? "default" : "outline"}
        onClick={() => onSelect(null)}
      >
        <MessageSquarePlus />
        {t("tutor.new")}
      </Button>

      {list.isLoading ? <Skeleton className="h-40" /> : null}
      {list.isError ? (
        <LoadError title={t("tutor.list.unreadable")} error={list.error} onRetry={list.refetch} />
      ) : null}
      {list.data && list.data.conversations.length === 0 ? (
        <p className="px-1 text-small text-muted-foreground">{t("tutor.list.empty")}</p>
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
              <span className="line-clamp-2 text-body">{row.title || t("tutor.untitled")}</span>
              {/* One line, never wrapped: a row that waits says only that it waits — its
                  time is now — and a long relative time is cut, never pushed under. */}
              <span className="mt-0.5 flex min-w-0 items-center gap-1.5 whitespace-nowrap text-small text-muted-foreground">
                {row.pending ? (
                  <>
                    <Spinner className="size-3 shrink-0" />
                    <span className="truncate">{t("tutor.list.waiting")}</span>
                  </>
                ) : (
                  <>
                    <span className="shrink-0">{plural("tutor.list.turns", row.turns, { n: row.turns })}</span>
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
              aria-label={t("tutor.delete")}
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
