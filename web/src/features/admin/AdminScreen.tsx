import {
  Check,
  ChevronRight,
  Copy,
  Link as LinkIcon,
  ShieldCheck,
  Trash2,
  UserCheck,
  UserX,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label, Select } from "@/components/ui/input";
import { EmptyState, Skeleton, Spinner } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { ARTIFACT_STATUS, when } from "@/lib/format";
import type {
  AdminAccount,
  AdminOverview,
  AdminWorkspace,
  Role,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { ROLE_HINTS, ROLE_LABELS, useSession } from "@/state/auth";
import {
  useAdminDeleteWorkspace,
  useAdminInvites,
  useAdminOverview,
  useCreateInvite,
  useDeleteAccount,
  useDeleteArtifact,
  useMembershipActions,
  useRevokeInvite,
  useSetAccountEnabled,
} from "@/state/queries";

import { StudyTab } from "@/study/AdminStudyTab";
import { useAdminEvaluations } from "@/study/queries";

import { StatTile } from "./charts";
import { ConfigTab } from "./ConfigTab";

const ROLES: Role[] = ["viewer", "editor", "owner"];

export function AdminScreen() {
  const session = useSession();
  const [tab, setTab] = useState("estudio");
  const [workspace, setWorkspace] = useState<string | null>(null);
  const [account, setAccount] = useState<number | null>(null);

  const overview = useAdminOverview();
  const study = useAdminEvaluations({ workspace, account });

  if (!session.data?.user.is_admin) {
    return (
      <EmptyState icon={<ShieldCheck className="size-6" />} title="Solo para administración">
        Esta pantalla es del administrador de la instalación. Tu cuenta no lo es.
      </EmptyState>
    );
  }

  if (overview.isLoading) return <Skeleton className="h-96" />;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="font-display font-expanded text-display">Administración</h1>
        <InfoHint label="Qué es esto">
          La instalación entera vista desde fuera: quién la usa, quién puede entrar y en
          qué, cuántos workspaces hay y cómo va el estudio de evaluación. Es la única
          pantalla que cruza cuentas, y el único sitio desde el que se dan accesos.
        </InfoHint>
      </header>

      {overview.data ? <Totals overview={overview.data} /> : null}

      <Tabs
        items={[
          { value: "estudio", label: "Evaluaciones" },
          { value: "cuentas", label: "Cuentas y accesos" },
          { value: "workspaces", label: "Workspaces" },
          { value: "config", label: "Configuración" },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "estudio" ? (
        <StudyTab
          data={study.data}
          loading={study.isLoading}
          workspace={workspace}
          account={account}
          onWorkspace={setWorkspace}
          onAccount={setAccount}
        />
      ) : null}

      {tab === "cuentas" && overview.data ? (
        <AccountsTab
          overview={overview.data}
          onInspect={(id) => {
            setAccount(id);
            setTab("estudio");
          }}
        />
      ) : null}

      {tab === "workspaces" && overview.data ? (
        <WorkspacesTab overview={overview.data} />
      ) : null}

      {tab === "config" ? <ConfigTab /> : null}
    </div>
  );
}

/* Headline ---------------------------------------------------------------------------- */

function Totals({ overview }: { overview: NonNullable<ReturnType<typeof useAdminOverview>["data"]> }) {
  const { totals, engine } = overview;
  return (
    <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-5">
      <StatTile label="Cuentas" value={totals.users} />
      <StatTile label="Workspaces" value={totals.workspaces} />
      <StatTile label="Variantes generadas" value={totals.generations.toLocaleString("es-ES")} />
      <StatTile
        label="Comparaciones"
        value={totals.evaluations}
        hint={`${totals.decided} con elección registrada`}
      />
      <StatTile
        label="Motor"
        value={engine.busy ? "ocupado" : "libre"}
        tone={engine.busy ? "accent" : "plain"}
        hint={
          engine.busy
            ? `${engine.job?.label ?? "trabajo"} · ${engine.queued} en cola`
            : `${engine.warm_contexts.length} contexto(s) caliente(s)`
        }
      />
    </div>
  );
}

/* Accounts and workspaces --------------------------------------------------------------- */

/**
 * The one screen that decides who exists and who gets in.
 *
 * It used to be two: an owner's «Personas e invitaciones» dialog, which handed out access
 * to one workspace, and this table, which listed the same accounts and could only switch
 * them off. Two places to answer one question is how the two answers drift apart, so the
 * dialog is gone and this is the whole of it — issuing invitations, moving people between
 * workspaces and disabling an account, in that order, which is the order they happen in.
 *
 * Access is per workspace and this panel crosses them all, so a row's memberships open
 * where the row is rather than obliging the administrator to change workspace to grant one.
 */
function AccountsTab({
  overview,
  onInspect,
}: {
  overview: AdminOverview;
  onInspect: (id: number) => void;
}) {
  const toggle = useSetAccountEnabled();
  const remove = useDeleteAccount();
  const session = useSession();
  const toast = useToast();
  const [open, setOpen] = useState<number | null>(null);

  // Irreversible, so it is spelled out before it happens — and what it spells out is the
  // half people get wrong: the account goes, the material it produced does not.
  const confirmDelete = (account: AdminAccount) => {
    const kept = [
      account.generations ? `${account.generations} variante(s) guardada(s)` : "",
      account.evaluations ? `${account.evaluations} comparación(es)` : "",
    ].filter(Boolean);
    const message =
      `¿Eliminar la cuenta «${account.username}» por completo?\n\n` +
      "Pierde sus accesos y sus sesiones abiertas, y el usuario queda libre para otra " +
      "cuenta.\n" +
      (kept.length
        ? `Lo que generó se queda pero sin autor: ${kept.join(" y ")}.\n`
        : "") +
      "\nNo se puede deshacer. Para cerrarle la puerta sin borrar nada, desactívala.";
    if (!window.confirm(message)) return;
    // The dialog is the confirmation BEFORE; this is the one after. Everything on this
    // screen that destroys something says so once it is done, because the row simply
    // disappearing is indistinguishable from a list that reloaded.
    remove.mutate(account.id, {
      onSuccess: () =>
        toast({ title: "Cuenta eliminada", description: account.username, tone: "attention" }),
      onError: (error: Error) =>
        toast({ title: "No se ha podido eliminar", description: error.message, tone: "danger" }),
    });
  };

  return (
    <div className="space-y-5">
      <InviteSection overview={overview} />

      <section className="space-y-2">
        <h2 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
          Cuentas ({overview.accounts.length})
        </h2>
        <div className="overflow-hidden rounded-lg border border-border">
          <Table minWidth="52rem">
            <THead>
              <TR>
                <TH>Cuenta</TH>
                <TH>Accesos</TH>
                <TH align="num">Variantes</TH>
                <TH align="num">Comparaciones</TH>
                <TH>Alta</TH>
                <TH />
              </TR>
            </THead>
            <TBody>
              {overview.accounts.map((account) => (
                <AccountRows
                  key={account.id}
                  account={account}
                  overview={overview}
                  self={account.id === session.data?.user.id}
                  expanded={open === account.id}
                  onToggle={() => setOpen(open === account.id ? null : account.id)}
                  onInspect={() => onInspect(account.id)}
                  onEnabled={(enabled) => toggle.mutate({ id: account.id, enabled })}
                  onDelete={() => confirmDelete(account)}
                  busy={toggle.isPending || remove.isPending}
                />
              ))}
            </TBody>
          </Table>
        </div>
        <FormError error={remove.error} />
      </section>
    </div>
  );
}

function AccountRows({
  account,
  overview,
  self,
  expanded,
  onToggle,
  onInspect,
  onEnabled,
  onDelete,
  busy,
}: {
  account: AdminAccount;
  overview: AdminOverview;
  self: boolean;
  expanded: boolean;
  onToggle: () => void;
  onInspect: () => void;
  onEnabled: (enabled: boolean) => void;
  onDelete: () => void;
  busy: boolean;
}) {
  return (
    <>
      <TR>
        <TD className="px-3 py-2">
          <span className="flex flex-wrap items-center gap-1.5">
            <span
              className={cn("truncate font-mono", account.disabled && "line-through opacity-60")}
            >
              {account.username}
            </span>
            {account.is_admin ? <Badge variant="secondary">admin</Badge> : null}
            {self ? <Badge variant="outline">tú</Badge> : null}
            {account.disabled ? <Badge variant="outline">desactivada</Badge> : null}
          </span>
          <span className="block text-small text-muted-foreground">{account.name}</span>
        </TD>
        <TD className="px-3 py-2">
          <button
            type="button"
            onClick={onToggle}
            className="flex items-center gap-1.5 text-left text-small hover:text-foreground"
          >
            <ChevronRight
              className={cn("size-3.5 shrink-0 transition-transform", expanded && "rotate-90")}
            />
            {/* For an administrator account the membership list does not describe what it can enter:
                it enters everything. Saying «sin acceso a ninguno» there would be false. */}
            {account.is_admin ? (
              <span className="text-muted-foreground">acceso total (administración)</span>
            ) : account.workspaces.length === 0 ? (
              <span className="text-muted-foreground">sin acceso a ninguno</span>
            ) : (
              <span className="flex flex-wrap gap-1">
                {account.workspaces.map((w) => (
                  <Badge key={w.slug} variant="outline">
                    {w.slug} · {ROLE_LABELS[w.role].toLowerCase()}
                  </Badge>
                ))}
              </span>
            )}
          </button>
        </TD>
        <TD align="num" className="px-3 py-2  nums">{account.generations}</TD>
        <TD align="num" className="px-3 py-2  nums">
          {account.evaluations}
          <span className="ml-1 text-small text-muted-foreground">({account.decided} dec.)</span>
        </TD>
        <TD className="whitespace-nowrap px-3 py-2 text-small text-muted-foreground">
          {account.created_at ? when(account.created_at) : "—"}
        </TD>
        <TD align="num" className="whitespace-nowrap px-3 py-2">
          {account.evaluations > 0 ? (
            <Button variant="ghost" size="sm" onClick={onInspect}>
              Ver sus sesiones
            </Button>
          ) : null}
          {/* Deactivating or deleting one's own account leaves the installation with nobody to
              administer it, and the server refuses both anyway; not offering them avoids a surprise
              409. They go together and in this order because they are one decision at two
              intensities: closing the door, or removing the account. */}
          {self ? null : (
            <>
              <Button
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={() => onEnabled(account.disabled)}
              >
                {account.disabled ? <UserCheck /> : <UserX />}
                {account.disabled ? "Reactivar" : "Desactivar"}
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                title="Eliminar la cuenta por completo"
                disabled={busy}
                onClick={onDelete}
              >
                <Trash2 />
              </Button>
            </>
          )}
        </TD>
      </TR>

      {expanded ? (
        <TR className="bg-muted/30">
          <TD colSpan={6} className="py-3">
            <MembershipEditor account={account} overview={overview} />
          </TD>
        </TR>
      ) : null}
    </>
  );
}

/** The memberships of one account, editable where they are read. */
function MembershipEditor({
  account,
  overview,
}: {
  account: AdminAccount;
  overview: AdminOverview;
}) {
  const { grant, revoke } = useMembershipActions();
  const missing = overview.workspaces.filter(
    (workspace) => !account.workspaces.some((w) => w.slug === workspace.slug),
  );
  const [slug, setSlug] = useState(missing[0]?.slug ?? "");
  const [role, setRole] = useState<Role>("editor");

  // An administrator already reaches every workspace — that is the one `if` in
  // `access_for` — so granting them a membership changes nothing they could not already
  // do, and a role selector here would be a control with no effect. The memberships they
  // do have are still worth reading, because that is where the owner's own powers over a
  // workspace come from, but they are not something this screen hands out.
  if (account.is_admin) {
    return (
      <div className="space-y-2">
        <p className="text-small text-muted-foreground">
          Esta cuenta administra la instalación: entra en todos los workspaces sin ser
          miembro de ninguno, así que no hay accesos que darle.
        </p>
        {account.workspaces.length > 0 ? (
          <p className="flex flex-wrap items-center gap-1.5 text-small text-muted-foreground">
            Consta además como miembro de
            {account.workspaces.map((membership) => (
              <Badge key={membership.slug} variant="outline">
                {membership.slug} · {ROLE_LABELS[membership.role].toLowerCase()}
              </Badge>
            ))}
          </p>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {account.workspaces.length === 0 ? (
        <p className="text-small text-muted-foreground">
          Esta cuenta no es miembro de ningún workspace: puede entrar, pero no verá nada
          hasta que le des acceso a alguno.
        </p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border bg-background">
          {account.workspaces.map((membership) => (
            <li key={membership.slug} className="flex flex-wrap items-center gap-2 p-2">
              <span className="min-w-0 flex-1 truncate font-mono text-small">
                {membership.slug}
              </span>
              <Select
                value={membership.role}
                className="w-36"
                disabled={grant.isPending}
                onChange={(event) =>
                  grant.mutate({
                    id: account.id,
                    workspace: membership.slug,
                    role: event.target.value as Role,
                  })
                }
              >
                {ROLES.map((option) => (
                  <option key={option} value={option}>
                    {ROLE_LABELS[option]}
                  </option>
                ))}
              </Select>
              <Button
                variant="ghost"
                size="icon-sm"
                title="Quitar el acceso a este workspace"
                disabled={revoke.isPending}
                onClick={() => revoke.mutate({ id: account.id, workspace: membership.slug })}
              >
                <Trash2 />
              </Button>
            </li>
          ))}
        </ul>
      )}

      {missing.length > 0 ? (
        <div className="flex flex-wrap items-end gap-2">
          <div className="space-y-1">
            <Label htmlFor={`add-${account.id}`}>Dar acceso a</Label>
            <Select
              id={`add-${account.id}`}
              value={slug}
              className="w-56"
              onChange={(event) => setSlug(event.target.value)}
            >
              {missing.map((workspace) => (
                <option key={workspace.slug} value={workspace.slug}>
                  {workspace.name} ({workspace.slug})
                </option>
              ))}
            </Select>
          </div>
          <Select
            value={role}
            className="w-36"
            onChange={(event) => setRole(event.target.value as Role)}
          >
            {ROLES.map((option) => (
              <option key={option} value={option}>
                {ROLE_LABELS[option]}
              </option>
            ))}
          </Select>
          <Button
            size="sm"
            disabled={!slug || grant.isPending}
            onClick={() => grant.mutate({ id: account.id, workspace: slug, role })}
          >
            {grant.isPending ? <Spinner /> : null}
            Conceder
          </Button>
          <span className="text-small text-muted-foreground">{ROLE_HINTS[role]}</span>
        </div>
      ) : null}

      <FormError error={grant.error ?? revoke.error} />
    </div>
  );
}

/**
 * Invitations, which are the only way an account comes into existence.
 *
 * The link IS the invitation: nothing is sent anywhere, it works once, it expires, and
 * whoever opens it chooses their own username. That is why the copy says not to leave it
 * in a shared place — until it is redeemed it is a credential.
 */
function InviteSection({ overview }: { overview: AdminOverview }) {
  const invites = useAdminInvites();
  const create = useCreateInvite();
  const revoke = useRevokeInvite();
  const [workspace, setWorkspace] = useState<string>(overview.workspaces[0]?.slug ?? "");
  const [role, setRole] = useState<Role>("editor");

  const pending = invites.data?.invites ?? [];

  return (
    <section className="space-y-3 rounded-lg border border-border bg-card p-3 shadow-sm">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
          Invitar a alguien
        </h2>
        <InfoHint label="Cómo se entra aquí">
          No hay registro abierto: una cuenta existe porque alguien abrió una invitación de
          un solo uso, o porque se creó desde la línea de órdenes. Quitar el registro
          público es lo que quita de en medio el mayor blanco de un login web.
        </InfoHint>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="invite-workspace">Workspace</Label>
          <Select
            id="invite-workspace"
            value={workspace}
            className="w-64"
            onChange={(event) => setWorkspace(event.target.value)}
          >
            <option value="">Ninguno (solo crear la cuenta)</option>
            {overview.workspaces.map((row) => (
              <option key={row.slug} value={row.slug}>
                {row.name} ({row.slug})
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="invite-role">Permiso</Label>
          <Select
            id="invite-role"
            value={role}
            className="w-40"
            disabled={!workspace}
            onChange={(event) => setRole(event.target.value as Role)}
          >
            {ROLES.map((option) => (
              <option key={option} value={option}>
                {ROLE_LABELS[option]}
              </option>
            ))}
          </Select>
        </div>
        <Button
          onClick={() => create.mutate({ workspace: workspace || null, role })}
          disabled={create.isPending}
        >
          {create.isPending ? <Spinner /> : <LinkIcon />}
          Crear enlace
        </Button>
        <span className="text-small text-muted-foreground">
          {workspace
            ? ROLE_HINTS[role]
            : "Entrará sin acceso a ninguna instancia; se lo das después desde la tabla."}
        </span>
      </div>

      <FormError error={create.error} />
      {create.isSuccess ? <InviteLink link={create.data.link} /> : null}

      {pending.length > 0 ? (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {pending.map((invite) => (
            <li key={invite.id} className="flex flex-wrap items-center gap-2 p-2 text-body">
              <div className="min-w-0 flex-1">
                {/* There is no addressee to name: what tells two pending links apart is when they were
                    issued and for which instance. */}
                <p className="truncate">
                  Enlace del {new Date(invite.created_at).toLocaleDateString("es-ES")}
                  {invite.created_by ? (
                    <span className="ml-1 text-small text-muted-foreground">
                      · lo creó {invite.created_by}
                    </span>
                  ) : null}
                </p>
                <p className="text-small text-muted-foreground">
                  {invite.workspace_slug
                    ? `${invite.workspace_slug} · ${ROLE_LABELS[invite.role]}`
                    : "sin workspace"}{" "}
                  · caduca el {new Date(invite.expires_at).toLocaleDateString("es-ES")}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                title="Anular"
                disabled={revoke.isPending}
                onClick={() => revoke.mutate(invite.id)}
              >
                <Trash2 />
              </Button>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}

function InviteLink({ link }: { link: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-3">
      <p className="text-body">
        Pásaselo tú a quien invitas. Sirve una sola vez y quien lo abra elegirá su propio
        usuario, así que no lo dejes en un sitio compartido.
      </p>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded bg-background px-2 py-1 font-mono text-small">
          {link}
        </code>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            navigator.clipboard.writeText(link);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? <Check /> : <Copy />}
          {copied ? "Copiado" : "Copiar"}
        </Button>
      </div>
    </div>
  );
}

/**
 * The installation's instances, and the one thing this panel writes about them: removing them.
 *
 * Emptying a stage and deleting the workspace are one decision at two scopes, so they live
 * in the same row: the stage is emptied from its badge, the workspace from the button at the
 * end. Neither builds nor approves anything — for that one enters the instance, which is
 * where what is being touched can be seen.
 */
function WorkspacesTab({ overview }: { overview: AdminOverview }) {
  const remove = useAdminDeleteWorkspace();
  const toast = useToast();
  const [target, setTarget] = useState<AdminWorkspace | null>(null);
  const only = overview.workspaces.length === 1;

  return (
    <div className="space-y-3">
      <div className="overflow-hidden rounded-lg border border-border">
        <Table minWidth="52rem">
          <THead>
            <TR>
              <TH>Workspace</TH>
              <TH>Cadena</TH>
              <TH align="num">Miembros</TH>
              <TH align="num">Variantes</TH>
              <TH>Creado</TH>
              <TH />
            </TR>
          </THead>
          <TBody>
            {overview.workspaces.map((workspace) => (
              <TR key={workspace.id}>
                <TD className="px-3 py-2">
                  {workspace.name}
                  <span className="ml-2 font-mono text-micro text-muted-foreground">
                    {workspace.slug}
                  </span>
                  {workspace.warm ? (
                    <span className="ml-2 text-micro text-muted-foreground">· en memoria</span>
                  ) : null}
                </TD>
                <TD className="px-3 py-2">
                  <ChainCell workspace={workspace} />
                </TD>
                <TD align="num" className="px-3 py-2  nums">{workspace.members}</TD>
                <TD align="num" className="px-3 py-2  nums">{workspace.generations}</TD>
                <TD className="whitespace-nowrap px-3 py-2 text-small text-muted-foreground">
                  {workspace.created_at ? when(workspace.created_at) : "—"}
                </TD>
                <TD align="num" className="whitespace-nowrap px-3 py-2">
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    disabled={only || remove.isPending}
                    title={
                      only
                        ? "Es el único workspace de la instalación"
                        : "Eliminar el workspace y sus ficheros"
                    }
                    onClick={() => setTarget(workspace)}
                  >
                    <Trash2 />
                  </Button>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>

      <FormError error={remove.error} />

      {target ? (
        <DeleteWorkspaceDialog
          workspace={target}
          busy={remove.isPending}
          onClose={() => setTarget(null)}
          onConfirm={() =>
            remove.mutate(target.slug, {
              onSuccess: () => {
                setTarget(null);
                toast({
                  title: "Workspace eliminado",
                  description: `${target.slug}, con su árbol de ficheros.`,
                  tone: "attention",
                });
              },
              onError: (error: Error) =>
                toast({
                  title: "No se ha podido eliminar",
                  description: error.message,
                  tone: "danger",
                }),
            })
          }
        />
      ) : null}
    </div>
  );
}

/**
 * An instance's chain, and the place a stage is emptied from.
 *
 * Emptying leaves the artifact «missing» and its workspace standing: the curated file, the
 * draft and the cache derivations that spoke of it are deleted. The copies under
 * `.history/` are untouched, so a mistaken deletion is undone from «Restaurar» on the
 * artifact's screen — and that is exactly what makes offering it here not reckless.
 */
function ChainCell({ workspace }: { workspace: AdminWorkspace }) {
  const discard = useDeleteArtifact();
  const toast = useToast();

  const confirm = (artifact: AdminWorkspace["stages"][number]) => {
    const message =
      `¿Vaciar «${artifact.label}» de ${workspace.slug}?\n\n` +
      "Se borran el fichero del artefacto y las derivaciones de la caché que dependían " +
      "de él; la etapa vuelve a «sin construir» y habrá que reconstruirla.\n\n" +
      "Las copias del historial no se tocan: si te equivocas, se restaura desde la " +
      "pantalla del artefacto.";
    if (!window.confirm(message)) return;
    discard.mutate(
      { slug: workspace.slug, artifact: artifact.artifact },
      {
        onSuccess: () =>
          toast({
            title: "Etapa vaciada",
            description: `«${artifact.label}» de ${workspace.slug}. El historial sigue ahí.`,
            tone: "attention",
          }),
        onError: (error: Error) =>
          toast({ title: "No se ha podido vaciar", description: error.message, tone: "danger" }),
      },
    );
  };

  return (
    <span className="flex flex-wrap items-center gap-1">
      {workspace.stages.map((stage) => {
        const meta = ARTIFACT_STATUS[stage.status];
        const empty = stage.status === "missing";
        return (
          <button
            key={stage.artifact}
            type="button"
            disabled={empty || discard.isPending}
            title={
              empty
                ? `${stage.label}: sin construir`
                : `Vaciar «${stage.label}» de ${workspace.slug}`
            }
            onClick={() => confirm(stage)}
            className={cn(
              "rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              empty ? "cursor-default" : "hover:opacity-75",
            )}
          >
            <Badge variant={meta.tone as never}>
              {stage.label.split(" ")[0]} · {meta.label.toLowerCase()}
            </Badge>
          </button>
        );
      })}
    </span>
  );
}

/**
 * Deleting a workspace is irreversible and takes the files with it, so the slug is typed.
 *
 * Not ceremony: the row next to it looks like this one, the button is an icon, and what
 * disappears includes the documents someone uploaded — the only thing here that cannot be
 * rebuilt with a GPU and a while.
 */
function DeleteWorkspaceDialog({
  workspace,
  busy,
  onClose,
  onConfirm,
}: {
  workspace: AdminWorkspace;
  busy: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const [typed, setTyped] = useState("");
  const built = workspace.stages.filter((stage) => stage.status !== "missing");

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Eliminar «${workspace.name}»`}
      description="No se puede deshacer."
      className="max-w-lg"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant="destructive"
            disabled={typed !== workspace.slug || busy}
            onClick={onConfirm}
          >
            {busy ? <Spinner /> : <Trash2 />}
            Eliminar
          </Button>
        </>
      }
    >
      <div className="space-y-3 text-body">
        <p>Desaparecen de la instalación y del disco:</p>
        <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
          <li>
            {built.length > 0
              ? `sus artefactos construidos (${built.map((s) => s.label.toLowerCase()).join(", ")})`
              : "sus artefactos, que están todos sin construir"}
          </li>
          <li>los documentos en bruto que se subieron a esta instancia</li>
          <li>sus cachés, sus accesos y sus aprobaciones</li>
          <li>
            {workspace.generations > 0
              ? `sus ${workspace.generations} variante(s) guardada(s) y sus comparaciones`
              : "sus comparaciones de evaluación, si las hubiera"}
          </li>
        </ul>
        <div className="space-y-1">
          <Label htmlFor="confirm-slug">
            Escribe <span className="font-mono normal-case">{workspace.slug}</span> para
            confirmar
          </Label>
          <Input
            id="confirm-slug"
            value={typed}
            autoFocus
            autoComplete="off"
            onChange={(event) => setTyped(event.target.value)}
          />
        </div>
      </div>
    </Dialog>
  );
}
