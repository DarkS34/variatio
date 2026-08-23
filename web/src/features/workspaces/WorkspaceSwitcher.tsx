import { Check, ChevronDown, FolderPlus, Loader2, Pencil, Shield } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/misc";
import { ROLE_LABELS } from "@/state/auth";
import {
  useCreateWorkspace,
  useRenameWorkspace,
  useSwitchWorkspace,
  useWorkspaces,
} from "@/state/queries";
import type { WorkspaceRow } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Which instance you are in, and how to get to another one.
 *
 * It sits in the header rather than in the account menu because it is not a setting: the
 * whole screen below it — graph, profile, bank, variants — belongs to the workspace this
 * names, and a header that does not say which subject you are editing is how somebody
 * rebuilds the wrong graph.
 */
export function WorkspaceSwitcher() {
  const listing = useWorkspaces();
  const switching = useSwitchWorkspace();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<"create" | "rename" | null>(null);
  const holder = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!holder.current?.contains(event.target as Node)) {
        setOpen(false);
        setEditing(null);
      }
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  const workspaces = listing.data?.workspaces ?? [];
  const active = workspaces.find((w) => w.active) ?? null;
  // Mirrors the server: PATCH is `auth.MANAGE`, and only over the active workspace.
  const canRename = Boolean(active && (active.as_admin || active.role === "owner"));
  const close = () => {
    setEditing(null);
    setOpen(false);
  };
  if (listing.isLoading || workspaces.length === 0) return null;

  return (
    <div className="relative shrink-0" ref={holder}>
      <button
        onClick={() => setOpen((was) => !was)}
        aria-haspopup="menu"
        aria-expanded={open}
        title={active ? `Workspace: ${active.name}` : "Elegir workspace"}
        className={cn(
          "flex max-w-44 items-center gap-1.5 rounded-md border border-border px-2 py-1.5 text-body transition-colors hover:bg-accent",
          open && "bg-accent",
        )}
      >
        {switching.isPending ? (
          <Loader2 className="size-3.5 shrink-0 animate-spin text-muted-foreground" />
        ) : null}
        <span className="truncate font-medium">{active?.name ?? "Sin workspace"}</span>
        <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute left-0 top-10 z-40 w-72 overflow-hidden rounded-lg border border-border bg-card shadow-lg"
        >
          <p className="px-3 pb-1 pt-2.5 text-[11px] font-medium uppercase tracking-wide text-muted-foreground">
            Workspaces
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
                    admin
                  </Badge>
                ) : workspace.role ? (
                  <Badge variant="outline" className="shrink-0">
                    {ROLE_LABELS[workspace.role]}
                  </Badge>
                ) : null}
              </button>
            ))}
          </div>

          <Separator />
          {editing === "create" ? (
            <CreateForm onDone={close} />
          ) : editing === "rename" && active ? (
            <RenameForm workspace={active} onDone={close} />
          ) : (
            <div className="p-1">
              {canRename ? (
                <button
                  role="menuitem"
                  onClick={() => setEditing("rename")}
                  className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-body transition-colors hover:bg-accent"
                >
                  <Pencil className="size-4 text-muted-foreground" />
                  Renombrar «{active!.name}»
                </button>
              ) : null}
              <button
                role="menuitem"
                onClick={() => setEditing("create")}
                className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-body transition-colors hover:bg-accent"
              >
                <FolderPlus className="size-4 text-muted-foreground" />
                Crear un workspace
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
  const create = useCreateWorkspace();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [touched, setTouched] = useState(false);

  const effective = touched ? slug : slugify(name);
  const valid = /^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$/.test(effective) && effective !== "default";

  return (
    <form
      className="space-y-2 p-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (valid) create.mutate({ slug: effective, name: name.trim() || effective }, { onSuccess: onDone });
      }}
    >
      <Input
        autoFocus
        aria-label="Nombre del workspace"
        placeholder="Nombre, p. ej. «Álgebra 2026»"
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      <Input
        aria-label="Identificador del workspace"
        placeholder="identificador"
        value={effective}
        onChange={(event) => {
          setTouched(true);
          setSlug(event.target.value.toLowerCase());
        }}
        className="font-mono text-small"
      />
      {create.isError ? (
        <p className="text-small text-destructive">{(create.error as Error).message}</p>
      ) : (
        <p className="text-[11px] text-muted-foreground">
          Empieza vacío: subes su corpus y sus ejemplares y construyes su propia cadena.
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" size="sm" className="flex-1" disabled={!valid || create.isPending}>
          {create.isPending ? <Loader2 className="size-4 animate-spin" /> : <FolderPlus />}
          Crear
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onDone}>
          Cancelar
        </Button>
      </div>
    </form>
  );
}

/**
 * Only the name changes. The slug stays: it names the directory tree, the `X-Workspace`
 * header and every row that points at the workspace, so renaming it is not a rename but a
 * migration nobody has asked for.
 */
function RenameForm({ workspace, onDone }: { workspace: WorkspaceRow; onDone: () => void }) {
  const rename = useRenameWorkspace();
  const [name, setName] = useState(workspace.name);
  const trimmed = name.trim();
  const valid = trimmed.length > 0 && trimmed.length <= 200 && trimmed !== workspace.name;

  return (
    <form
      className="space-y-2 p-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (valid) rename.mutate({ slug: workspace.slug, name: trimmed }, { onSuccess: onDone });
      }}
    >
      <Input
        autoFocus
        aria-label="Nuevo nombre del workspace"
        placeholder="Nombre"
        value={name}
        onChange={(event) => setName(event.target.value)}
      />
      {rename.isError ? (
        <p className="text-small text-destructive">{(rename.error as Error).message}</p>
      ) : (
        <p className="font-mono text-[11px] text-muted-foreground">
          El identificador «{workspace.slug}» no cambia.
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" size="sm" className="flex-1" disabled={!valid || rename.isPending}>
          {rename.isPending ? <Loader2 className="size-4 animate-spin" /> : <Pencil />}
          Renombrar
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onDone}>
          Cancelar
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
