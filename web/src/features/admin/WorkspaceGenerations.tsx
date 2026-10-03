import { Archive, ArrowLeft, Search } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";
import { EmptyState, LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { GenerationCard } from "@/features/generations/GenerationsPanel";
import { useT } from "@/lib/i18n";
import type { AdminWorkspace } from "@/lib/types";
import { useAdminWorkspaceGenerations } from "@/state/queries";

const PAGE = 30;

/**
 * Every exercise generated in one workspace, whoever wrote it, for the administrator.
 *
 * Read-only on purpose: deleting an exercise or generating more like it stays with its
 * author, on "Mi perfil". The rows are drawn with the workspace's own profile, which the
 * endpoint sends, because the administrator need not be a member of it.
 */
export function WorkspaceGenerations({
  workspace,
  onBack,
}: {
  workspace: AdminWorkspace;
  onBack: () => void;
}) {
  const { t } = useT();
  const [author, setAuthor] = useState("");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [open, setOpen] = useState<string | null>(null);

  const listing = useAdminWorkspaceGenerations(workspace.slug, {
    author: author ? Number(author) : undefined,
    q: search || undefined,
    limit: PAGE,
    offset,
  });
  const rows = listing.data?.generations ?? [];
  const total = listing.data?.total ?? 0;
  const profile = listing.data?.profile ?? null;
  const filtered = Boolean(author || search);

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <Button variant="ghost" size="sm" onClick={onBack}>
          <ArrowLeft />
          {t("wsgen.back")}
        </Button>
        <div className="flex flex-wrap items-baseline gap-2">
          <h2 className="text-heading">{t("wsgen.title", { name: workspace.name })}</h2>
          <span className="text-body nums text-muted-foreground">{total}</span>
        </div>
        <p className="text-small text-muted-foreground">{t("wsgen.readOnly")}</p>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="wsgen-author">{t("wsgen.author")}</Label>
          <Select
            id="wsgen-author"
            value={author}
            className="w-56"
            onChange={(event) => {
              setAuthor(event.target.value);
              setOffset(0);
            }}
          >
            <option value="">{t("wsgen.allAuthors")}</option>
            {(listing.data?.authors ?? []).map((account) => (
              <option key={account.id} value={account.id}>
                {account.username}
              </option>
            ))}
          </Select>
        </div>
        <form
          className="flex min-w-56 flex-1 items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            setSearch(query.trim());
            setOffset(0);
          }}
        >
          <Input
            aria-label={t("generations.search")}
            placeholder={t("generations.search.placeholder")}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <Button type="submit" variant="outline" size="sm">
            <Search />
            {t("common.search")}
          </Button>
        </form>
      </div>

      {listing.isError ? (
        <LoadError
          title={t("wsgen.unreadable")}
          error={listing.error}
          onRetry={() => listing.refetch()}
        />
      ) : listing.isLoading ? (
        <Skeleton className="h-64" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<Archive className="size-6" />}
          title={filtered ? t("generations.noMatch") : t("generations.empty")}
        />
      ) : (
        <div className="space-y-3">
          {rows.map((row) => (
            <GenerationCard
              key={row.id}
              row={row}
              profile={profile}
              expanded={open === row.id}
              onToggle={() => setOpen(open === row.id ? null : row.id)}
              showAuthor
            />
          ))}
          {total > PAGE ? (
            <div className="flex flex-wrap items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0 || listing.isFetching}
                onClick={() => setOffset(Math.max(0, offset - PAGE))}
              >
                {t("wsgen.previous")}
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={offset + PAGE >= total || listing.isFetching}
                onClick={() => setOffset(offset + PAGE)}
              >
                {t("wsgen.next")}
              </Button>
              <span className="text-small nums text-muted-foreground">
                {t("wsgen.range", {
                  from: offset + 1,
                  to: Math.min(offset + PAGE, total),
                  total,
                })}
              </span>
              {listing.isFetching ? <Spinner /> : null}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
