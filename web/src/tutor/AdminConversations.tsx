import "./i18n";

import { ArrowLeft } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Label, Select } from "@/components/ui/input";
import { LoadError, Skeleton } from "@/components/ui/misc";
import { SectionHeader } from "@/features/admin/Sections";
import { when } from "@/lib/format";
import { useT, type Key } from "@/lib/i18n";
import type { AdminWorkspace } from "@/lib/types";
import { cn } from "@/lib/utils";

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
    <div className="space-y-7">
      <div className="space-y-3">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft />
          {t("wsgen.back")}
        </Button>
        <SectionHeader
          title={
            <>
              {t("tutor.admin.title", { name: workspace.name })}{" "}
              <span className="nums text-body text-muted-foreground">{total}</span>
            </>
          }
          description={t("tutor.admin.readOnly")}
        />
      </div>

      {/* One block, its conversations ruled rows as every list (2026-10-07: a frame per row,
          on the ground, was the panel's one list drawn that way). What a row opens — the
          conversation — is held in a well under it. */}
      <section className="surface space-y-4 p-5">
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
          <p className="text-small text-muted-foreground">{t("tutor.admin.empty")}</p>
        ) : null}

        {rows.length > 0 ? (
          <ul className="rows rows-flush">
            {rows.map((row) => {
              const isOpen = open?.id === row.id && open.author === row.author.id;
              return (
                <li key={`${row.author.id}-${row.id}`}>
                  <button
                    type="button"
                    className={cn(
                      "-mx-3 block w-[calc(100%+1.5rem)] rounded-inner px-3 py-2.5 text-left transition-colors",
                      isOpen ? "bg-sunk" : "hover:bg-accent",
                    )}
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
                  {isOpen ? (
                    <div className="well mb-2 mt-1">
                      <Transcript slug={workspace.slug} author={row.author.id} id={row.id} />
                    </div>
                  ) : null}
                </li>
              );
            })}
          </ul>
        ) : null}
      </section>

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
    <div className="space-y-3 p-4">
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
            <Reply text={turn.text} map={turn.concept_map} />
          ) : (
            <p className="whitespace-pre-wrap">{turn.text}</p>
          )}
        </div>
      ))}
    </div>
  );
}
