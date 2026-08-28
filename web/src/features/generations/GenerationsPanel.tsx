import {
  Archive,
  BookPlus,
  Brain,
  Copy,
  Download,
  Library,
  Search,
  Sparkles,
  Trash2,
  User,
  Users,
} from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Input } from "@/components/ui/input";
import { EmptyState, Skeleton } from "@/components/ui/misc";
import { fromGeneration, stashDraft } from "@/features/run/draft";
import { ItemChecks, ItemFields, download, toMarkdown } from "@/features/run/ResultCard";
import { fieldText } from "@/lib/fields";
import { when } from "@/lib/format";
import { useRouter } from "@/lib/router";
import { itemTypeOf, typeLabel } from "@/lib/profile";
import type { ExemplarsProfile, GenerationRow } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useCanEdit, useSession } from "@/state/auth";
import {
  useDeleteGeneration,
  useGenerations,
  useProfile,
  usePromoteGeneration,
} from "@/state/queries";
import { useT } from "@/lib/i18n";

/**
 * Everything this workspace has generated, kept.
 *
 * Until phase 3 a variant lived exactly as long as the tab that produced it: reload and a
 * minute of GPU was gone. Every validated item is now a row, and the row carries the
 * commission that produced it — concepts, currículo, campos fijados, instrucciones y si el
 * modelo razonó — because a statement without its parameters can be read but not judged
 * and not reproduced.
 *
 * Two scopes, and «mías» is the default: someone looking for the exercise they wrote
 * yesterday means their own, and a shared subject is the other question, not the same one.
 *
 * A panel and not a screen: it is a tab of «Mi perfil», which already carries the page's
 * title, so this one heads its own section and does not claim to be the page.
 */
export function GenerationsPanel() {
  const { t } = useT();
  const session = useSession();
  const profileQuery = useProfile();
  const [scope, setScope] = useState<"mine" | "workspace">("mine");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState<number | null>(null);

  const listing = useGenerations({ scope, q: search || undefined, limit: 60 });
  const remove = useDeleteGeneration();
  const promote = usePromoteGeneration();
  const canEdit = useCanEdit();

  const profile = profileQuery.data?.profile ?? null;
  const rows = listing.data?.generations ?? [];
  const total = listing.data?.total ?? 0;
  const isOwner = session.data?.role === "owner";
  const me = session.data?.user.id ?? null;

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

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center gap-2">
        <h2 className="text-heading">Variantes guardadas</h2>
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
        <div className="inline-flex overflow-hidden rounded-md border border-border">
          <ScopeTab
            active={scope === "mine"}
            onClick={() => setScope("mine")}
            icon={<User className="size-3.5" />}
            label={t("generations.mine")}
          />
          <ScopeTab
            active={scope === "workspace"}
            onClick={() => setScope("workspace")}
            icon={<Users className="size-3.5" />}
            label={t("generations.wholeWorkspace")}
          />
        </div>

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
          // The same glyph the header's «Mis variantes» pill carries: an empty state is
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
              canDelete={isOwner || row.author.id === me}
              onDelete={() => remove.mutate(row.id)}
              canPromote={canEdit}
              promoting={promote.isPending && promote.variables === row.id}
              onPromote={() => promote.mutate(row.id)}
              showAuthor={scope === "workspace"}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function ScopeTab({
  active,
  onClick,
  icon,
  label,
}: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
}) {
  return (
    <button
      onClick={onClick}
      className={cn(
        "flex items-center gap-1.5 px-3 py-1.5 text-body transition-colors",
        active ? "bg-accent font-medium text-accent-foreground" : "text-muted-foreground hover:text-foreground",
      )}
    >
      {icon}
      {label}
    </button>
  );
}

function GenerationCard({
  row,
  profile,
  expanded,
  onToggle,
  canDelete,
  onDelete,
  canPromote,
  promoting,
  onPromote,
  showAuthor,
}: {
  row: GenerationRow;
  profile: ExemplarsProfile | null;
  expanded: boolean;
  onToggle: () => void;
  canDelete: boolean;
  onDelete: () => void;
  canPromote: boolean;
  promoting: boolean;
  onPromote: () => void;
  showAuthor: boolean;
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
          <CardTitle className="text-body">
            {row.concepts.length > 0 ? row.concepts.join(" · ") : t("generations.noConcepts")}
          </CardTitle>
          {manyTypes && profile ? (
            <Badge variant="outline">{typeLabel(profile, row.item_type, t)}</Badge>
          ) : null}
          {row.think ? (
            <Badge variant="secondary" className="gap-1">
              <Brain className="size-3" />
              {t("generations.reasoned")}
            </Badge>
          ) : null}
          <span className="text-small text-muted-foreground">
            {when(new Date(row.created_at * 1000).toISOString())}
          </span>
          {showAuthor && row.author.name ? (
            <span className="text-small text-muted-foreground">· {row.author.name}</span>
          ) : null}

          <div className="ml-auto flex gap-1">
            {row.promoted_item_id ? (
              <Badge variant="secondary" className="gap-1 self-center">
                <Library className="size-3" />
                {t("generations.inBank", { id: row.promoted_item_id })}
              </Badge>
            ) : canPromote ? (
              <Button
                variant="ghost"
                size="sm"
                disabled={promoting}
                title={t("generations.promoteHint")}
                onClick={onPromote}
              >
                <BookPlus />
                {promoting ? t("generations.promoting") : t("generations.promote")}
              </Button>
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
            {canDelete ? (
              <Button variant="ghost" size="icon-sm" aria-label={t("generations.delete")} onClick={onDelete}>
                <Trash2 />
              </Button>
            ) : null}
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
 *  as evidence: «demasiado fácil» means nothing until you know what curriculum it had. */
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
