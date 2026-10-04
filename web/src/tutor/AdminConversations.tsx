import "./i18n";

import { ArrowLeft, MessagesSquare } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label, Select } from "@/components/ui/input";
import { EmptyState, LoadError, Skeleton } from "@/components/ui/misc";
import { when } from "@/lib/format";
import { useT, type Key } from "@/lib/i18n";
import type { AdminWorkspace } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ConceptMap } from "./ConceptMap";
import { useAdminConversation, useAdminConversations } from "./queries";
import { Reply } from "./Reply";

const PAGE = 30;

const KIND_KEYS: Record<string, Key> = {
  theory: "tutor.kind.theory",
  exercise: "tutor.kind.exercise",
  attempt: "tutor.kind.attempt",
  solution: "tutor.kind.solution",
  social: "tutor.kind.social",
  administrative: "tutor.kind.administrative",
  off_topic: "tutor.kind.off_topic",
  blocked: "tutor.kind.blocked",
};

/**
 * Every conversation held with the tutor in one workspace, whoever held it, for the
 * administrator: the one reader besides the author, read-only, as with the generated
 * exercises. Each reply shows what kind of message it answered, which is what a person
 * reviewing how the tutor behaves wants to see first.
 */
export function AdminConversations({
  workspace,
  onBack,
}: {
  workspace: AdminWorkspace;
  onBack: () => void;
}) {
  const { t, plural } = useT();
  const [author, setAuthor] = useState("");
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState<{ author: number; id: string } | null>(null);
  const listing = useAdminConversations(workspace.slug, author ? Number(author) : null, offset);
  const rows = listing.data?.conversations ?? [];
  const total = listing.data?.total ?? 0;

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft />
          {t("wsgen.back")}
        </Button>
        <div className="flex flex-wrap items-baseline gap-2">
          <h2 className="text-heading">{t("tutor.admin.title", { name: workspace.name })}</h2>
          <span className="text-body nums text-muted-foreground">{total}</span>
        </div>
        <p className="text-small text-muted-foreground">{t("tutor.admin.readOnly")}</p>
      </div>

      {(listing.data?.authors.length ?? 0) > 1 ? (
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="tutor-admin-author">{t("wsgen.author")}</Label>
          <Select
            id="tutor-admin-author"
            className="w-64"
            value={author}
            onChange={(event) => {
              setAuthor(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">{t("wsgen.allAuthors")}</option>
            {listing.data?.authors.map((a) => (
              <option key={a.id} value={String(a.id)}>
                {a.name || a.username || `#${a.id}`}
              </option>
            ))}
          </Select>
        </div>
      ) : null}

      {listing.isLoading ? <Skeleton className="h-64" /> : null}
      {listing.isError ? (
        <LoadError title={t("tutor.admin.unreadable")} error={listing.error} onRetry={listing.refetch} />
      ) : null}
      {listing.data && rows.length === 0 ? (
        <EmptyState icon={<MessagesSquare />} title={t("tutor.admin.empty")} />
      ) : null}

      <ul className="space-y-2">
        {rows.map((row) => {
          const isOpen = open?.id === row.id && open.author === row.author.id;
          return (
            <li key={`${row.author.id}-${row.id}`} className="rounded-lg border border-border">
              <button
                type="button"
                className={cn("w-full px-4 py-3 text-left hover:bg-accent", isOpen && "bg-accent")}
                onClick={() => setOpen(isOpen ? null : { author: row.author.id, id: row.id })}
                aria-expanded={isOpen}
              >
                <span className="block font-medium">{row.title || t("tutor.untitled")}</span>
                <span className="text-small text-muted-foreground">
                  {row.author.username ?? t("generations.byNobody")} ·{" "}
                  {plural("tutor.list.turns", row.turns, { n: row.turns })} ·{" "}
                  {row.updated_at ? when(row.updated_at) : "—"}
                </span>
              </button>
              {isOpen ? <Transcript slug={workspace.slug} author={row.author.id} id={row.id} /> : null}
            </li>
          );
        })}
      </ul>

      {total > PAGE ? (
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
            {t("wsgen.previous")}
          </Button>
          <span className="text-small text-muted-foreground">
            {t("wsgen.range", { from: offset + 1, to: Math.min(total, offset + PAGE), total })}
          </span>
          <Button variant="outline" size="sm" disabled={offset + PAGE >= total} onClick={() => setOffset(offset + PAGE)}>
            {t("wsgen.next")}
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function Transcript({ slug, author, id }: { slug: string; author: number; id: string }) {
  const { t } = useT();
  const conversation = useAdminConversation(slug, author, id);
  if (conversation.isLoading) return <Skeleton className="m-4 h-32" />;
  if (!conversation.data) {
    return <LoadError title={t("tutor.unreadable")} error={conversation.error} onRetry={conversation.refetch} />;
  }
  return (
    <div className="space-y-3 border-t border-border p-4">
      {conversation.data.turns.map((turn, index) => (
        <div key={index} className="space-y-1">
          <p className="flex flex-wrap items-center gap-2 text-micro text-muted-foreground">
            {turn.role === "student" ? t("tutor.student") : t("tutor.tutor")} · {when(turn.at)}
            {turn.role === "tutor" && turn.kind ? (
              <Badge variant="outline">{t(KIND_KEYS[turn.kind] ?? "tutor.kind.theory")}</Badge>
            ) : null}
            {turn.role === "tutor" && turn.fallback ? (
              <Badge variant="attention">{t("tutor.admin.fallback")}</Badge>
            ) : null}
          </p>
          {turn.role === "tutor" ? (
            <>
              <Reply text={turn.text} />
              <ConceptMap map={turn.concept_map} />
            </>
          ) : (
            <p className="whitespace-pre-wrap">{turn.text}</p>
          )}
        </div>
      ))}
    </div>
  );
}
