import {
  ChevronDown,
  KeyRound,
  LockOpen,
  GraduationCap,
  LogOut,
  MailPlus,
  Presentation,
  ShieldCheck,
  ShieldOff,
  Trash2,
  UserCheck,
  UserX,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label, Select } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { profileLabel } from "@/lib/evaluator";
import { when } from "@/lib/format";
import { inviteState } from "@/lib/invites";
import type { AdminAccount, AdminOverview, Role } from "@/lib/types";
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

import { groupOf, matchesAccount, type GroupKey } from "./accounts";
import { CopyLink } from "./CopyLink";
import { InvitesSection } from "./InvitesSection";
import { SectionHeader, Sections } from "./Sections";

const ROLES: Role[] = ["viewer", "editor", "owner"];

/** The permissions from the widest to the narrowest: the order an account's subjects are read in. */
const ROLE_ORDER: Role[] = ["owner", "editor", "viewer"];

/**
 * The kinds of account in the order they are listed (`accounts.groupOf`), each with the
 * sentence its section opens with. A kind with no account is not listed.
 */
const GROUPS: { key: GroupKey; label: Key; note: Key; mark: LucideIcon; showProfile: boolean }[] = [
  { key: "teachers", label: "acc.group.teachers", note: "acc.group.teachers.note", mark: Presentation, showProfile: false },
  { key: "students", label: "acc.group.students", note: "acc.group.students.note", mark: GraduationCap, showProfile: false },
  { key: "admins", label: "acc.group.admins", note: "acc.group.admins.note", mark: ShieldCheck, showProfile: true },
  { key: "disabled", label: "acc.group.disabled", note: "acc.group.disabled.note", mark: UserX, showProfile: true },
];

/**
 * The one screen that decides who exists and who gets in.
 *
 * It used to be two: an owner's "Personas e invitaciones" dialog, which handed out access
 * to one workspace, and this table, which listed the same accounts and could only switch
 * them off. Two places to answer one question is how the two answers drift apart, so the
 * dialog is gone and this is the whole of it: the accounts — moving people between
 * workspaces, disabling one — and the invitations that bring a new one in.
 *
 * ONE TABLE PER KIND OF ACCOUNT (the user's call, 2026-10-04): teachers, students,
 * administrators and the deactivated, with the same columns. A row says who the account is
 * and lists its subjects one per line, each with its permission; what the account produced
 * is not counted here — the exercises are its own, and what it evaluated is read in
 * «Evaluaciones».
 *
 * EACH KIND IS A SECTION OF THE LIST, and the search over the list crosses them all (the
 * user's call, same day): stacked down one page, the students' table sat under every
 * teacher. The search reads the name and the username, and its result is the same tables
 * with the matching rows alone.
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
  const [section, setSection] = useState<GroupKey | "invites">("teachers");
  const [search, setSearch] = useState("");
  const invites = useAdminInvites();
  const now = Date.now();
  const waiting = invites.data
    ? invites.data.invites.filter((row) => inviteState(row, now) === "pending").length
    : null;
  const names = new Map(overview.workspaces.map((workspace) => [workspace.slug, workspace.name]));
  const groups = GROUPS.map((group) => ({
    ...group,
    accounts: overview.accounts.filter((account) => groupOf(account) === group.key),
  })).filter((group) => group.accounts.length > 0);
  // An account that changes kind may empty the section open: the first one listed takes over.
  const current =
    section === "invites" ? null : (groups.find((group) => group.key === section) ?? groups[0]);
  const term = search.trim();
  const matches = term
    ? groups
        .map((group) => ({
          ...group,
          accounts: group.accounts.filter((account) => matchesAccount(account, term)),
        }))
        .filter((group) => group.accounts.length > 0)
    : null;

  // The row leaves the table it was in, so the change is said: a row that simply
  // disappears is indistinguishable from a list that reloaded.
  const setEnabled = (account: AdminAccount, enabled: boolean) =>
    toggle.mutate(
      { id: account.id, enabled },
      {
        onSuccess: () =>
          toast({
            title: t(enabled ? "acc.reactivated" : "acc.deactivated"),
            description: account.username,
          }),
        onError: (error: Error) =>
          toast({ title: t("acc.changeFailed"), description: error.message, tone: "danger" }),
      },
    );

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

  const tableOf = (accounts: AdminAccount[], showProfile: boolean) => (
    <AccountsTable
      accounts={accounts}
      overview={overview}
      names={names}
      showProfile={showProfile}
      selfId={session.data?.user.id}
      open={open}
      onOpen={setOpen}
      onEnabled={setEnabled}
      onDelete={confirmDelete}
      busy={toggle.isPending || remove.isPending}
    />
  );

  return (
    <Sections
      label={t("acc.sections")}
      value={matches ? null : (current?.key ?? "invites")}
      onChange={(key) => {
        setSearch("");
        setSection(key as GroupKey | "invites");
      }}
      before={
        <Input
          type="search"
          aria-label={t("acc.search")}
          placeholder={t("acc.searchPlaceholder")}
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
      }
      items={[
        ...groups.map((group) => ({
          key: group.key,
          label: t(group.label),
          mark: <group.mark className="size-4" />,
          detail: plural("acc.count", group.accounts.length),
        })),
        {
          key: "invites",
          label: t("acc.invite"),
          mark: <MailPlus className="size-4" />,
          detail:
            waiting === null ? undefined : plural("acc.invite.pendingHeading", waiting),
        },
      ]}
    >
      {matches ? (
        <>
          <SectionHeader
            title={plural(
              "acc.matches",
              matches.reduce((total, group) => total + group.accounts.length, 0),
              { term },
            )}
            description={matches.length === 0 ? t("acc.noMatches") : undefined}
          />
          {matches.map((group) => (
            <section key={group.key} aria-labelledby={`accounts-${group.key}`} className="space-y-3">
              <h3 id={`accounts-${group.key}`} className="flex items-baseline gap-2 px-1 text-heading">
                {t(group.label)}
                <span className="nums text-small font-normal text-muted-foreground">
                  {group.accounts.length}
                </span>
              </h3>
              {tableOf(group.accounts, group.showProfile)}
            </section>
          ))}
        </>
      ) : current ? (
        <>
          <SectionHeader title={t(current.label)} description={t(current.note)} />
          {tableOf(current.accounts, current.showProfile)}
        </>
      ) : (
        <InvitesSection overview={overview} />
      )}
      {matches || current ? <FormError error={remove.error} /> : null}
    </Sections>
  );
}

/** The accounts of one kind: the same columns and widths wherever the table is drawn. */
function AccountsTable({
  accounts,
  overview,
  names,
  showProfile,
  selfId,
  open,
  onOpen,
  onEnabled,
  onDelete,
  busy,
}: {
  accounts: AdminAccount[];
  overview: AdminOverview;
  /** Every subject's name by its slug: an account carries the slugs alone. */
  names: Map<string, string>;
  /** Where the table does not say it already: the administrators' and the deactivated. */
  showProfile: boolean;
  selfId: number | undefined;
  /** The account whose controls are open under its row, across every table. */
  open: number | null;
  onOpen: (id: number | null) => void;
  onEnabled: (account: AdminAccount, enabled: boolean) => void;
  onDelete: (account: AdminAccount) => void;
  busy: boolean;
}) {
  const { t } = useT();
  return (
    <div className="surface overflow-hidden p-2">
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
              showProfile={showProfile}
              self={account.id === selfId}
              expanded={open === account.id}
              onToggle={() => onOpen(open === account.id ? null : account.id)}
              onEnabled={(enabled) => onEnabled(account, enabled)}
              onDelete={() => onDelete(account)}
              busy={busy}
            />
          ))}
        </TBody>
      </Table>
    </div>
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
  const { setAdmin, makeTeacher, resetLink, revokeSessions, unlock } = useAccountActions();
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

  // Confirmed, because it cannot be undone: the profile only climbs, and a teacher creates
  // subjects from the moment it lands.
  const confirmTeacher = async () => {
    const asked = await confirm({
      title: t("acc.makeTeacherConfirm", { username: account.username }),
      body: t("acc.makeTeacherConfirmBody"),
      confirmLabel: t("acc.makeTeacher"),
    });
    if (!asked) return;
    makeTeacher.mutate(account.id, {
      onSuccess: () =>
        toast({ title: t("acc.nowTeacher"), description: account.username }),
      onError: (error: Error) =>
        toast({ title: t("acc.changeFailed"), description: error.message, tone: "danger" }),
    });
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
      {/* The account's profile decides one thing, creating subjects, and `require_member`
          never reads it: it lives here rather than beside the memberships for that reason.
          It only climbs, so a teacher has no control and anybody else has one button. */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-small">
          {t("acc.profileLabel")}:{" "}
          <span className="font-medium">{profileLabel(account.evaluator_profile, t)}</span>
        </span>
        {account.evaluator_profile !== "teacher" ? (
          <Button
            variant="outline"
            size="sm"
            disabled={makeTeacher.isPending}
            onClick={confirmTeacher}
          >
            {makeTeacher.isPending ? <Spinner /> : <Presentation />}
            {t("acc.makeTeacher")}
          </Button>
        ) : null}
        <InfoHint label={t("acc.profileHint")}>{t("acc.profileHint.body")}</InfoHint>
      </div>

      <FormError
        error={
          setAdmin.error ??
          makeTeacher.error ??
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
  const { grant, revoke, enable } = useMembershipActions();
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
              <span className={cn("min-w-0 flex-1", membership.disabled && "text-muted-foreground")}>
                <span className="block truncate text-small">
                  {names.get(membership.slug) ?? membership.slug}
                </span>
                <span className="block truncate font-mono text-small text-muted-foreground">
                  {membership.slug}
                </span>
              </span>
              {membership.disabled ? (
                // Paused by a teacher: the role stays as it was, and what is offered is
                // opening it again or taking it away, as the class screen offers.
                <>
                  <Badge variant="outline">{t("acc.membershipPaused")}</Badge>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={enable.isPending}
                    onClick={() => enable.mutate({ id: account.id, workspace: membership.slug })}
                  >
                    <UserCheck />
                    {t("class.open")}
                  </Button>
                </>
              ) : (
                <Select
                  value={membership.role}
                  className="w-36"
                  aria-label={t("acc.permission")}
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
              )}
              <Button
                variant="ghost"
                size="icon-sm"
                title={t("acc.revokeWorkspace")}
                aria-label={t("acc.revokeWorkspace")}
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

      <FormError error={grant.error ?? revoke.error ?? enable.error} />
    </div>
  );
}
