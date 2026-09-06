import {
  Archive,
  Copy,
  Download,
  Library,
  Search,
  Sparkles,
  Trash2,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Input } from "@/components/ui/input";
import { EmptyState, LoadError, Skeleton } from "@/components/ui/misc";
import { fromGeneration, stashDraft } from "@/features/generate/draft";
import { ItemChecks, ItemFields, download, toMarkdown } from "@/features/generate/ResultCard";
import { fieldText } from "@/lib/fields";
import { useRouter } from "@/lib/router";
import { itemTypeOf, typeLabel } from "@/lib/profile";
import type { ExemplarsProfile, GenerationRow } from "@/lib/types";
import {
  useDeleteGeneration,
  useGenerations,
  useProfile,
} from "@/state/queries";
import { useHasWorkspace } from "@/state/auth";
import { useT } from "@/lib/i18n";

/**
 * Everything this account has generated, kept.
 *
 * Every validated item is a row, and the row carries the commission that produced it —
 * concepts, curriculum, fixed fields, instructions, whether the model reasoned — because a
 * statement without its parameters can be read but neither judged nor reproduced.
 *
 * YOURS AND NOBODY ELSE'S: the endpoint answers your own rows and only those, so there is
 * no scope to flip and no author to print on a row.
 *
 * A panel and not a screen: it is a tab of "Mi perfil", which already carries the page's
 * title.
 *
 * With no subject it asks for NOTHING. "Mi perfil" is reachable without belonging to an
 * instance, and the two reads would only answer 403 — with the server's sentence, in
 * Spanish whatever the reader's language. The list is a child component so that its hooks
 * do not run at all in that state.
 */
export function GenerationsPanel() {
  const { t } = useT();
  const hasWorkspace = useHasWorkspace();
  if (!hasWorkspace) {
    return (
      <div className="space-y-5">
        <h2 className="text-heading">{t("generations.title")}</h2>
        <EmptyState icon={<Archive className="size-6" />} title={t("generations.noSubject")}>
          {t("generations.noSubjectHint")}
        </EmptyState>
      </div>
    );
  }
  return <GenerationsList />;
}

function GenerationsList() {
  const { t } = useT();
  const profileQuery = useProfile();
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState<number | null>(null);

  const listing = useGenerations({ q: search || undefined, limit: 60 });
  const remove = useDeleteGeneration();

  const profile = profileQuery.data?.profile ?? null;
  const rows = listing.data?.generations ?? [];
  const total = listing.data?.total ?? 0;

  const asMarkdown = useMemo(
    () =>
      profile
        ? toMarkdown(
            rows.map((row) => ({ item: row.item, item_type: row.item_type })),
            profile,
            t,
          )
        : "",
    [rows, profile, t],
  );

  if (profileQuery.isLoading) return <Skeleton className="h-96" />;
  if (profileQuery.isError)
    return (
      <LoadError
        title={t("generations.unreadable")}
        error={profileQuery.error}
        onRetry={profileQuery.refetch}
      />
    );

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="text-heading">{t("generations.title")}</h2>
        <InfoHint label={t("generations.whatIsHere")}>
          {t("generations.whatIsHere.body")}
        </InfoHint>
        <span className="text-body nums text-muted-foreground">{total}</span>

        {rows.length > 0 && profile ? (
          <div className="ml-auto flex gap-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => download("variantes.md", asMarkdown, "text/markdown")}
            >
              <Download />
              Markdown
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                download(
                  "variantes.json",
                  JSON.stringify(rows.map((r) => r.item), null, 2),
                  "application/json",
                )
              }
            >
              <Download />
              JSON
            </Button>
          </div>
        ) : null}
      </header>

      <div className="flex flex-wrap items-center gap-2">
        <form
          className="flex min-w-56 flex-1 items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            setSearch(query.trim());
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

      {listing.isLoading ? (
        <Skeleton className="h-64" />
      ) : rows.length === 0 ? (
        <EmptyState
          // The same glyph the header's "Mis variantes" pill carries: an empty state is
          // the first thing a new account sees of this screen, and it should be looking at
          // the icon it just pressed. `Sparkles` stays below, where it means GENERATING.
          icon={<Archive className="size-6" />}
          title={search ? t("generations.noMatch") : t("generations.empty")}
        >
          {search ? t("generations.noMatchHint") : t("generations.emptyHint")}
        </EmptyState>
      ) : (
        <div className="space-y-3">
          {rows.map((row) => (
            <GenerationCard
              key={row.id}
              row={row}
              profile={profile}
              expanded={open === row.id}
              onToggle={() => setOpen(open === row.id ? null : row.id)}
              onDelete={() => remove.mutate(row.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function GenerationCard({
  row,
  profile,
  expanded,
  onToggle,
  onDelete,
}: {
  row: GenerationRow;
  profile: ExemplarsProfile | null;
  expanded: boolean;
  onToggle: () => void;
  onDelete: () => void;
}) {
  const { t } = useT();
  const { navigate } = useRouter();
  const spec = profile ? itemTypeOf(profile, { item_type: row.item_type }) : null;
  const manyTypes = profile ? Object.keys(profile.item_types).length > 1 : false;
  const primary = spec ? fieldText(row.item[spec.primary_field]) : "";

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          {/* The modality first, then the concepts: the row answers "¿qué clase de
              ejercicio es, y sobre qué?", which is the order those two are asked in — and
              the modality is one word from a closed list, so a badge after a list of names
              lands at whatever width they happen to end at. Whether the model reasoned,
              which one wrote it and when are in the expanded commission, where somebody
              reproducing the exercise reads them. */}
          {manyTypes && profile ? (
            <Badge variant="outline">{typeLabel(profile, row.item_type, t)}</Badge>
          ) : null}
          <CardTitle className="text-body">
            {row.concepts.length > 0 ? row.concepts.join(" · ") : t("generations.noConcepts")}
          </CardTitle>

          <div className="ml-auto flex gap-1">
            {/* A promoted row keeps saying so: that is data about the bank and not a
                control. Promotion itself has no screen; the endpoint stays. */}
            {row.promoted_item_id ? (
              <Badge variant="secondary" className="gap-1 self-center">
                <Library className="size-3" />
                {t("generations.inBank", { id: row.promoted_item_id })}
              </Badge>
            ) : null}
            <Button
              variant="ghost"
              size="sm"
              title={t("generations.againHint")}
              onClick={() => {
                stashDraft(fromGeneration(row));
                navigate("/generate");
              }}
            >
              <Sparkles />
              {t("generations.moreLikeThis")}
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t("generations.copyJson")}
              onClick={() => navigator.clipboard.writeText(JSON.stringify(row.item, null, 2))}
            >
              <Copy />
            </Button>
            {/* Always offered: every row here is this account's own, and the endpoint
                refuses anybody else's before this screen could draw one. */}
            <Button variant="ghost" size="icon-sm" aria-label={t("generations.delete")} onClick={onDelete}>
              <Trash2 />
            </Button>
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {expanded ? (
          <>
            <ItemFields item={row.item} spec={spec} />
            <ItemChecks checks={row.checks} />
          </>
        ) : (
          <p className="line-clamp-3 whitespace-pre-wrap text-body text-muted-foreground">
            {primary}
          </p>
        )}

        {expanded ? <Commission row={row} /> : null}

        <button
          onClick={onToggle}
          className="text-small font-medium text-primary underline-offset-4 hover:underline"
        >
          {expanded ? t("common.showLess") : t("generations.viewFull")}
        </button>
      </CardContent>
    </Card>
  );
}

/** The parameters the item was asked for with. Without them the statement is unreadable
 *  as evidence: "demasiado fácil" means nothing until you know what curriculum it had. */
function Commission({ row }: { row: GenerationRow }) {
  const { t } = useT();
  const entries: [string, string][] = [];
  if (row.curriculum.length > 0)
    entries.push([t("generations.curriculum"), row.curriculum.join(" · ")]);
  for (const [field, value] of Object.entries(row.fixed)) {
    entries.push([field, String(value)]);
  }
  if (row.instructions) entries.push([t("generations.instructions"), row.instructions]);
  if (entries.length === 0) return null;

  return (
    <dl className="grid gap-x-4 gap-y-1 rounded-lg border border-border bg-muted/30 p-3 text-small sm:grid-cols-[auto_minmax(0,1fr)]">
      {entries.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="font-medium text-muted-foreground">{label}</dt>
          <dd className="min-w-0 break-words">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
