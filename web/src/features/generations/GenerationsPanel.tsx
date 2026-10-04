import { Archive, Copy, Download, Library, MessagesSquare, Search, Sparkles, Trash2 } from "lucide-react";
import { useMemo, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { EmptyState, LoadError, Skeleton } from "@/components/ui/misc";
import type { FormState } from "@/features/generate/commission";
import { fromGeneration, stashDraft } from "@/features/generate/draft";
import { stashTutorDraft } from "@/lib/tutorDraft";
import { ItemChecks, ItemFields, download, toMarkdown } from "@/features/generate/ResultCard";
import { fieldText } from "@/lib/fields";
import { useRouter } from "@/lib/router";
import { itemTypeOf, typeLabel } from "@/lib/profile";
import type { ExemplarsProfile, GenerationRow } from "@/lib/types";
import {
  useDeleteGeneration,
  useGenerations,
  useProfile,
  useSwitchWorkspace,
} from "@/state/queries";
import { useFeatures } from "@/state/auth";
import { useT } from "@/lib/i18n";

/** How many of the newest exercises the list draws before a search is needed. */
const PAGE = 60;

/**
 * How many exercises this account has in `slug`, or undefined while that is not known.
 *
 * Read off a page of ONE row of the list's own endpoint: the count is on screen at every
 * visit and refreshed at every saved item, and a full page each time moved sixty rows
 * nobody had asked to see. It shares the `["generations"]` key, so whatever refreshes the
 * list refreshes it. The placeholder a key change keeps is another subject's total, never
 * this one.
 */
export function useExerciseTotal(slug: string | null): number | undefined {
  const listing = useGenerations({ limit: 1 }, slug);
  return listing.isPlaceholderData ? undefined : listing.data?.total;
}

/**
 * Everything this account has generated in one subject, kept.
 *
 * Every validated item is saved, with the commission that produced it — concepts,
 * curriculum, fixed fields, instructions, whether the model reasoned — because a statement
 * without its parameters can be read but neither judged nor reproduced.
 *
 * YOURS AND NOBODY ELSE'S: the endpoint answers your own rows and only those, so there is
 * no scope to flip and no author to print on a row.
 *
 * It unfolds under its subject on "Mis asignaturas y ejercicios", and it is the «Mis
 * ejercicios» tab of "Generar" for the subject in use; both name the subject already, so it
 * carries no title. Every read carries `slug` as its own `X-Workspace`: the list is read
 * where it lives, without switching the tab into that subject. «Generar más como este» does
 * switch, because "Generar" works on the subject in use.
 */
export function SubjectExercises({
  slug,
  inUse,
  onGenerateMore,
}: {
  slug: string;
  inUse: boolean;
  /** Takes the commission of «Generar más como este» on the screen that holds the form,
   *  instead of stashing it and opening "Generar"; read only for the subject in use. `null`
   *  is that screen busy with a batch of its own: the rows offer no «Generar más como
   *  este» then, as the screen offers no other way to a new commission until it ends. */
  onGenerateMore?: ((form: FormState) => void) | null;
}) {
  const { t } = useT();
  const { navigate } = useRouter();
  const tutorOpen = useFeatures().tutor;
  const profileQuery = useProfile(slug);
  const switching = useSwitchWorkspace();
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState<string | null>(null);

  const listing = useGenerations({ q: search || undefined, limit: PAGE }, slug);
  const remove = useDeleteGeneration(slug);

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

  // Both actions work on the subject in use, so from another subject they switch into it
  // first. `mutateAsync` and not `mutate`'s callbacks: switching drops the listing this list
  // is drawn from, so the list unmounts before the switch answers, and a mutation forgets
  // the per-call callbacks of an unmounted caller.
  const goTo = (path: string, stash: () => void) => {
    if (inUse) {
      stash();
      navigate(path);
      return;
    }
    void switching
      .mutateAsync(slug)
      .then(() => {
        stash();
        navigate(path);
      })
      .catch(() => undefined);
  };
  const again = (row: GenerationRow) => {
    const draft = fromGeneration(row);
    if (onGenerateMore && inUse) {
      onGenerateMore(draft);
      return;
    }
    goTo("/generate", () => stashDraft(draft));
  };
  // The statement goes into the tutor's box and the exercise is named, so the conversation
  // starts on the concepts the exercise practises.
  const withTutor = (row: GenerationRow) => {
    const spec = profile ? itemTypeOf(profile, { item_type: row.item_type }) : null;
    const statement = spec ? fieldText(row.item[spec.primary_field]) : "";
    goTo("/tutor", () =>
      stashTutorDraft({ message: t("tutor.fromExercise.message", { statement }), generationId: row.id }),
    );
  };

  if (profileQuery.isLoading) return <Skeleton className="h-40" />;
  if (profileQuery.isError)
    return (
      <LoadError
        title={t("generations.unreadable")}
        error={profileQuery.error}
        onRetry={profileQuery.refetch}
      />
    );

  // Nothing generated here yet: one line under the fold, not a search box over nothing.
  if (!listing.isLoading && !listing.isError && total === 0 && !search)
    return (
      <p className="text-small text-muted-foreground">
        {t("generations.empty")}. {t("generations.emptyHint")}
      </p>
    );

  return (
    <div className="space-y-3">
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

        {rows.length > 0 && profile ? (
          <div className="flex gap-1">
            <Button
              variant="outline"
              size="sm"
              onClick={() => download(`${slug}-ejercicios.md`, asMarkdown, "text/markdown")}
            >
              <Download />
              Markdown
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() =>
                download(
                  `${slug}-ejercicios.json`,
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
      </div>

      {listing.isError ? (
        <LoadError
          title={t("generations.unreadable")}
          error={listing.error}
          onRetry={() => listing.refetch()}
        />
      ) : listing.isLoading ? (
        <Skeleton className="h-40" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<Archive className="size-6" />}
          title={t("generations.noMatch")}
        >
          {t("generations.noMatchHint")}
        </EmptyState>
      ) : (
        <div className="space-y-3">
          {total > rows.length ? (
            <p className="text-small text-muted-foreground">
              {t("generations.newest", { shown: rows.length, total })}
            </p>
          ) : null}
          {rows.map((row) => (
            <GenerationCard
              key={row.id}
              row={row}
              profile={profile}
              expanded={open === row.id}
              onToggle={() => setOpen(open === row.id ? null : row.id)}
              onAgain={
                switching.isPending || onGenerateMore === null ? undefined : () => again(row)
              }
              // Only for an account the tutor is open to: for anybody else there is no
              // conversation to land in.
              onTutor={switching.isPending || !tutorOpen ? undefined : () => withTutor(row)}
              onDelete={() => remove.mutate(row.id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/**
 * One saved exercise, folded to its statement.
 *
 * `onAgain` and `onDelete` absent is the administrator's read-only view: no «Generar más
 * como este» and no delete, which stay the author's. `showAuthor` names who wrote it, which
 * only that view needs.
 */
export function GenerationCard({
  row,
  profile,
  expanded,
  onToggle,
  onAgain,
  onTutor,
  onDelete,
  showAuthor = false,
}: {
  row: GenerationRow;
  profile: ExemplarsProfile | null;
  expanded: boolean;
  onToggle: () => void;
  onAgain?: () => void;
  /** Opens a conversation with the tutor on this exercise; absent on the read-only view. */
  onTutor?: () => void;
  onDelete?: () => void;
  showAuthor?: boolean;
}) {
  const { t } = useT();
  const spec = profile ? itemTypeOf(profile, { item_type: row.item_type }) : null;
  const manyTypes = profile ? Object.keys(profile.item_types).length > 1 : false;
  const primary = spec ? fieldText(row.item[spec.primary_field]) : "";
  // What it practises: the targets that ran, which an older API does not send, and the
  // concepts asked for otherwise — empty when the bank chose them and nobody recorded which.
  const concepts = row.targets?.length ? row.targets : row.concepts;

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          {/* The modality first, then the concepts: the row answers "¿qué clase de
              exercise is it, and about what?", which is the order those two are asked in — and
              the modality is one word from a closed list, so a badge after a list of names
              lands at whatever width they happen to end at. Whether the model reasoned,
              which one wrote it and when are in the expanded commission, where somebody
              reproducing the exercise reads them. */}
          {manyTypes && profile ? (
            <Badge variant="outline">{typeLabel(profile, row.item_type, t)}</Badge>
          ) : null}
          <CardTitle className="text-body">
            {concepts.length > 0 ? concepts.join(" · ") : t("generations.noConcepts")}
          </CardTitle>
          {showAuthor ? (
            <span className="text-small text-muted-foreground">
              {row.author.username
                ? t("generations.by", { username: row.author.username })
                : t("generations.byNobody")}
            </span>
          ) : null}

          {/* Wraps inside too: on a phone the controls alone are wider than the card. */}
          <div className="ml-auto flex flex-wrap justify-end gap-1">
            {/* A promoted row keeps saying so: that is data about the bank and not a
                control. Promotion itself has no screen; the endpoint stays. */}
            {row.promoted_item_id ? (
              <Badge variant="secondary" className="gap-1 self-center">
                <Library className="size-3" />
                {t("generations.inBank", { id: row.promoted_item_id })}
              </Badge>
            ) : null}
            {onAgain ? (
              <Button
                variant="ghost"
                size="sm"
                title={t("generations.againHint")}
                onClick={onAgain}
              >
                <Sparkles />
                {t("generations.moreLikeThis")}
              </Button>
            ) : null}
            {onTutor ? (
              <Button variant="tutor" size="sm" title={t("tutor.fromExercise.hint")} onClick={onTutor}>
                <MessagesSquare />
                {t("tutor.fromExercise")}
              </Button>
            ) : null}
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label={t("generations.copyJson")}
              onClick={() => navigator.clipboard.writeText(JSON.stringify(row.item, null, 2))}
            >
              <Copy />
            </Button>
            {/* Offered on every row of the author's own list: each is this account's own, and the
                endpoint refuses anybody else's before this screen could draw one. */}
            {onDelete ? (
              <Button
                variant="ghost"
                size="icon-sm"
                aria-label={t("generations.delete")}
                onClick={onDelete}
              >
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
