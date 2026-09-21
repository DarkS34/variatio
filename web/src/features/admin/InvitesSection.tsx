import {
  Eye,
  EyeOff,
  Link as LinkIcon,
  Pencil,
  RotateCcw,
  Trash2,
  X,
} from "lucide-react";
import { useRef, useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label, Select } from "@/components/ui/input";
import { Alert, LoadError, Spinner } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { dateTime, relative } from "@/lib/format";
import { useT, type Key } from "@/lib/i18n";
import {
  BATCH_MAX,
  EXPIRY_PRESETS,
  LABEL_MAX,
  changesOf,
  draftOf,
  fromLocalInput,
  inDays,
  inviteState,
  isAhead,
  linkLines,
  matchesInvite,
  newDraft,
  termsOf,
  toLocalInput,
  type ExpiryPreset,
  type TermsDraft,
} from "@/lib/invites";
import type {
  AdminOverview,
  InviteImportOutcome,
  InviteRow,
  InviteState,
  MintedInvite,
  Role,
} from "@/lib/types";
import { cn } from "@/lib/utils";
import { ROLE_HINT_KEYS, ROLE_LABEL_KEYS } from "@/state/auth";
import {
  useAdminInvites,
  useCreateInvites,
  useEditInvite,
  useImportInvite,
  useInviteLink,
  useRevokeInvite,
} from "@/state/queries";

import { CopyButton, CopyLink } from "./CopyLink";

const ROLES: Role[] = ["viewer", "editor", "owner"];

const PRESET_KEYS: Record<ExpiryPreset, Key> = {
  day: "acc.invite.preset.day",
  week: "acc.invite.preset.week",
  month: "acc.invite.preset.month",
  quarter: "acc.invite.preset.quarter",
};

// Below this many rows a search box finds nothing a glance would not.
const SEARCH_FROM = 6;

// A labelled control that takes the whole line on a phone and its own width above that.
const FIELD = "w-full space-y-1 sm:w-auto";

type Mode = "new" | "recover";
type Recovered = MintedInvite & { outcome: InviteImportOutcome };

/**
 * Invitations, which are the only way an account comes into existence.
 *
 * The link IS the invitation: nothing is sent anywhere, it works once, it expires, and
 * whoever opens it chooses their own username — so until it is redeemed it is a credential.
 * What the administrator controls around that is everything but the single use: when it
 * expires, a name only this panel shows, the asignatura and permission it carries, reading
 * the link again, and pasting back the link of one deleted by mistake. The listing never
 * carries a link; «Ver enlace» asks for that one and the server writes down who did.
 */
export function InvitesSection({ overview }: { overview: AdminOverview }) {
  const { t } = useT();
  const invites = useAdminInvites();
  const [mode, setMode] = useState<Mode>("new");
  const [minted, setMinted] = useState<MintedInvite[] | null>(null);
  const [recovered, setRecovered] = useState<Recovered | null>(null);
  const top = useRef<HTMLDivElement>(null);

  const recoverLink = () => {
    setMode("recover");
    top.current?.scrollIntoView({ block: "nearest" });
  };

  return (
    <section className="space-y-4 rounded-lg border border-border bg-card p-3 shadow-sm">
      <div ref={top} className="flex scroll-mt-24 flex-wrap items-center gap-2">
        <h2 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
          {t("acc.invite")}
        </h2>
        <InfoHint label={t("acc.invite.hintLabel")}>{t("acc.invite.hint")}</InfoHint>
        <Tabs
          className="ml-auto"
          value={mode}
          onChange={(next) => setMode(next as Mode)}
          items={[
            { value: "new", label: t("acc.invite.mode.new") },
            { value: "recover", label: t("acc.invite.mode.recover") },
          ]}
        />
      </div>

      {/* Each form keeps its own last result under it, so a batch's links are still there to
          copy after a look at the other tab. */}
      {mode === "new" ? (
        <>
          <NewInvites overview={overview} onMinted={setMinted} />
          {minted ? <MintedLinks minted={minted} onDismiss={() => setMinted(null)} /> : null}
        </>
      ) : (
        <>
          <RecoverInvite overview={overview} onRecovered={setRecovered} />
          {recovered ? (
            <RecoveredNotice recovered={recovered} onDismiss={() => setRecovered(null)} />
          ) : null}
        </>
      )}

      {invites.isError ? (
        <LoadError
          title={t("acc.invite.loadFailed")}
          error={invites.error}
          onRetry={() => invites.refetch()}
        />
      ) : invites.isLoading ? (
        <Spinner />
      ) : (
        <InviteList
          rows={invites.data?.invites ?? []}
          overview={overview}
          onRecover={recoverLink}
        />
      )}
    </section>
  );
}

function NewInvites({
  overview,
  onMinted,
}: {
  overview: AdminOverview;
  onMinted: (minted: MintedInvite[]) => void;
}) {
  const { t } = useT();
  const create = useCreateInvites();
  const [draft, setDraft] = useState<TermsDraft>(() => newDraft(overview.workspaces[0]?.slug));
  // Text and not a number: an emptied box is a state the person passes through while
  // typing, and a number field that snaps back to 1 fights them.
  const [countText, setCountText] = useState("1");
  const count = /^\d+$/.test(countText) ? Number(countText) : 0;
  const countOk = count >= 1 && count <= BATCH_MAX;
  const terms = termsOf(draft);
  const ready = terms !== null && isAhead(draft.expires) && countOk;
  const alias = draft.label.trim();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!ready || !terms) return;
    create.mutate(
      { ...terms, count },
      {
        onSuccess: (data) => {
          onMinted(data.invites ?? [{ invite: data.invite, link: data.link }]);
          setDraft((current) => ({ ...current, label: "" }));
          setCountText("1");
        },
      },
    );
  };

  return (
    <form noValidate onSubmit={submit} className="space-y-3">
      <TermsFields draft={draft} onChange={setDraft} overview={overview} idPrefix="invite-new" />
      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor="invite-new-count">{t("acc.invite.count")}</Label>
          <Input
            id="invite-new-count"
            type="number"
            inputMode="numeric"
            min={1}
            max={BATCH_MAX}
            value={countText}
            aria-invalid={!countOk}
            className="w-24"
            onChange={(event) => setCountText(event.target.value)}
          />
        </div>
        <Button type="submit" disabled={!ready || create.isPending}>
          {create.isPending ? <Spinner /> : <LinkIcon />}
          {count > 1 ? t("acc.invite.createMany", { n: count }) : t("acc.invite.create")}
        </Button>
        <span className="text-small text-muted-foreground">
          {draft.workspace ? t(ROLE_HINT_KEYS[draft.role]) : t("acc.invite.noAccessHint")}
        </span>
      </div>
      {!countOk ? (
        <p className="text-small text-destructive">{t("acc.invite.countRange", { max: BATCH_MAX })}</p>
      ) : count > 1 ? (
        <p className="text-small text-muted-foreground">
          {alias
            ? t("acc.invite.batchNamed", { n: count, label: alias })
            : t("acc.invite.batchUnnamed", { n: count })}
        </p>
      ) : null}
      <FormError error={create.error} />
    </form>
  );
}

/**
 * Pasting back a link that was already handed over.
 *
 * For the invitation deleted by mistake: its holder still has the link, and making that
 * same link work again is kinder than sending another. The terms below apply only when the
 * link names no invitation of the list; one that still does is left as it is.
 */
function RecoverInvite({
  overview,
  onRecovered,
}: {
  overview: AdminOverview;
  onRecovered: (recovered: Recovered) => void;
}) {
  const { t } = useT();
  const recover = useImportInvite();
  const [link, setLink] = useState("");
  const [draft, setDraft] = useState<TermsDraft>(() => newDraft(overview.workspaces[0]?.slug));
  const terms = termsOf(draft);
  const ready = link.trim().length > 0 && terms !== null && isAhead(draft.expires);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!ready || !terms) return;
    recover.mutate(
      { ...terms, link: link.trim() },
      {
        onSuccess: (data) => {
          onRecovered(data);
          setLink("");
        },
      },
    );
  };

  return (
    <form noValidate onSubmit={submit} className="space-y-3">
      <p className="max-w-3xl text-small text-muted-foreground">{t("acc.invite.recover.lead")}</p>
      <div className="space-y-1">
        <Label htmlFor="invite-recover-link">{t("acc.invite.recover.link")}</Label>
        <Input
          id="invite-recover-link"
          value={link}
          autoComplete="off"
          spellCheck={false}
          aria-describedby="invite-recover-link-hint"
          className="max-w-2xl font-mono"
          onChange={(event) => setLink(event.target.value)}
        />
        <p id="invite-recover-link-hint" className="text-small text-muted-foreground">
          {t("acc.invite.recover.linkHint")}
        </p>
      </div>
      <TermsFields
        draft={draft}
        onChange={setDraft}
        overview={overview}
        idPrefix="invite-recover"
      />
      <Button type="submit" disabled={!ready || recover.isPending}>
        {recover.isPending ? <Spinner /> : <RotateCcw />}
        {t("acc.invite.recover.submit")}
      </Button>
      <FormError error={recover.error} />
    </form>
  );
}

/**
 * What an invitation grants and until when, and the name only the panel shows.
 *
 * The date is a real picker and the four quick periods only write into it, so what will
 * be sent is always the moment on screen and never a hidden «+7 días».
 */
function TermsFields({
  draft,
  onChange,
  overview,
  idPrefix,
  dateNote,
}: {
  draft: TermsDraft;
  onChange: (next: TermsDraft) => void;
  overview: AdminOverview;
  idPrefix: string;
  /** Said under the date instead of the usual line — an expired date nobody has moved yet. */
  dateNote?: string;
}) {
  const { t } = useT();
  const set = (patch: Partial<TermsDraft>) => onChange({ ...draft, ...patch });
  const moment = fromLocalInput(draft.expires);
  const ahead = isAhead(draft.expires);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end gap-2">
        <div className={FIELD}>
          <Label htmlFor={`${idPrefix}-label`}>{t("acc.invite.alias")}</Label>
          <Input
            id={`${idPrefix}-label`}
            value={draft.label}
            maxLength={LABEL_MAX}
            autoComplete="off"
            placeholder={t("acc.invite.aliasPlaceholder")}
            aria-describedby={`${idPrefix}-label-hint`}
            className="w-full sm:w-72"
            onChange={(event) => set({ label: event.target.value })}
          />
        </div>
        <div className={FIELD}>
          <Label htmlFor={`${idPrefix}-workspace`}>{t("acc.invite.workspace")}</Label>
          <Select
            id={`${idPrefix}-workspace`}
            value={draft.workspace}
            className="w-full sm:w-64"
            onChange={(event) => set({ workspace: event.target.value })}
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
          <Label htmlFor={`${idPrefix}-role`}>{t("acc.permission")}</Label>
          <Select
            id={`${idPrefix}-role`}
            value={draft.role}
            className="w-40"
            disabled={!draft.workspace}
            onChange={(event) => set({ role: event.target.value as Role })}
          >
            {ROLES.map((option) => (
              <option key={option} value={option}>
                {t(ROLE_LABEL_KEYS[option])}
              </option>
            ))}
          </Select>
        </div>
      </div>
      <p id={`${idPrefix}-label-hint`} className="text-small text-muted-foreground">
        {t("acc.invite.aliasHint")}
      </p>

      <div className="flex flex-wrap items-end gap-2">
        <div className="space-y-1">
          <Label htmlFor={`${idPrefix}-expires`}>{t("acc.invite.expiresAt")}</Label>
          <Input
            id={`${idPrefix}-expires`}
            type="datetime-local"
            value={draft.expires}
            min={toLocalInput(new Date())}
            aria-invalid={!ahead && !dateNote}
            aria-describedby={`${idPrefix}-expires-hint`}
            className="w-56"
            onChange={(event) => set({ expires: event.target.value })}
          />
        </div>
        <div role="group" aria-label={t("acc.invite.quickExpiry")} className="flex flex-wrap gap-1">
          {EXPIRY_PRESETS.map((preset) => (
            <Button
              key={preset.key}
              type="button"
              size="sm"
              variant="outline"
              onClick={() => set({ expires: toLocalInput(inDays(preset.days)) })}
            >
              {t(PRESET_KEYS[preset.key])}
            </Button>
          ))}
        </div>
      </div>
      <p
        id={`${idPrefix}-expires-hint`}
        className={cn(
          "text-small",
          ahead || dateNote ? "text-muted-foreground" : "text-destructive",
        )}
      >
        {dateNote
          ? dateNote
          : !moment
            ? t("acc.invite.expiryMissing")
            : ahead
              ? t("acc.invite.expiresIn", { when: relative(moment.toISOString()) })
              : t("acc.invite.expiryPast")}
      </p>
    </div>
  );
}

/** What was just minted: one link as ever, or a batch to hand out one by one. */
function MintedLinks({ minted, onDismiss }: { minted: MintedInvite[]; onDismiss: () => void }) {
  const { plural, t } = useT();
  const lost = minted.some((item) => item.stored === false);
  const warning = lost ? (
    <Alert tone="attention" title={t("acc.invite.notStoredNow")} />
  ) : null;

  if (minted.length === 1) {
    const [only] = minted;
    return (
      <div className="space-y-2">
        <CopyLink link={only.link} onDismiss={onDismiss}>
          {only.invite.label
            ? t("acc.invite.copyNamed", { label: only.invite.label })
            : t("acc.invite.copy")}
        </CopyLink>
        {warning}
      </div>
    );
  }

  return (
    <div className="space-y-2 rounded-lg border border-border bg-muted/40 p-3">
      <div className="flex flex-wrap items-center gap-2">
        <p className="min-w-0 flex-1 font-medium">{plural("acc.invite.batchDone", minted.length)}</p>
        <CopyButton text={linkLines(minted)} label={t("acc.invite.copyAll")} />
        <Button
          variant="ghost"
          size="icon-sm"
          title={t("common.close")}
          aria-label={t("common.close")}
          onClick={onDismiss}
        >
          <X />
        </Button>
      </div>
      <p className="text-body">{t("acc.invite.copyMany")}</p>
      <ul className="max-h-72 divide-y divide-border overflow-y-auto rounded-md border border-border bg-background">
        {minted.map(({ invite, link }) => (
          <li key={invite.id} className="flex items-center gap-2 px-2 py-1">
            <span className="w-40 shrink-0 truncate text-small font-medium" title={invite.label ?? undefined}>
              {invite.label ?? "—"}
            </span>
            <code className="min-w-0 flex-1 truncate font-mono text-small">{link}</code>
            <CopyButton text={link} compact />
          </li>
        ))}
      </ul>
      {warning}
    </div>
  );
}

/** What pasting a link back did, in the one of three ways it can go. */
function RecoveredNotice({
  recovered,
  onDismiss,
}: {
  recovered: Recovered;
  onDismiss: () => void;
}) {
  const { t } = useT();
  const { outcome, invite, link, stored } = recovered;
  if (outcome === "created") {
    return (
      <div className="space-y-2">
        <CopyLink link={link} onDismiss={onDismiss}>
          {t("acc.invite.recover.created")}
        </CopyLink>
        {stored === false ? <Alert tone="attention" title={t("acc.invite.notStoredNow")} /> : null}
      </div>
    );
  }
  const name = invite.label || t("acc.invite.linkOf", { date: dateTime(invite.created_at) });
  return (
    <Alert
      tone="info"
      title={t(
        outcome === "recovered" ? "acc.invite.recover.recovered" : "acc.invite.recover.unchanged",
      )}
      action={
        <Button
          variant="ghost"
          size="icon-sm"
          title={t("common.close")}
          aria-label={t("common.close")}
          onClick={onDismiss}
        >
          <X />
        </Button>
      }
    >
      <p>{t("acc.invite.recover.inList", { name })}</p>
    </Alert>
  );
}

/**
 * The invitations nobody has used: pending first, and the expired ones one tab away.
 *
 * The expired ones are kept because a date can be moved and the same link then works
 * again. The tab only exists while there is something expired to show — a switch between
 * a list and an empty one is a control with nothing behind it.
 */
function InviteList({
  rows,
  overview,
  onRecover,
}: {
  rows: InviteRow[];
  overview: AdminOverview;
  onRecover: () => void;
}) {
  const { plural, t } = useT();
  const [filter, setFilter] = useState<InviteState>("pending");
  const [query, setQuery] = useState("");

  const now = Date.now();
  const pending = rows.filter((row) => inviteState(row, now) === "pending");
  const expired = rows.filter((row) => inviteState(row, now) === "expired");
  const current: InviteState = expired.length === 0 ? "pending" : filter;
  const inTab = current === "pending" ? pending : expired;
  const shown = inTab.filter((row) => matchesInvite(row, query));

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-2">
        {expired.length > 0 ? (
          <Tabs
            value={current}
            onChange={(next) => setFilter(next as InviteState)}
            items={[
              {
                value: "pending",
                label: t("acc.invite.tab.pending"),
                badge: <Count n={pending.length} />,
              },
              {
                value: "expired",
                label: t("acc.invite.tab.expired"),
                badge: <Count n={expired.length} />,
              },
            ]}
          />
        ) : (
          <h3 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
            {plural("acc.invite.pendingHeading", pending.length)}
          </h3>
        )}
        {inTab.length > SEARCH_FROM ? (
          <Input
            type="search"
            value={query}
            aria-label={t("acc.invite.search")}
            placeholder={t("acc.invite.search")}
            className="ml-auto w-72"
            onChange={(event) => setQuery(event.target.value)}
          />
        ) : null}
      </div>

      {rows.length === 0 ? (
        <p className="text-small text-muted-foreground">{t("acc.invite.none")}</p>
      ) : shown.length === 0 ? (
        <p className="text-small text-muted-foreground">
          {inTab.length === 0 ? t("acc.invite.nonePending") : t("acc.invite.noMatch")}
        </p>
      ) : (
        <ul className="divide-y divide-border rounded-lg border border-border">
          {shown.map((row) => (
            <InviteItem
              key={row.id}
              row={row}
              expired={current === "expired"}
              overview={overview}
              onRecover={onRecover}
            />
          ))}
        </ul>
      )}
    </div>
  );
}

function Count({ n }: { n: number }) {
  return <span className="nums text-small text-muted-foreground">{n}</span>;
}

type Panel = "link" | "edit" | null;

function InviteItem({
  row,
  expired,
  overview,
  onRecover,
}: {
  row: InviteRow;
  expired: boolean;
  overview: AdminOverview;
  onRecover: () => void;
}) {
  const { t } = useT();
  const confirm = useConfirm();
  const toast = useToast();
  const revoke = useRevokeInvite();
  const [panel, setPanel] = useState<Panel>(null);
  // No addressee to fall back on: an invitation with no alias is told apart by when it was
  // issued, which is what the list said before aliases existed.
  const name = row.label || t("acc.invite.linkOf", { date: dateTime(row.created_at) });
  const toggle = (next: Panel) => setPanel(panel === next ? null : next);

  const remove = async () => {
    const asked = await confirm({
      title: t("acc.invite.revokeConfirm", { name }),
      body: t("acc.invite.revokeConfirmBody"),
      confirmLabel: t("acc.invite.revoke"),
      tone: "danger",
    });
    if (!asked) return;
    revoke.mutate(row.id, {
      onSuccess: () => toast({ title: t("acc.invite.revoked"), description: name, tone: "attention" }),
      onError: (error: Error) =>
        toast({ title: t("acc.invite.revokeFailed"), description: error.message, tone: "danger" }),
    });
  };

  return (
    <li className="space-y-2 p-2">
      {/* The text keeps a floor so that, on a phone, the three actions drop below it as one
          group instead of squeezing it into a column one word wide. */}
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <div className="min-w-64 flex-1">
          <p className="flex min-w-0 items-center gap-1.5">
            <span className={cn("truncate", row.label ? "font-medium" : "text-muted-foreground")}>
              {name}
            </span>
            {expired ? <Badge variant="outline">{t("acc.invite.expiredBadge")}</Badge> : null}
          </p>
          <p className="text-small text-muted-foreground">
            {row.workspace_slug
              ? `${row.workspace ?? row.workspace_slug} · ${t(ROLE_LABEL_KEYS[row.role])}`
              : t("acc.invite.noWorkspaceShort")}
            {" · "}
            {t(expired ? "acc.invite.expiredOn" : "acc.invite.expiresOn", {
              date: dateTime(row.expires_at),
              when: relative(row.expires_at),
            })}
            {row.created_by
              ? ` · ${t("acc.invite.createdByOn", {
                  name: row.created_by,
                  date: dateTime(row.created_at),
                })}`
              : ""}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="ghost"
            size="sm"
            aria-expanded={panel === "link"}
            onClick={() => toggle("link")}
          >
            {panel === "link" ? <EyeOff /> : <Eye />}
            {panel === "link" ? t("acc.invite.hideLink") : t("acc.invite.showLink")}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            aria-expanded={panel === "edit"}
            onClick={() => toggle("edit")}
          >
            <Pencil />
            {t("acc.invite.edit")}
          </Button>
          <Button
            variant="ghost"
            size="icon-sm"
            title={t("acc.invite.revoke")}
            aria-label={t("acc.invite.revoke")}
            disabled={revoke.isPending}
            onClick={remove}
          >
            <Trash2 />
          </Button>
        </div>
      </div>
      {panel === "link" ? (
        <LinkPanel row={row} expired={expired} onRecover={onRecover} />
      ) : null}
      {panel === "edit" ? (
        <EditPanel
          row={row}
          expired={expired}
          overview={overview}
          onClose={() => setPanel(null)}
        />
      ) : null}
    </li>
  );
}

/** An invitation's link, asked for when the panel opens and gone when it closes. */
function LinkPanel({
  row,
  expired,
  onRecover,
}: {
  row: InviteRow;
  expired: boolean;
  onRecover: () => void;
}) {
  const { t } = useT();
  // An API older than the field says nothing, and asking is what finds out.
  const stored = row.link_stored !== false;
  const read = useInviteLink(row.id, stored);

  if (!stored) {
    return (
      <Alert
        tone="attention"
        title={t("acc.invite.notStored")}
        action={
          <Button size="sm" variant="outline" onClick={onRecover}>
            <RotateCcw />
            {t("acc.invite.recoverIt")}
          </Button>
        }
      >
        <p>{t("acc.invite.notStoredBody")}</p>
      </Alert>
    );
  }
  if (read.isError) return <FormError error={read.error} />;
  if (!read.data) return <Spinner />;
  return (
    <CopyLink link={read.data.link}>
      {expired ? t("acc.invite.linkExpired") : t("acc.invite.linkLive")}
    </CopyLink>
  );
}

/** The terms of one invitation, changed in place; only what moved is sent. */
function EditPanel({
  row,
  expired,
  overview,
  onClose,
}: {
  row: InviteRow;
  expired: boolean;
  overview: AdminOverview;
  onClose: () => void;
}) {
  const { t } = useT();
  const toast = useToast();
  const edit = useEditInvite();
  const [draft, setDraft] = useState<TermsDraft>(() => draftOf(row));
  const changes = changesOf(row, draft);
  const dirty = Object.keys(changes).length > 0;
  // An untouched date is not a change, so an expired invitation can be renamed without
  // being made to move it; a touched one has to be a moment still to come.
  const dateTouched = draft.expires !== draftOf(row).expires;
  const dateOk = !dateTouched || isAhead(draft.expires);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!dirty || !dateOk) return;
    edit.mutate(
      { id: row.id, changes },
      {
        onSuccess: () => {
          toast({ title: t("acc.invite.saved"), description: draft.label.trim() || undefined });
          onClose();
        },
      },
    );
  };

  return (
    <form
      noValidate
      onSubmit={submit}
      className="space-y-3 rounded-lg border border-border bg-muted/30 p-3"
    >
      <TermsFields
        draft={draft}
        onChange={setDraft}
        overview={overview}
        idPrefix={`invite-${row.id}`}
        dateNote={
          expired && !dateTouched
            ? t("acc.invite.expiredEditHint", { when: relative(row.expires_at) })
            : undefined
        }
      />
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" size="sm" disabled={!dirty || !dateOk || edit.isPending}>
          {edit.isPending ? <Spinner /> : null}
          {t("acc.invite.save")}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onClose}>
          {t("common.cancel")}
        </Button>
      </div>
      <FormError error={edit.error} />
    </form>
  );
}
