import {
  Brain,
  Copy,
  Download,
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
import { ItemFields, download, toMarkdown } from "@/features/run/ResultCard";
import { when } from "@/lib/format";
import { itemTypeOf, typeLabel } from "@/lib/profile";
import type { ExemplarsProfile, GenerationRow } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useSession } from "@/state/auth";
import { useDeleteGeneration, useGenerations, useProfile } from "@/state/queries";

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
 */
export function GenerationsScreen() {
  const session = useSession();
  const profileQuery = useProfile();
  const [scope, setScope] = useState<"mine" | "workspace">("mine");
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState("");
  const [open, setOpen] = useState<number | null>(null);

  const listing = useGenerations({ scope, q: search || undefined, limit: 60 });
  const remove = useDeleteGeneration();

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
          )
        : "",
    [rows, profile],
  );

  if (profileQuery.isLoading) return <Skeleton className="h-96" />;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold tracking-tight">Variantes guardadas</h1>
        <InfoHint label="Qué hay aquí">
          Cada ítem que el generador validó, con el encargo que lo produjo. Se guardan
          solas: no hay nada que pulsar al generar.
        </InfoHint>
        <span className="text-sm tabular-nums text-muted-foreground">{total}</span>

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
            label="Mías"
          />
          <ScopeTab
            active={scope === "workspace"}
            onClick={() => setScope("workspace")}
            icon={<Users className="size-3.5" />}
            label="De todo el workspace"
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
            placeholder="Buscar en el enunciado, el concepto o las instrucciones…"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
          <Button type="submit" variant="outline" size="sm">
            <Search />
            Buscar
          </Button>
        </form>
      </div>

      {listing.isLoading ? (
        <Skeleton className="h-64" />
      ) : rows.length === 0 ? (
        <EmptyState
          icon={<Sparkles className="size-6" />}
          title={search ? "Nada coincide con esa búsqueda" : "Todavía no hay variantes guardadas"}
        >
          {search
            ? "Prueba con otro término, o cambia el ámbito a todo el workspace."
            : "Genera un ítem y quedará aquí, con los conceptos y las instrucciones con que lo pediste."}
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
        "flex items-center gap-1.5 px-3 py-1.5 text-sm transition-colors",
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
  showAuthor,
}: {
  row: GenerationRow;
  profile: ExemplarsProfile | null;
  expanded: boolean;
  onToggle: () => void;
  canDelete: boolean;
  onDelete: () => void;
  showAuthor: boolean;
}) {
  const spec = profile ? itemTypeOf(profile, { item_type: row.item_type }) : null;
  const manyTypes = profile ? Object.keys(profile.item_types).length > 1 : false;
  const primary = spec ? String(row.item[spec.primary_field] ?? "") : "";

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle className="text-sm">
            {row.concepts.length > 0 ? row.concepts.join(" · ") : "Sin conceptos declarados"}
          </CardTitle>
          {manyTypes && profile ? (
            <Badge variant="outline">{typeLabel(profile, row.item_type)}</Badge>
          ) : null}
          {row.think ? (
            <Badge variant="secondary" className="gap-1">
              <Brain className="size-3" />
              razonó
            </Badge>
          ) : null}
          <span className="text-xs text-muted-foreground">
            {when(new Date(row.created_at * 1000).toISOString())}
          </span>
          {showAuthor && row.author.name ? (
            <span className="text-xs text-muted-foreground">· {row.author.name}</span>
          ) : null}

          <div className="ml-auto flex gap-1">
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Copiar JSON"
              onClick={() => navigator.clipboard.writeText(JSON.stringify(row.item, null, 2))}
            >
              <Copy />
            </Button>
            {canDelete ? (
              <Button variant="ghost" size="icon-sm" aria-label="Borrar" onClick={onDelete}>
                <Trash2 />
              </Button>
            ) : null}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-3">
        {expanded ? (
          <ItemFields item={row.item} spec={spec} />
        ) : (
          <p className="line-clamp-3 whitespace-pre-wrap text-sm text-muted-foreground">
            {primary}
          </p>
        )}

        {expanded ? <Commission row={row} /> : null}

        <button
          onClick={onToggle}
          className="text-xs font-medium text-primary underline-offset-4 hover:underline"
        >
          {expanded ? "Ver menos" : "Ver el ítem completo y su encargo"}
        </button>
      </CardContent>
    </Card>
  );
}

/** The parameters the item was asked for with. Without them the statement is unreadable
 *  as evidence: «demasiado fácil» means nothing until you know what curriculum it had. */
function Commission({ row }: { row: GenerationRow }) {
  const entries: [string, string][] = [];
  if (row.curriculum.length > 0) entries.push(["Currículo", row.curriculum.join(" · ")]);
  for (const [field, value] of Object.entries(row.fixed)) {
    entries.push([field, String(value)]);
  }
  if (row.instructions) entries.push(["Instrucciones", row.instructions]);
  if (entries.length === 0) return null;

  return (
    <dl className="grid gap-x-4 gap-y-1 rounded-lg border border-border bg-muted/30 p-3 text-xs sm:grid-cols-[auto_minmax(0,1fr)]">
      {entries.map(([label, value]) => (
        <div key={label} className="contents">
          <dt className="font-medium text-muted-foreground">{label}</dt>
          <dd className="min-w-0 break-words">{value}</dd>
        </div>
      ))}
    </dl>
  );
}
