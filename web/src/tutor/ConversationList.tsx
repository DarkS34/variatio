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
 * a conversation is about is its first line, which is its title.
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
    <aside className="space-y-3">
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

      <ul className="space-y-1">
        {(list.data?.conversations ?? []).map((row) => (
          <li key={row.id} className="group flex items-start gap-1">
            <button
              type="button"
              onClick={() => onSelect(row.id)}
              aria-current={selected === row.id ? "true" : undefined}
              className={cn(
                "min-w-0 flex-1 rounded-md px-2.5 py-2 text-left transition-colors hover:bg-accent",
                selected === row.id && "bg-accent",
              )}
            >
              <span className="line-clamp-2 text-body">{row.title || t("tutor.untitled")}</span>
              <span className="mt-0.5 flex items-center gap-1.5 text-small text-muted-foreground">
                {row.pending ? <Spinner className="size-3" /> : null}
                {row.pending
                  ? t("tutor.list.waiting")
                  : plural("tutor.list.turns", row.turns, { n: row.turns })}
                {row.updated_at ? <span aria-hidden>·</span> : null}
                {row.updated_at ? relative(row.updated_at) : null}
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
