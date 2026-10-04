import {
  ChevronDown,
  KeyRound,
  LockOpen,
  LogOut,
  MailPlus,
  ShieldCheck,
  ShieldOff,
  Trash2,
  UserCheck,
  Users,
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
import { PROFILE_LABEL_KEYS, PROFILES, profileLabel } from "@/lib/evaluator";
import { when } from "@/lib/format";
import { inviteState } from "@/lib/invites";
import type { AdminAccount, AdminOverview, EvaluatorProfile, Role } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT, type Key } from "@/lib/i18n";
import { ROLE_HINT_KEYS, ROLE_LABEL_KEYS, useSession } from "@/state/auth";
import {
  useAccountActions,
  useAdminInvites,
  useDeleteAccount,
  useMembershipActions,
  useSetAccountEnabled,
} from "@/state/queries";

import { CopyLink } from "./CopyLink";
import { InvitesSection } from "./InvitesSection";
import { SectionHeader, Sections } from "./Sections";

const ROLES: Role[] = ["viewer", "editor", "owner"];

/** The permissions from the widest to the narrowest: the order an account's subjects are read in. */
const ROLE_ORDER: Role[] = ["owner", "editor", "viewer"];

/**
 * THE TABLES OF THE SCREEN: each account is listed in one, by what it most is.
 *
 * A deactivated account is that before anything else, and an administrator before a
 * profile: the first is who cannot enter, the second who enters everywhere. The other
 * accounts are told apart by the profile they chose, which is what the installation calls
 * a teacher or a student; one that chose none has a table of its own, drawn only when
 * there is such an account.
 */
type GroupKey = "teachers" | "students" | "unset" | "admins" | "disabled";

const GROUPS: { key: GroupKey; label: Key; note?: Key; showProfile: boolean }[] = [
  { key: "teachers", label: "acc.group.teachers", showProfile: false },
  { key: "students", label: "acc.group.students", showProfile: false },
  { key: "unset", label: "acc.group.unset", note: "acc.group.unset.note", showProfile: false },
  { key: "admins", label: "acc.group.admins", showProfile: true },
  { key: "disabled", label: "acc.group.disabled", showProfile: true },
];

function groupOf(account: AdminAccount): GroupKey {
  if (account.disabled) return "disabled";
  if (account.is_admin) return "admins";
  if (account.evaluator_profile === "teacher") return "teachers";
  if (account.evaluator_profile === "student") return "students";
  return "unset";
}

/**
 * The one screen that decides who exists and who gets in.
 *
 * It used to be two: an owner's "Personas e invitaciones" dialog, which handed out access
 * to one workspace, and this table, which listed the same accounts and could only switch
 * them off. Two places to answer one question is how the two answers drift apart, so the
 * dialog is gone and this is the whole of it, in two sections: the accounts — moving people
 * between workspaces, disabling one — and the invitations that bring a new one in.
 *
 * ONE TABLE PER KIND OF ACCOUNT (the user's call, 2026-10-04): teachers, students,
 * administrators and the deactivated, each a block of its own with the same columns. A row
 * says who the account is and lists its subjects one per line, each with its permission;
 * what the account produced is not counted here — the exercises are its own, and what it
 * evaluated is read in «Evaluaciones».
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
  const [section, setSection] = useState("accounts");
  const invites = useAdminInvites();
  const now = Date.now();
  const waiting = invites.data
    ? invites.data.invites.filter((row) => inviteState(row, now) === "pending").length
    : null;
  const names = new Map(overview.workspaces.map((workspace) => [workspace.slug, workspace.name]));

  // Irreversible, so it is spelled out before it happens — and what it spells out is the
  // half people get wrong: the account goes, the material it produced does not.
  const confirmDelete = async (account: AdminAccount) => {
    const kept = [
      account.generations ? plural("acc.savedVariants", account.generations) : "",
      account.evaluations ? plural("acc.comparisons", account.evaluations) : "",
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
    <Sections
      label={t("acc.sections")}
      value={section}
      onChange={setSection}
      items={[
        {
          key: "accounts",
          label: t("admin.tab.accounts"),
          mark: <Users className="size-4" />,
          detail: plural("acc.count", overview.accounts.length),
        },
        {
          key: "invites",
          label: t("acc.invite"),
          mark: <MailPlus className="size-4" />,
          detail:
            waiting === null ? undefined : plural("acc.invite.pendingHeading", waiting),
        },
      ]}
    >
      {section === "invites" ? <InvitesSection overview={overview} /> : null}

      {section === "accounts" ? (
        <>
          <SectionHeader title={t("admin.tab.accounts")} description={t("acc.note")} />
          {GROUPS.map((group) => {
            const accounts = overview.accounts.filter((account) => groupOf(account) === group.key);
            if (accounts.length === 0) return null;
            return (
              <section key={group.key} aria-labelledby={`accounts-${group.key}`} className="space-y-3">
                <div className="space-y-1 px-1">
                  <h3 id={`accounts-${group.key}`} className="flex items-baseline gap-2 text-heading">
                    {t(group.label)}
                    <span className="nums text-small font-normal text-muted-foreground">
                      {accounts.length}
                    </span>
                  </h3>
                  {group.note ? (
                    <p className="text-small text-muted-foreground">{t(group.note)}</p>
                  ) : null}
                </div>
                <div className="surface overflow-hidden p-2">
                  {/* The same widths on every table, so a column is one line down the page. */}
                  <Table minWidth="50rem" className="table-fixed">
                    <THead>
                      <TR>
                        <TH className="w-[12.5rem]">{t("acc.col.account")}</TH>
                        <TH>{t("acc.col.subjects")}</TH>
                        <TH className="w-[7rem]">{t("acc.col.created")}</TH>
                        <TH className="w-[15.5rem]" />
                      </TR>
                    </THead>
                    <TBody>
                      {accounts.map((account) => (
                        <AccountRows
                          key={account.id}
                          account={account}
                          overview={overview}
                          names={names}
                          showProfile={group.showProfile}
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
              </section>
            );
          })}
          <FormError error={remove.error} />
        </>
      ) : null}
    </Sections>
  );
}

/**
 * One account: who it is, its subjects, since when, and what can be done with it.
 *
 * Every cell starts at the top of the row: an account with five subjects is five lines
 * tall, and its name centred against them read as belonging to the third.
 */
function AccountRows({
  account,
  overview,
  names,
  showProfile,
  self,
  expanded,
  onToggle,
  onEnabled,
  onDelete,
  busy,
}: {
  account: AdminAccount;
  overview: AdminOverview;
  /** Every subject's name by its slug: an account carries the slugs alone. */
  names: Map<string, string>;
  /** Where the table does not say it already: the administrators' and the deactivated. */
  showProfile: boolean;
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
      <TR className={cn(expanded && "bg-none")}>
        <TD className="py-3 align-top">
          <span className="flex flex-wrap items-center gap-1.5">
            <span className="truncate font-mono text-body">{account.username}</span>
            {/* Only where the table is not the administrators' own: a deactivated one. */}
            {account.is_admin && account.disabled ? (
              <Badge variant="secondary">{t("acc.badge.admin")}</Badge>
            ) : null}
            {self ? <Badge variant="outline">{t("acc.badge.you")}</Badge> : null}
            {locked ? (
              <Badge variant="attention" title={t("acc.lockedSeconds", { n: Math.ceil(account.locked_seconds) })}>
                {t("acc.badge.locked")}
              </Badge>
            ) : null}
          </span>
          <span className="block truncate text-muted-foreground">
            {account.name}
            {showProfile ? ` · ${profileLabel(account.evaluator_profile, t).toLowerCase()}` : ""}
          </span>
        </TD>
        <TD className="py-3 align-top">
          <SubjectList account={account} names={names} />
        </TD>
        <TD className="whitespace-nowrap py-3 align-top text-muted-foreground">
          {account.created_at ? when(account.created_at) : "—"}
        </TD>
        <TD className="py-2 align-top">
          <div className="flex items-center justify-end gap-1">
          <Button variant="ghost" size="sm" aria-expanded={expanded} onClick={onToggle}>
            {t("acc.manage")}
            <ChevronDown className={cn("transition-transform", expanded && "rotate-180")} />
          </Button>
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
          </div>
        </TD>
      </TR>

      {expanded ? (
        <TR>
          <TD colSpan={4} className="pb-4 pt-0">
            <div className="well grid gap-x-8 gap-y-5 p-4 lg:grid-cols-2">
              <div className="space-y-3">
                <h4 className="text-micro font-condensed uppercase text-muted-foreground">
                  {t("acc.col.subjects")}
                </h4>
                <MembershipEditor account={account} overview={overview} names={names} />
              </div>
              <div className="space-y-3">
                <h4 className="text-micro font-condensed uppercase text-muted-foreground">
                  {t("acc.theAccount")}
                </h4>
                <AccountControls account={account} self={self} />
              </div>
            </div>
          </TD>
        </TR>
      ) : null}
    </>
  );
}

/**
 * The subjects of one account, one per line: the name, then the permission in a column of
 * its own, the widest permission first.
 *
 * A line each and not a row of pills: with four subjects the pills wrapped where they
 * pleased, and which permission went with which subject had to be worked out.
 */
function SubjectList({ account, names }: { account: AdminAccount; names: Map<string, string> }) {
  const { t } = useT();
  const subjects = account.workspaces
    .map((membership) => ({ ...membership, name: names.get(membership.slug) ?? membership.slug }))
    .sort(
      (a, b) =>
        ROLE_ORDER.indexOf(a.role) - ROLE_ORDER.indexOf(b.role) || a.name.localeCompare(b.name),
    );
  return (
    <div className="space-y-1.5">
      {/* For an administrator the membership list does not describe what it can enter: it
          enters everything. Saying "sin acceso a ninguna" there would be false. */}
      {account.is_admin ? (
        <p className="text-muted-foreground">{t("acc.fullAccess")}</p>
      ) : subjects.length === 0 ? (
        <p className="text-muted-foreground">{t("acc.noAccess")}</p>
      ) : null}
      {subjects.length > 0 ? (
        <ul className="space-y-1.5">
          {subjects.map((subject) => (
            <li
              key={subject.slug}
              className="grid grid-cols-[minmax(0,1fr)_5.5rem] items-baseline gap-3"
            >
              <span className="break-words" title={subject.slug}>
                {subject.name}
              </span>
              <span className="text-micro font-condensed uppercase text-muted-foreground">
                {t(ROLE_LABEL_KEYS[subject.role])}
              </span>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
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
  const { setAdmin, setProfile, resetLink, revokeSessions, unlock } = useAccountActions();
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

  // Not confirmed, unlike everything else on this row: it grants nothing, nobody is locked
  // out by it, and setting it back costs one more click.
  const changeProfile = (value: string) => {
    const profile = (value || null) as EvaluatorProfile | null;
    setProfile.mutate(
      { id: account.id, profile },
      {
        onSuccess: () =>
          toast({
            title: t("acc.profileToast"),
            description: t("acc.profileToastBody", {
              username: account.username,
              profile: profileLabel(profile, t).toLowerCase(),
            }),
          }),
        onError: (error: Error) =>
          toast({ title: t("acc.changeFailed"), description: error.message, tone: "danger" }),
      },
    );
  };

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
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
          <span className="nums text-muted-foreground">{account.sessions}</span>
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
      {/* An administrator is a teacher or a student like anybody else: the profile decides
          what somebody is asked when they compare, and `require_member` never reads it. It
          lives here rather than beside the memberships for exactly that reason. */}
      <div className="flex flex-wrap items-center gap-2">
        <Label htmlFor={`profile-${account.id}`}>{t("acc.profileLabel")}</Label>
        <Select
          id={`profile-${account.id}`}
          value={account.evaluator_profile ?? ""}
          className="w-44"
          disabled={setProfile.isPending}
          onChange={(event) => changeProfile(event.target.value)}
        >
          <option value="">{t("acc.profileUnset")}</option>
          {PROFILES.map((option) => (
            <option key={option} value={option}>
              {t(PROFILE_LABEL_KEYS[option])}
            </option>
          ))}
        </Select>
        <InfoHint label={t("acc.profileHint")}>{t("acc.profileHint.body")}</InfoHint>
      </div>

      <FormError
        error={
          setAdmin.error ??
          setProfile.error ??
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
  names,
}: {
  account: AdminAccount;
  overview: AdminOverview;
  names: Map<string, string>;
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
      <p className="text-small text-muted-foreground">{t("acc.adminNoMemberships")}</p>
    );
  }

  return (
    <div className="space-y-3">
      {account.workspaces.length === 0 ? (
        <p className="text-small text-muted-foreground">
          {t("acc.noMemberships")}
        </p>
      ) : (
        <ul className="divide-y divide-border">
          {account.workspaces.map((membership) => (
            <li key={membership.slug} className="flex flex-wrap items-center gap-2 py-2">
              <span className="min-w-0 flex-1">
                <span className="block truncate text-small">
                  {names.get(membership.slug) ?? membership.slug}
                </span>
                <span className="block truncate font-mono text-small text-muted-foreground">
                  {membership.slug}
                </span>
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
