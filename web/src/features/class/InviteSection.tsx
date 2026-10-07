import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Download, Link2, Maximize2, Pause, Play, QrCode, RefreshCw, Settings2, Trash2, UserPlus } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import { ChoicePill } from "@/components/ui/choice";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Textarea } from "@/components/ui/input";
import { LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { PersonName } from "@/components/ui/person";
import { useRadioGroup } from "@/components/ui/radio";
import { RowAction, RowGestures, TD, TR } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { CopyButton, CopyLink, LinkTable } from "@/features/admin/CopyLink";
import { SectionHeader } from "@/features/admin/Sections";
import { api } from "@/lib/api";
import { csvFile, saveCsv } from "@/lib/csv";
import { dateTime, relative, when } from "@/lib/format";
import { useT, type Key, type Translate } from "@/lib/i18n";
import {
  BATCH_MAX,
  CLASS_LINK_DEFAULT_DAYS,
  CLASS_LINK_DEFAULT_SEATS,
  CLASS_LINK_MAX_SEATS,
  EXPIRY_PRESETS,
  TEACHER_INVITE_DEFAULT_DAYS,
  TEACHER_LINK_MAX_DAYS,
  fromLocalInput,
  inDays,
  inviteState,
  isAhead,
  isEmail,
  linkLines,
  recipientsOf,
  toLocalInput,
  withinTeacherCap,
  type ExpiryPreset,
} from "@/lib/invites";
import { qrDrawing } from "@/lib/qr";
import type { ClassLinkTerms, ClassLinkView, MemberInvite, MintedMemberInvite, Role } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useIsOwner, useSession } from "@/state/auth";
import {
  useClassLink,
  useClassLinkActions,
  useClassLinkUrl,
  useMemberInviteActions,
  useMemberInvites,
} from "@/state/queries";

import { PEOPLE_COLUMNS, PeopleTable } from "./PersonRow";

const PRESET_KEYS: Record<ExpiryPreset, Key> = {
  day: "acc.invite.preset.day",
  week: "acc.invite.preset.week",
  month: "acc.invite.preset.month",
  quarter: "acc.invite.preset.quarter",
};

/**
 * «Invitar»: the two ways a teacher brings people in, each a block of one page under «Miembros»
 * (user's requests, 2026-10-07: first a page each and a page of the unused ones, then one page
 * again, drawn anew).
 *
 * «Invitación general» is the class link: one link for the whole class, its QR code beside it
 * to project, a bar of the seats taken and left, the link to copy, and a quiet row of what a
 * teacher does with it. «Invitaciones personales» is the list of the ones nobody has used yet,
 * drawn as the people of the class are; «Nuevas invitaciones» opens the form in a dialog, which
 * then hands over what it made.
 */
export function InviteSection({ subject, slug }: { subject: string; slug: string | null }) {
  const { t } = useT();
  return (
    <>
      <SectionHeader title={t("class.invite")} description={t("class.invite.lead")} />
      <GeneralInvite subject={subject} />
      <PersonalInvites slug={slug} />
    </>
  );
}

/** The line under «Invitar» in the section list: the general invitation's state, and the unused. */
export function inviteDetail(link: ClassLinkView | null | undefined, rows: MemberInvite[], tr: Translate): string {
  const { t, plural } = tr;
  const general = !link
    ? t("class.invite.general.none")
    : link.expired
      ? t("class.invite.general.expired")
      : t(link.paused ? "class.invite.general.paused" : "class.invite.general.live");
  return rows.length > 0 ? `${general} · ${plural("class.invites.detail", rows.length)}` : general;
}

/* The general invitation (the class link) ------------------------------------------ */

/** «Invitación general»: the subject's class link, or the form that creates it. */
function GeneralInvite({ subject }: { subject: string }) {
  const { t } = useT();
  const read = useClassLink();
  const link = read.data?.class_link ?? null;
  return (
    <section className="surface space-y-4 p-5" aria-labelledby="class-general-title">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h3 id="class-general-title" className="text-heading">
            {t("class.link.title")}
          </h3>
          <p className="text-small text-muted-foreground">{t("class.link.lead")}</p>
        </div>
        {link ? (
          <Badge variant={link.expired || link.paused ? "outline" : "settled"}>
            {t(link.expired ? "class.link.state.expired" : link.paused ? "class.link.state.paused" : "class.link.state.live")}
          </Badge>
        ) : null}
      </div>
      {read.isError ? (
        <LoadError title={t("class.link.unreadable")} error={read.error} onRetry={() => read.refetch()} />
      ) : read.isLoading ? (
        <Skeleton className="h-36" />
      ) : link ? (
        <LiveLink link={link} subject={subject} />
      ) : (
        <LinkTerms />
      )}
    </section>
  );
}

/**
 * The live link: its QR code, how full it is and until when, the link itself, and what a
 * teacher does with it — pause, renew, change its terms, and, apart, delete it.
 */
function LiveLink({ link, subject }: { link: ClassLinkView; subject: string }) {
  const { t, plural } = useT();
  const confirm = useConfirm();
  const toast = useToast();
  const url = useClassLinkUrl(link.link_stored);
  const { mint, edit, revoke } = useClassLinkActions();
  const [editing, setEditing] = useState(false);
  const [projecting, setProjecting] = useState(false);
  const text = url.data?.link ?? null;
  const drawing = useMemo(() => (text ? qrDrawing(text) : null), [text]);
  const free = Math.max(0, link.max_uses - link.uses);
  const filled = link.max_uses > 0 ? Math.min(100, (100 * link.uses) / link.max_uses) : 0;

  const failed = (error: Error) =>
    toast({ title: t("class.failed"), description: error.message, tone: "danger" });

  const renew = async () => {
    const asked = await confirm({
      title: t("class.link.renewConfirm"),
      body: t("class.link.renewConfirmBody"),
      confirmLabel: t("class.link.renew"),
    });
    if (!asked) return;
    // The same seats and the same date, on a new link; a date already gone takes the default.
    mint.mutate(
      { max_uses: link.max_uses, expires_at: link.expired ? null : link.expires_at },
      { onSuccess: () => toast({ title: t("class.link.renewed") }), onError: failed },
    );
  };

  const remove = async () => {
    const asked = await confirm({
      title: t("class.link.deleteConfirm"),
      body: t("class.link.deleteConfirmBody"),
      confirmLabel: t("class.link.delete"),
      tone: "danger",
    });
    if (!asked) return;
    revoke.mutate(undefined, { onSuccess: () => toast({ title: t("class.link.deleted") }), onError: failed });
  };

  const pause = (paused: boolean) =>
    edit.mutate(
      { paused },
      {
        onSuccess: () => toast({ title: t(paused ? "class.link.pausedToast" : "class.link.resumedToast") }),
        onError: failed,
      },
    );

  return (
    <div className="space-y-4">
      <div className="grid gap-5 sm:grid-cols-[8.5rem_minmax(0,1fr)] sm:items-start">
        {/* The code itself, small: pressed, it opens big enough to project. */}
        <button
          type="button"
          disabled={drawing === null}
          onClick={() => setProjecting(true)}
          aria-label={t("class.link.showQr")}
          title={t("class.link.showQr")}
          className={cn(
            "well group flex w-34 flex-col items-center gap-1.5 rounded-inner p-2.5 transition-colors",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            drawing && "hover:bg-accent",
          )}
        >
          {drawing ? (
            <svg
              viewBox={`0 0 ${drawing.size} ${drawing.size}`}
              aria-hidden
              shapeRendering="crispEdges"
              className="block size-28 rounded-md bg-qr text-qr-foreground"
            >
              <path d={drawing.path} fill="currentColor" />
            </svg>
          ) : (
            <span className="flex size-28 items-center justify-center text-muted-foreground">
              {link.link_stored && !url.isError ? <Spinner /> : <QrCode className="size-8" />}
            </span>
          )}
          <span className="flex items-center gap-1 text-small text-muted-foreground group-hover:text-foreground">
            <Maximize2 className="size-3" />
            {t("class.link.project")}
          </span>
        </button>

        <div className="min-w-0 space-y-4">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-3 text-small">
              <span className="nums font-medium">{t("class.link.seats", { uses: link.uses, max: link.max_uses })}</span>
              {link.expired ? null : (
                <span className="nums text-muted-foreground">{plural("class.link.free", free)}</span>
              )}
            </div>
            <div
              role="meter"
              aria-label={t("class.link.seatsLabel")}
              aria-valuemin={0}
              aria-valuemax={link.max_uses}
              aria-valuenow={link.uses}
              className="h-2 overflow-hidden rounded-full bg-muted"
            >
              <span className="block h-full rounded-full bg-ink" style={{ width: `${filled}%` }} />
            </div>
            <p className="text-small text-muted-foreground">
              {t(link.expired ? "class.link.expiredOn" : "class.link.expiresOn", { date: dateTime(link.expires_at) })}
            </p>
          </div>

          {!link.link_stored ? (
            <p className="text-small text-muted-foreground">{t("class.link.notStored")}</p>
          ) : url.isError ? (
            <p role="alert" className="text-small text-destructive">
              {(url.error as Error).message}
            </p>
          ) : text === null ? (
            <Skeleton className="h-9" />
          ) : (
            <div className="flex items-center gap-2">
              <code className="min-w-0 flex-1 truncate rounded-md bg-sunk px-2.5 py-2 font-mono text-small" title={text}>
                {text}
              </code>
              <CopyButton text={text} />
            </div>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1 border-t border-border pt-3">
        {link.expired ? null : (
          <Button size="sm" variant="ghost" disabled={edit.isPending} onClick={() => pause(!link.paused)}>
            {link.paused ? <Play /> : <Pause />}
            {t(link.paused ? "class.link.resume" : "class.link.pause")}
          </Button>
        )}
        <Button size="sm" variant="ghost" disabled={mint.isPending} onClick={renew}>
          {mint.isPending ? <Spinner /> : <RefreshCw />}
          {t("class.link.renew")}
        </Button>
        <Button size="sm" variant="ghost" aria-expanded={editing} onClick={() => setEditing((open) => !open)}>
          <Settings2 />
          {t("class.link.change")}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          className="ml-auto text-destructive hover:text-destructive"
          disabled={revoke.isPending}
          onClick={remove}
        >
          {revoke.isPending ? <Spinner /> : <Trash2 />}
          {t("class.link.delete")}
        </Button>
      </div>

      {editing ? (
        <div className="well rounded-inner p-4">
          <LinkTerms link={link} onDone={() => setEditing(false)} />
        </div>
      ) : null}

      <QrDialog open={projecting && text !== null} link={text} subject={subject} onClose={() => setProjecting(false)} />
    </div>
  );
}

/**
 * A class link's seats and date: the form that mints the first one, and the one that
 * changes the live one's. Only what moved is sent; its seats never go under the ones taken.
 */
function LinkTerms({ link, onDone }: { link?: ClassLinkView; onDone?: () => void }) {
  const { t } = useT();
  const toast = useToast();
  const { mint, edit } = useClassLinkActions();
  const initialDate = toLocalInput(link ? new Date(link.expires_at) : inDays(CLASS_LINK_DEFAULT_DAYS));
  const [seats, setSeats] = useState(String(link?.max_uses ?? CLASS_LINK_DEFAULT_SEATS));
  const [expires, setExpires] = useState(initialDate);
  const [tried, setTried] = useState(false);
  const floor = Math.max(1, link?.uses ?? 0);
  const count = Number(seats);
  const seatsOk = Number.isInteger(count) && count >= floor && count <= CLASS_LINK_MAX_SEATS;
  const dateOk = isAhead(expires) && withinTeacherCap(expires);
  const busy = mint.isPending || edit.isPending;
  const id = link ? "class-link-edit" : "class-link-new";

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setTried(true);
    const moment = fromLocalInput(expires);
    if (!seatsOk || !dateOk || moment === null) return;
    const failed = (error: Error) =>
      toast({ title: t("class.failed"), description: error.message, tone: "danger" });
    if (!link) {
      mint.mutate(
        { max_uses: count, expires_at: moment.toISOString() },
        { onSuccess: () => toast({ title: t("class.link.created") }), onError: failed },
      );
      return;
    }
    const changes: ClassLinkTerms = {};
    if (count !== link.max_uses) changes.max_uses = count;
    if (expires !== initialDate) changes.expires_at = moment.toISOString();
    if (Object.keys(changes).length === 0) {
      onDone?.();
      return;
    }
    edit.mutate(changes, {
      onSuccess: () => {
        toast({ title: t("class.link.changed") });
        onDone?.();
      },
      onError: failed,
    });
  };

  return (
    <form onSubmit={submit} className="space-y-3">
    <div className="flex flex-wrap items-end gap-3">
      <div className="space-y-1">
        <Label htmlFor={`${id}-seats`}>{t("class.link.seatsLabel")}</Label>
        <Input
          id={`${id}-seats`}
          type="number"
          inputMode="numeric"
          min={floor}
          max={CLASS_LINK_MAX_SEATS}
          value={seats}
          aria-invalid={tried && !seatsOk}
          className="w-28"
          onChange={(event) => setSeats(event.target.value)}
        />
      </div>
      <ExpiryField id={id} value={expires} onChange={setExpires} />
    </div>
    <p className={tried && !(seatsOk && dateOk) ? "text-small text-destructive" : "text-small text-muted-foreground"}>
      {tried && !seatsOk
        ? t("class.link.seatsBounds", { min: floor, max: CLASS_LINK_MAX_SEATS })
        : tried && !dateOk
          ? t("class.expiryBounds", { days: TEACHER_LINK_MAX_DAYS })
          : t("class.expiresIn", { when: relative((fromLocalInput(expires) ?? new Date()).toISOString()) })}
    </p>
    <div className="flex flex-wrap items-center gap-2">
      <Button type="submit" size="sm" disabled={busy}>
        {busy ? <Spinner /> : link ? null : <Link2 />}
        {link ? t("common.save") : t("class.link.create")}
      </Button>
      {link ? (
        <Button type="button" size="sm" variant="ghost" onClick={onDone}>
          {t("common.cancel")}
        </Button>
      ) : null}
    </div>
  </form>
);
}

/** The date a link stops working: the picker, and the quick choices beside it. */
function ExpiryField({
id,
value,
onChange,
}: {
id: string;
value: string;
onChange: (next: string) => void;
}) {
const { t } = useT();
return (
  <>
    <div className="space-y-1">
      <Label htmlFor={`${id}-expires`}>{t("class.expiresAt")}</Label>
      <Input
        id={`${id}-expires`}
        type="datetime-local"
        value={value}
        min={toLocalInput(new Date())}
        max={toLocalInput(inDays(TEACHER_LINK_MAX_DAYS))}
        className="w-56"
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
    {/* The shortcuts as the administrator's form draws them: outline buttons, level with
        the date beside them. */}
    <div role="group" aria-label={t("acc.invite.quickExpiry")} className="flex flex-wrap gap-2">
      {EXPIRY_PRESETS.map((preset) => (
        <Button
          key={preset.key}
          type="button"
          variant="outline"
          onClick={() => onChange(toLocalInput(inDays(preset.days)))}
        >
          {t(PRESET_KEYS[preset.key])}
        </Button>
      ))}
    </div>
  </>
);
}

/**
 * The class link as a QR code, big enough to project: drawn in the browser as one SVG path,
 * dark on light in either theme (`--qr`), with the link written under it for whoever types.
 */
function QrDialog({
open,
link,
subject,
onClose,
}: {
open: boolean;
link: string | null;
subject: string;
onClose: () => void;
}) {
const { t } = useT();
const drawing = useMemo(() => (link ? qrDrawing(link) : null), [link]);
return (
  <Dialog open={open} onClose={onClose} title={t("class.link.qrTitle", { subject })} className="max-w-3xl">
    {drawing ? (
      <div className="flex flex-col items-center gap-4">
        <div className="well w-full max-w-[min(64vh,34rem)] rounded-inner p-3">
          <svg
            viewBox={`0 0 ${drawing.size} ${drawing.size}`}
            role="img"
            aria-label={t("class.link.qrLabel", { subject })}
            shapeRendering="crispEdges"
            className="block h-auto w-full rounded-md bg-qr text-qr-foreground"
          >
            <path d={drawing.path} fill="currentColor" />
          </svg>
        </div>
        <p className="max-w-full break-all text-center font-mono text-body">{link}</p>
      </div>
    ) : null}
  </Dialog>
);
}

/* Personal invitations -------------------------------------------------------------- */

const INVITE_ROLES: Role[] = ["viewer", "editor"];

/**
 * «Invitaciones personales»: the ones nobody has used yet, drawn as the people of the class
 * are, and «Nuevas invitaciones», which opens the form in a dialog.
 */
function PersonalInvites({ slug }: { slug: string | null }) {
const { t } = useT();
const read = useMemberInvites();
const rows = read.data?.invites ?? [];
const [creating, setCreating] = useState(false);
return (
  <section className="surface space-y-4 p-5" aria-labelledby="class-personal-title">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0 space-y-1">
        <h3 id="class-personal-title" className="text-heading">
          {t("class.invites.title")}
        </h3>
        <p className="text-small text-muted-foreground">{t("class.invites.lead")}</p>
      </div>
      <Button size="sm" variant="outline" onClick={() => setCreating(true)}>
        <UserPlus />
        {t("class.invites.new")}
      </Button>
    </div>
    {read.isLoading ? (
      <Skeleton className="h-24" />
    ) : read.isError ? (
      <LoadError title={t("class.invites.unreadable")} error={read.error} onRetry={() => read.refetch()} />
    ) : rows.length === 0 ? (
      <p className="text-small text-muted-foreground">{t("class.invites.noneUnused")}</p>
    ) : (
      <PeopleTable
        label={t("class.invites.title")}
        captions={{ name: t("class.col.invitee"), how: t("class.col.invitedBy"), since: t("class.col.expires") }}
      >
        {rows.map((row) => (
          <UnusedRow key={row.id} row={row} />
        ))}
      </PeopleTable>
    )}
    <NewInvites open={creating} slug={slug} onClose={() => setCreating(false)} />
  </section>
);
}

/**
 * «Nuevas invitaciones», a dialog: the form, then — once made — the links it made, to copy one
 * by one, all at once or as a CSV, until the teacher closes it (a link is a credential).
 */
function NewInvites({ open, slug, onClose }: { open: boolean; slug: string | null; onClose: () => void }) {
const { t } = useT();
const [minted, setMinted] = useState<MintedMemberInvite[] | null>(null);
const close = () => {
  setMinted(null);
  onClose();
};
return (
  <Dialog
    open={open}
    onClose={close}
    title={t("class.invites.new")}
    description={minted ? t("class.invites.handOver") : t("class.invites.formLead")}
    className="max-w-2xl"
    footer={
      minted ? (
        <Button onClick={close}>{t("class.invites.done")}</Button>
      ) : null
    }
  >
    {minted ? <MintedInvites minted={minted} slug={slug} /> : <InviteForm onMinted={setMinted} onCancel={close} />}
  </Dialog>
);
}

/**
 * One invitation per name typed, a student's each — or, for an owner who chooses «Docentes»,
 * a teacher's. Where the installation sends mail a line may be «Nombre <correo>»: its link
 * goes there, and the address is kept nowhere. What was just minted stays on screen — a link
 * per name, whether its mail left, «Copiar todo» and a CSV — until it is put away: a link is
 * a credential.
 */
function InviteForm({
onMinted,
onCancel,
}: {
onMinted: (invites: MintedMemberInvite[]) => void;
onCancel: () => void;
}) {
const { t, plural } = useT();
const toast = useToast();
const owner = useIsOwner();
const mailing = useSession().data?.mail_configured === true;
const { mint } = useMemberInviteActions();
const [text, setText] = useState("");
const [role, setRole] = useState<Role>("viewer");
const radios = useRadioGroup(INVITE_ROLES, role, setRole);
const [expires, setExpires] = useState(toLocalInput(inDays(TEACHER_INVITE_DEFAULT_DAYS)));
const [tried, setTried] = useState(false);
const recipients = recipientsOf(text);
const names = recipients.map((recipient) => recipient.name);
const unnamed = recipients.find((recipient) => !recipient.name);
const addressed = recipients.filter((recipient) => recipient.email !== null);
const badAddress = addressed.find((recipient) => !isEmail(recipient.email ?? ""));
const dateOk = isAhead(expires) && withinTeacherCap(expires);
const problem =
  names.length === 0
    ? t("class.invites.noNames")
    : names.length > BATCH_MAX
      ? t("class.invites.tooMany", { max: BATCH_MAX })
      : unnamed
        ? t("class.invites.noNames")
        : addressed.length > 0 && !mailing
          ? t("class.invites.noMail")
          : badAddress
            ? t("class.invites.badEmail", { line: badAddress.line })
            : !dateOk
              ? t("class.expiryBounds", { days: TEACHER_LINK_MAX_DAYS })
              : null;

const submit = (event: FormEvent) => {
  event.preventDefault();
  setTried(true);
  const moment = fromLocalInput(expires);
  if (problem || moment === null) return;
  mint.mutate(
    {
      names,
      expires_at: moment.toISOString(),
      role: owner ? role : "viewer",
      ...(addressed.length > 0 ? { emails: recipients.map((recipient) => recipient.email) } : {}),
    },
    {
      onSuccess: ({ invites }) => {
        onMinted(invites);
        setText("");
        setTried(false);
        toast({ title: plural("class.invites.created", invites.length) });
      },
      onError: (error: Error) =>
        toast({ title: t("class.failed"), description: error.message, tone: "danger" }),
    },
  );
};

return (
  <form onSubmit={submit} className="space-y-3">
      {owner ? (
        <div className="space-y-1">
          <p id="class-invites-role" className="text-micro font-condensed uppercase text-muted-foreground">
            {t("class.invites.role")}
          </p>
          <div role="radiogroup" aria-labelledby="class-invites-role" className="flex flex-wrap gap-2" {...radios.group}>
            {INVITE_ROLES.map((choice) => {
              const chosen = choice === role;
              return (
                <ChoicePill key={choice} {...radios.radio(choice)} chosen={chosen} onClick={() => setRole(choice)}>
                  {t(choice === "editor" ? "class.invites.role.editor" : "class.invites.role.viewer")}
                </ChoicePill>
              );
            })}
          </div>
        </div>
      ) : null}
      <div className="space-y-1">
        <Label htmlFor="class-invites-names">{t("class.invites.names")}</Label>
        <Textarea
          id="class-invites-names"
          rows={5}
          value={text}
          placeholder={t("class.invites.namesPlaceholder")}
          aria-invalid={tried && problem !== null && names.length === 0}
          className="max-w-xl"
          onChange={(event) => setText(event.target.value)}
        />
        {mailing ? (
          <p className="max-w-xl text-small text-muted-foreground">{t("class.invites.mailHint")}</p>
        ) : null}
      </div>
      <div className="flex flex-wrap items-end gap-3">
        <ExpiryField id="class-invites" value={expires} onChange={setExpires} />
      </div>
      {tried && problem ? (
        <p role="alert" className="text-small text-destructive">
          {problem}
        </p>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <Button type="submit" size="sm" disabled={mint.isPending}>
          {mint.isPending ? <Spinner /> : <UserPlus />}
          {names.length > 0 ? plural("class.invites.createN", names.length) : t("class.invites.create")}
        </Button>
        <Button type="button" size="sm" variant="ghost" onClick={onCancel}>
          {t("common.cancel")}
        </Button>
      </div>
    </form>
  );
}

/** The links just minted: one row per name with its own copy, and the batch copied or saved whole. */
function MintedInvites({ minted, slug }: { minted: MintedMemberInvite[]; slug: string | null }) {
  const { t } = useT();
  const csv = () =>
    csvFile(
      [t("class.csv.name"), t("class.csv.link"), t("class.csv.expires")],
      minted.map(({ invite, link }) => [
        invite.label ?? "",
        link,
        toLocalInput(new Date(invite.expires_at)).replace("T", " "),
      ]),
    );
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <CopyButton text={linkLines(minted)} label={t("class.invites.copyAll")} />
        <Button
          size="sm"
          variant="outline"
          onClick={() => saveCsv(t("class.csv.file", { slug: slug ?? "clase" }), csv())}
        >
          <Download />
          {t("class.invites.csv")}
        </Button>
      </div>
      <LinkTable
        label={t("class.invites.title")}
        rows={minted.map(({ invite, link, sent }) => ({
          id: invite.id,
          label: invite.label,
          link,
          teacher: invite.role === "editor",
          sent,
        }))}
      />
    </div>
  );
}

const linkKey = (id: number) => ["members", "invite-link", id] as const;

/**
 * One unused invitation. «Copiar» reads its link — a logged read — and puts it on the
 * clipboard in the same gesture; where the browser refuses a copy that waited for the
 * network, the link opens under the row with a button of its own.
 */
function UnusedRow({ row }: { row: MemberInvite }) {
  const { t } = useT();
  const client = useQueryClient();
  const confirm = useConfirm();
  const toast = useToast();
  const { revoke } = useMemberInviteActions();
  const [shown, setShown] = useState(false);
  const expired = inviteState(row) === "expired";
  const name = row.label || t("class.invites.unnamed");

  const read = () =>
    client
      .fetchQuery({ queryKey: linkKey(row.id), queryFn: () => api.memberInviteLink(row.id), staleTime: Infinity })
      .then(({ link }) => link);

  const copy = async () => {
    if (await copyFetched(read)) toast({ title: t("class.invites.copied"), description: name });
    else setShown(true);
  };

  const remove = async () => {
    const asked = await confirm({
      title: t("class.invites.deleteConfirm", { name }),
      body: t("class.invites.deleteConfirmBody"),
      confirmLabel: t("class.invites.delete"),
      tone: "danger",
    });
    if (!asked) return;
    revoke.mutate(row.id, {
      onError: (error: Error) =>
        toast({ title: t("class.failed"), description: error.message, tone: "danger" }),
    });
  };

  return (
    <>
      <TR className="group h-11">
        <TD>
          <PersonName
            name={name}
            badges={
              <>
                {row.role === "editor" ? (
                  <Badge variant="outline" className="shrink-0">
                    {t("class.invites.teacherBadge")}
                  </Badge>
                ) : null}
                {expired ? (
                  <Badge variant="outline" className="shrink-0">
                    {t("class.invites.expiredBadge")}
                  </Badge>
                ) : null}
              </>
            }
          />
        </TD>
        <TD className={cn(PEOPLE_COLUMNS.how, "truncate text-muted-foreground")}>
          {row.created_by ? t("class.invitedBy", { name: row.created_by }) : "—"}
        </TD>
        <TD className={cn(PEOPLE_COLUMNS.since, "nums text-muted-foreground")}>{when(row.expires_at)}</TD>
        <TD className="py-1.5">
          {/* Copying stays in sight: it is what this list is for. Deleting shows on hover. */}
          <RowGestures
            always={
              expired || row.link_stored === false ? null : (
                <RowAction label={t("class.invites.copyOne", { name })} title={t("acc.copy")} icon={<Copy />} onClick={copy} />
              )
            }
          >
            <RowAction
              label={t("class.invites.deleteOne", { name })}
              title={t("class.invites.delete")}
              icon={<Trash2 />}
              disabled={revoke.isPending}
              onClick={remove}
              danger
            />
          </RowGestures>
        </TD>
      </TR>
      {shown ? (
        <TR>
          <TD colSpan={4} className="pb-3 pt-0">
            <div className="well rounded-inner p-3">
              <ShownLink id={row.id} onDismiss={() => setShown(false)} />
            </div>
          </TD>
        </TR>
      ) : null}
    </>
  );
}

/** An invitation's link under its row, for a browser that would not copy it unasked. */
function ShownLink({ id, onDismiss }: { id: number; onDismiss: () => void }) {
  const { t } = useT();
  const read = useQuery({
    queryKey: linkKey(id),
    queryFn: () => api.memberInviteLink(id),
    staleTime: Infinity,
    retry: false,
  });
  if (read.isError) {
    return (
      <p role="alert" className="text-small text-destructive">
        {(read.error as Error).message}
      </p>
    );
  }
  if (!read.data) return <Spinner />;
  return (
    <CopyLink link={read.data.link} onDismiss={onDismiss}>
      {t("class.invites.linkHere")}
    </CopyLink>
  );
}

/**
 * Put text that has to be fetched first on the clipboard, inside the press that asked for
 * it: a `ClipboardItem` holding the promise keeps the gesture for browsers that demand one.
 * False when the browser refuses or the read fails, so the caller can show the link instead.
 */
async function copyFetched(read: () => Promise<string>): Promise<boolean> {
  try {
    if (typeof ClipboardItem !== "undefined" && navigator.clipboard?.write) {
      const blob = read().then((text) => new Blob([text], { type: "text/plain" }));
      await navigator.clipboard.write([new ClipboardItem({ "text/plain": blob })]);
    } else {
      await navigator.clipboard.writeText(await read());
    }
    return true;
  } catch {
    return false;
  }
}
