import {
  Check,
  ChevronRight,
  Copy,
  KeyRound,
  Link as LinkIcon,
  LockOpen,
  LogOut,
  ShieldCheck,
  ShieldOff,
  Trash2,
  UserCheck,
  UserX,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InfoHint } from "@/components/ui/hint";
import { Label, Select } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { when } from "@/lib/format";
import type { AdminAccount, AdminOverview, Role } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { ROLE_HINT_KEYS, ROLE_LABEL_KEYS, useSession } from "@/state/auth";
import {
  useAccountActions,
  useAdminInvites,
  useCreateInvite,
  useDeleteAccount,
  useMembershipActions,
  useRevokeInvite,
  useSetAccountEnabled,
} from "@/state/queries";

const ROLES: Role[] = ["viewer", "editor", "owner"];

/**
 * The one screen that decides who exists and who gets in.
 *
 * It used to be two: an owner's "Personas e invitaciones" dialog, which handed out access
 * to one workspace, and this table, which listed the same accounts and could only switch
 * them off. Two places to answer one question is how the two answers drift apart, so the
 * dialog is gone and this is the whole of it — issuing invitations, moving people between
 * workspaces and disabling an account, in that order, which is the order they happen in.
 *
 * Access is per workspace and this panel crosses them all, so a row's memberships open
 * where the row is rather than obliging the administrator to change workspace to grant one.
 */
export function AccountsTab({ overview }: { overview: AdminOverview }) {
  const { plural, t } = useT();
  const confirm = useConfirm();
  const toggle = useSetAccountEnabled();
  const remove = useDeleteAccount();
  const session = useSession();
  const toast = useToast();
  const [open, setOpen] = useState<number | null>(null);

  // Irreversible, so it is spelled out before it happens — and what it spells out is the
  // half people get wrong: the account goes, the material it produced does not.
  const confirmDelete = async (account: AdminAccount) => {
    const kept = [
      account.generations ? plural("acc.savedVariants", account.generations) : "",
    ].filter(Boolean);
    const message =
      t("acc.deleteConfirm", { username: account.username }) +
      (kept.length ? t("acc.deleteKept", { kept: kept.join(t("acc.and")) }) : "") +
      t("acc.deleteTail");
    if (!(await confirm({ title: message, tone: "danger" }))) return;
    // The dialog is the confirmation BEFORE; this is the one after. Everything on this
    // screen that destroys something says so once it is done, because the row simply
    // disappearing is indistinguishable from a list that reloaded.
    remove.mutate(account.id, {
      onSuccess: () =>
        toast({ title: t("acc.deleted"), description: account.username, tone: "attention" }),
      onError: (error: Error) =>
        toast({ title: t("acc.deleteFailed"), description: error.message, tone: "danger" }),
    });
  };

  return (
    <div className="space-y-5">
      <InviteSection overview={overview} />

      <section className="space-y-2">
        <h2 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
          {t("acc.heading", { n: overview.accounts.length })}
        </h2>
        <div className="overflow-hidden rounded-lg border border-border">
          <Table minWidth="56rem">
            <THead>
              <TR>
                <TH>{t("acc.col.account")}</TH>
                <TH>{t("acc.col.access")}</TH>
                <TH align="num">{t("acc.col.variants")}</TH>
                <TH align="num">{t("acc.col.sessions")}</TH>
                <TH>{t("acc.col.created")}</TH>
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
  onEnabled,
  onDelete,
  busy,
}: {
  account: AdminAccount;
  overview: AdminOverview;
  self: boolean;
  expanded: boolean;
  onToggle: () => void;
  onEnabled: (enabled: boolean) => void;
  onDelete: () => void;
  busy: boolean;
}) {
  const { t } = useT();
  const locked = account.locked_seconds > 0;
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
            {account.is_admin ? <Badge variant="secondary">{t("acc.badge.admin")}</Badge> : null}
            {self ? <Badge variant="outline">{t("acc.badge.you")}</Badge> : null}
            {account.disabled ? (
              <Badge variant="outline">{t("acc.badge.disabled")}</Badge>
            ) : null}
            {locked ? (
              <Badge variant="attention" title={t("acc.lockedSeconds", { n: Math.ceil(account.locked_seconds) })}>
                {t("acc.badge.locked")}
              </Badge>
            ) : null}
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
                it enters everything. Saying "sin acceso a ninguno" there would be false. */}
            {account.is_admin ? (
              <span className="text-muted-foreground">{t("acc.fullAccess")}</span>
            ) : account.workspaces.length === 0 ? (
              <span className="text-muted-foreground">{t("acc.noAccess")}</span>
            ) : (
              <span className="flex flex-wrap gap-1">
                {account.workspaces.map((w) => (
                  <Badge key={w.slug} variant="outline">
                    {w.slug} · {t(ROLE_LABEL_KEYS[w.role]).toLowerCase()}
                  </Badge>
                ))}
              </span>
            )}
          </button>
        </TD>
        <TD align="num" className="px-3 py-2 nums">{account.generations}</TD>
        <TD align="num" className="px-3 py-2 nums">{account.sessions}</TD>
        <TD className="whitespace-nowrap px-3 py-2 text-small text-muted-foreground">
          {account.created_at ? when(account.created_at) : "—"}
        </TD>
        <TD align="num" className="whitespace-nowrap px-3 py-2">
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
                {account.disabled ? t("acc.reactivate") : t("acc.deactivate")}
              </Button>
              <Button
                variant="ghost"
                size="icon-sm"
                title={t("acc.deleteTitle")}
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
          <TD colSpan={7} className="space-y-4 py-3">
            <MembershipEditor account={account} overview={overview} />
            <AccountControls account={account} self={self} />
          </TD>
        </TR>
      ) : null}
    </>
  );
}

/**
 * What the administrator can do to an account beyond letting it in or not: make it an
 * administrator, hand it a way back in when the password is lost, close the sessions it
 * has open, and lift the login lock. Each is one call with one consequence, and the ones
 * that are confirmed are the ones that somebody else feels at once.
 */
function AccountControls({ account, self }: { account: AdminAccount; self: boolean }) {
  const { plural, t } = useT();
  const confirm = useConfirm();
  const { setAdmin, resetLink, revokeSessions, unlock } = useAccountActions();
  const toast = useToast();
  const locked = account.locked_seconds > 0;

  const confirmAdmin = async () => {
    const message = t(
      account.is_admin ? "acc.confirmRemoveAdmin" : "acc.confirmMakeAdmin",
      { username: account.username },
    );
    if (!(await confirm({ title: message, tone: "danger" }))) return;
    setAdmin.mutate(
      { id: account.id, isAdmin: !account.is_admin },
      {
        onSuccess: ({ is_admin }) =>
          toast({
            title: is_admin ? t("acc.nowAdmin") : t("acc.noLongerAdmin"),
            description: account.username,
            tone: "attention",
          }),
        onError: (error: Error) =>
          toast({ title: t("acc.changeFailed"), description: error.message, tone: "danger" }),
      },
    );
  };

  const confirmRevoke = async () => {
    const message = plural("acc.revokeConfirm", account.sessions, {
      n: plural("acc.openSessions", account.sessions),
      username: account.username,
    });
    if (!(await confirm({ title: message, tone: "danger" }))) return;
    revokeSessions.mutate(account.id, {
      onSuccess: ({ revoked }) =>
        toast({
          title: t("acc.sessionsClosed"),
          description: t("acc.sessionsClosedOf", { n: revoked, username: account.username }),
        }),
      onError: (error: Error) =>
        toast({ title: t("acc.failed"), description: error.message, tone: "danger" }),
    });
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-small font-medium uppercase tracking-wide text-muted-foreground">
          {t("acc.theAccount")}
        </span>
        {self ? null : (
          <Button variant="outline" size="sm" disabled={setAdmin.isPending} onClick={confirmAdmin}>
            {account.is_admin ? <ShieldOff /> : <ShieldCheck />}
            {account.is_admin ? t("acc.removeAdmin") : t("acc.makeAdmin")}
          </Button>
        )}
        <Button
          variant="outline"
          size="sm"
          disabled={resetLink.isPending || account.disabled}
          title={
            account.disabled
              ? t("acc.resetDisabled")
              : t("acc.resetHint")
          }
          onClick={() => resetLink.mutate(account.id)}
        >
          {resetLink.isPending ? <Spinner /> : <KeyRound />}
          {t("acc.resetLink")}
        </Button>
        <Button
          variant="outline"
          size="sm"
          disabled={revokeSessions.isPending || account.sessions === 0}
          title={account.sessions === 0 ? t("acc.noOpenSessions") : undefined}
          onClick={confirmRevoke}
        >
          <LogOut />
          {t("acc.closeSessions")}
        </Button>
        {locked ? (
          <Button
            variant="outline"
            size="sm"
            disabled={unlock.isPending}
            onClick={() =>
              unlock.mutate(account.id, {
                onSuccess: () =>
                  toast({ title: t("acc.loginUnlocked"), description: account.username }),
              })
            }
          >
            <LockOpen />
            {t("acc.unlockLogin", { n: Math.ceil(account.locked_seconds / 60) })}
          </Button>
        ) : null}
      </div>
      <FormError
        error={
          setAdmin.error ??
          resetLink.error ??
          revokeSessions.error ??
          unlock.error
        }
      />
      {resetLink.isSuccess ? (
        <CopyLink link={resetLink.data.link}>
          {t("acc.resetCopy", {
            minutes: resetLink.data.expires_in_minutes,
            username: account.username,
          })}
        </CopyLink>
      ) : null}
    </div>
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
  const { t } = useT();
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
          {t("acc.adminNoMemberships")}
        </p>
        {account.workspaces.length > 0 ? (
          <p className="flex flex-wrap items-center gap-1.5 text-small text-muted-foreground">
            {t("acc.alsoMemberOf")}
            {account.workspaces.map((membership) => (
              <Badge key={membership.slug} variant="outline">
                {membership.slug} · {t(ROLE_LABEL_KEYS[membership.role]).toLowerCase()}
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
          {t("acc.noMemberships")}
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
                    {t(ROLE_LABEL_KEYS[option])}
                  </option>
                ))}
              </Select>
              <Button
                variant="ghost"
                size="icon-sm"
                title={t("acc.revokeWorkspace")}
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
            <Label htmlFor={`add-${account.id}`}>{t("acc.grantAccessTo")}</Label>
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
            aria-label={t("acc.permission")}
            onChange={(event) => setRole(event.target.value as Role)}
          >
            {ROLES.map((option) => (
              <option key={option} value={option}>
                {t(ROLE_LABEL_KEYS[option])}
              </option>
            ))}
          </Select>
          <Button
            size="sm"
            disabled={!slug || grant.isPending}
            onClick={() => grant.mutate({ id: account.id, workspace: slug, role })}
          >
            {grant.isPending ? <Spinner /> : null}
            {t("acc.grant")}
          </Button>
          <span className="text-small text-muted-foreground">{t(ROLE_HINT_KEYS[role])}</span>
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
  const { t, language } = useT();
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
          {t("acc.invite")}
        </h2>
        <InfoHint label={t("acc.invite.hintLabel")}>{t("acc.invite.hint")}</InfoHint>
      </div>

      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="invite-workspace">{t("acc.invite.workspace")}</Label>
          <Select
            id="invite-workspace"
            value={workspace}
            className="w-64"
            onChange={(event) => setWorkspace(event.target.value)}
          >
            <option value="">{t("acc.invite.noWorkspace")}</option>
            {overview.workspaces.map((row) => (
              <option key={row.slug} value={row.slug}>
                {row.name} ({row.slug})
              </option>
            ))}
          </Select>
        </div>
        <div className="space-y-1">
          <Label htmlFor="invite-role">{t("acc.permission")}</Label>
          <Select
            id="invite-role"
            value={role}
            className="w-40"
            disabled={!workspace}
            onChange={(event) => setRole(event.target.value as Role)}
          >
            {ROLES.map((option) => (
              <option key={option} value={option}>
                {t(ROLE_LABEL_KEYS[option])}
              </option>
            ))}
          </Select>
        </div>
        {/* The link binds the access and nothing else: whoever registers chooses their
            own username and password. */}
        <Button
          onClick={() => create.mutate({ workspace: workspace || null, role })}
          disabled={create.isPending}
        >
          {create.isPending ? <Spinner /> : <LinkIcon />}
          {t("acc.invite.create")}
        </Button>
        <span className="text-small text-muted-foreground">
          {workspace
            ? t(ROLE_HINT_KEYS[role])
            : t("acc.invite.noAccessHint")}
        </span>
      </div>

      <FormError error={create.error} />
      {create.isSuccess ? (
        <CopyLink link={create.data.link}>{t("acc.invite.copy")}</CopyLink>
      ) : null}

      {pending.length > 0 ? (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {pending.map((invite) => (
            <li key={invite.id} className="flex flex-wrap items-center gap-2 p-2 text-body">
              <div className="min-w-0 flex-1">
                {/* There is no addressee to name: what tells two pending links apart is when they were
                    issued and for which instance. */}
                <p className="truncate">
                  {t("acc.invite.linkOf", {
                    date: new Date(invite.created_at).toLocaleDateString(language),
                  })}
                  {invite.created_by ? (
                    <span className="ml-1 text-small text-muted-foreground">
                      {t("acc.invite.createdBy", { name: invite.created_by })}
                    </span>
                  ) : null}
                </p>
                <p className="text-small text-muted-foreground">
                  {invite.workspace_slug
                    ? `${invite.workspace_slug} · ${t(ROLE_LABEL_KEYS[invite.role])}`
                    : t("acc.invite.noWorkspaceShort")}
                  {t("acc.invite.expires", {
                    date: new Date(invite.expires_at).toLocaleDateString(language),
                  })}
                </p>
              </div>
              <Button
                variant="ghost"
                size="icon-sm"
                title={t("acc.invite.revoke")}
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

/** A credential handed over by hand: the link, the warning, and a copy button. */
export function CopyLink({ link, children }: { link: string; children: React.ReactNode }) {
  const { t } = useT();
  const [copied, setCopied] = useState(false);
  return (
    <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-3">
      <p className="text-body">{children}</p>
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
          {copied ? t("acc.copied") : t("acc.copy")}
        </Button>
      </div>
    </div>
  );
}
