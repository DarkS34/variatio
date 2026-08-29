import { Check, ChevronDown, FolderPlus, Loader2, Shield } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/misc";
import { LANGUAGES, LANGUAGE_NAMES, useT } from "@/lib/i18n";
import { ROLE_LABEL_KEYS } from "@/state/auth";
import { useCreateWorkspace, useSwitchWorkspace, useWorkspaces } from "@/state/queries";
import { cn } from "@/lib/utils";
import { usePromptLanguage } from "./promptLanguage";

/**
 * Which instance you are in, and how to get to another one.
 *
 * It sits in the header rather than in the account menu because it is not a setting: the
 * whole screen below it — graph, profile, bank, variants — belongs to the workspace this
 * names, and a header that does not say which subject you are editing is how somebody
 * rebuilds the wrong graph.
 */
export function WorkspaceSwitcher() {
  const { t } = useT();
  const listing = useWorkspaces();
  const switching = useSwitchWorkspace();
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const holder = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!holder.current?.contains(event.target as Node)) {
        setOpen(false);
        setCreating(false);
      }
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  const workspaces = listing.data?.workspaces ?? [];
  const active = workspaces.find((w) => w.active) ?? null;
  const close = () => {
    setCreating(false);
    setOpen(false);
  };
  if (listing.isLoading || workspaces.length === 0) return null;

  return (
    <div className="relative shrink-0" ref={holder}>
      <button
        onClick={() => setOpen((was) => !was)}
        aria-haspopup="menu"
        aria-expanded={open}
        title={
          active
            ? t("workspace.switcher.current", { name: active.name })
            : t("workspace.switcher.choose")
        }
        className={cn(
          "flex max-w-44 items-center gap-1.5 rounded-md border border-border px-2 py-1.5 text-body transition-colors hover:bg-accent",
          open && "bg-accent",
        )}
      >
        {switching.isPending ? (
          <Loader2 className="size-3.5 shrink-0 animate-spin text-muted-foreground" />
        ) : null}
        <span className="truncate font-medium">{active?.name ?? t("workspace.none")}</span>
        <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute left-0 top-10 z-40 w-72 overflow-hidden rounded-lg border border-border bg-card shadow-lg"
        >
          <p className="px-3 pb-1 pt-2.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            {t("workspace.switcher.title")}
          </p>
          <div className="max-h-72 overflow-y-auto p-1">
            {workspaces.map((workspace) => (
              <button
                key={workspace.slug}
                role="menuitem"
                disabled={switching.isPending}
                onClick={() => {
                  setOpen(false);
                  if (!workspace.active) switching.mutate(workspace.slug);
                }}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-body transition-colors hover:bg-accent disabled:opacity-60"
              >
                <Check
                  className={cn(
                    "size-3.5 shrink-0",
                    workspace.active ? "text-primary" : "opacity-0",
                  )}
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate">{workspace.name}</span>
                  <span className="block truncate font-mono text-[11px] text-muted-foreground">
                    {workspace.slug}
                  </span>
                </span>
                {workspace.as_admin ? (
                  <Badge variant="secondary" className="shrink-0 gap-1">
                    <Shield className="size-3" />
                    {t("workspace.adminBadge")}
                  </Badge>
                ) : workspace.role ? (
                  <Badge variant="outline" className="shrink-0">
                    {t(ROLE_LABEL_KEYS[workspace.role])}
                  </Badge>
                ) : null}
              </button>
            ))}
          </div>

          <Separator />
          {/* Creating is offered here and renaming is NOT, and there is no owner-facing
              route left for it either: a workspace is named when it is created, and after
              that only an administrator renames it, from «Administración». What the name is
              worth is that everybody means the same instance by it. */}
          {creating ? (
            <CreateForm onDone={close} />
          ) : (
            <div className="p-1">
              <button
                role="menuitem"
                onClick={() => setCreating(true)}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-body transition-colors hover:bg-accent"
              >
                <FolderPlus className="size-4 text-muted-foreground" />
                {t("ws.createOne")}
              </button>
            </div>
          )}
        </div>
      ) : null}
    </div>
  );
}

/**
 * A new workspace is a new instance: empty corpus, empty graph, empty bank.
 *
 * The slug is derived from the name and stays editable, because it is what the paths on
 * disk are named after and what the `X-Workspace` header carries — a value the user will
 * see again in the health panel, so letting them choose it beats inventing one.
 */
function CreateForm({ onDone }: { onDone: () => void }) {
  const { t } = useT();
  const create = useCreateWorkspace();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [touched, setTouched] = useState(false);
  // What the model will be instructed in throughout this instance's whole construction.
  // It defaults to what the person reads because that is the common case, and it is asked
  // HERE because it cannot be asked later: see `api.createWorkspace`.
  const [language, setLanguage] = usePromptLanguage();

  const effective = touched ? slug : slugify(name);
  const valid = /^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$/.test(effective);

  return (
    <form
      className="space-y-2 p-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (valid)
          create.mutate(
            { slug: effective, name: name.trim() || effective, language },
            { onSuccess: onDone },
          );
      }}
    >
      <Input
        autoFocus
        aria-label={t("workspace.name")}
        placeholder={t("workspace.name.placeholder")}
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      <Input
        aria-label={t("workspace.slug")}
        placeholder="identificador"
        value={effective}
        onChange={(event) => {
          setTouched(true);
          setSlug(event.target.value.toLowerCase());
        }}
        className="font-mono text-small"
      />
      <div className="flex flex-col gap-1">
        <span className="text-[11px] text-muted-foreground">{t("workspace.language.title")}</span>
        <div role="group" aria-label={t("workspace.language.title")} className="flex gap-1">
          {LANGUAGES.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setLanguage(option)}
              aria-pressed={language === option}
              className={cn(
                "h-8 flex-1 border text-small font-medium transition-colors",
                language === option
                  ? "border-primary bg-primary text-primary-foreground"
                  : "border-border bg-card hover:bg-accent/60",
              )}
            >
              {LANGUAGE_NAMES[option]}
            </button>
          ))}
        </div>
        <span className="text-[11px] text-muted-foreground">
          {t("workspace.language.onlyAtCreation")}
        </span>
      </div>

      {create.isError ? (
        <p className="text-small text-destructive">{(create.error as Error).message}</p>
      ) : (
        <p className="text-[11px] text-muted-foreground">
          {t("workspace.startsEmpty")}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" size="sm" className="flex-1" disabled={!valid || create.isPending}>
          {create.isPending ? <Loader2 className="size-4 animate-spin" /> : <FolderPlus />}
          {t("common.create")}
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onDone}>
          {t("common.cancel")}
        </Button>
      </div>
    </form>
  );
}

function slugify(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}
