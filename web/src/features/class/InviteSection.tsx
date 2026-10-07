import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Copy, Download, Link2, Pause, Play, QrCode, RefreshCw, Settings2, Trash2, UserPlus, X } from "lucide-react";
import { useMemo, useState, type FormEvent } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Textarea } from "@/components/ui/input";
import { LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { CopyButton, CopyLink } from "@/features/admin/CopyLink";
import { SectionHeader } from "@/features/admin/Sections";
import { api } from "@/lib/api";
import { csvFile, saveCsv } from "@/lib/csv";
import { dateTime, relative } from "@/lib/format";
import { useT, type Key } from "@/lib/i18n";
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
  linkLines,
  namesOf,
  toLocalInput,
  withinTeacherCap,
  type ExpiryPreset,
} from "@/lib/invites";
import { qrDrawing } from "@/lib/qr";
import type { ClassLinkTerms, ClassLinkView, MemberInvite, MintedMemberInvite } from "@/lib/types";
import {
  useClassLink,
  useClassLinkActions,
  useClassLinkUrl,
  useMemberInviteActions,
  useMemberInvites,
} from "@/state/queries";

const PRESET_KEYS: Record<ExpiryPreset, Key> = {
  day: "acc.invite.preset.day",
  week: "acc.invite.preset.week",
  month: "acc.invite.preset.month",
  quarter: "acc.invite.preset.quarter",
};

/**
 * «Invitar»: the two ways a teacher brings students in, each a block.
 *
 * The class link is one link for the whole class, with seats, an expiry and a pause, shown
 * as a QR code to project. Personal invitations are one link per name, handed out by hand
 * or as a CSV. Both make students: a teacher's invitation is an owner's, and not here yet.
 */
export function InviteSection({ subject, slug }: { subject: string; slug: string | null }) {
  const { t } = useT();
  return (
    <>
      <SectionHeader title={t("class.invite")} description={t("class.invite.lead")} />
      <ClassLinkBlock subject={subject} />
      <PersonalInvites slug={slug} />
      <UnusedInvites />
    </>
  );
}

/** The detail the section list reads under «Invitar»: the class link's state in one line. */
export function classLinkDetail(
  link: ClassLinkView | null | undefined,
  t: ReturnType<typeof useT>["t"],
): string {
  if (!link) return t("class.link.none");
  const seats = { uses: link.uses, max: link.max_uses };
  if (link.expired) return t("class.link.detail.expired");
  return t(link.paused ? "class.link.detail.paused" : "class.link.detail.live", seats);
}

/* The class link ------------------------------------------------------------------- */

function ClassLinkBlock({ subject }: { subject: string }) {
  const { t } = useT();
  const read = useClassLink();
  const link = read.data?.class_link ?? null;
  return (
    <section className="surface space-y-4 p-5" aria-labelledby="class-link-title">
      <div className="space-y-1">
        <h3 id="class-link-title" className="text-heading">
          {t("class.link.title")}
        </h3>
        <p className="max-w-3xl text-small text-muted-foreground">{t("class.link.lead")}</p>
      </div>
      {read.isError ? (
        <LoadError title={t("class.link.unreadable")} error={read.error} onRetry={() => read.refetch()} />
      ) : read.isLoading ? (
        <Skeleton className="h-24" />
      ) : link ? (
        <LiveLink link={link} subject={subject} />
      ) : (
        <LinkTerms />
      )}
    </section>
  );
}

/**
 * The live link: how full it is, until when, whether it lets anybody in, the link itself,
 * and what a teacher does with it.
 */
function LiveLink({ link, subject }: { link: ClassLinkView; subject: string }) {
  const { t } = useT();
  const confirm = useConfirm();
  const toast = useToast();
  const url = useClassLinkUrl(link.link_stored);
  const { mint, edit, revoke } = useClassLinkActions();
  const [editing, setEditing] = useState(false);
  const [projecting, setProjecting] = useState(false);
  const text = url.data?.link ?? null;

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
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-body">
        <span className="nums font-medium">
          {t("class.link.seats", { uses: link.uses, max: link.max_uses })}
        </span>
        <span aria-hidden className="text-muted-foreground">·</span>
        <span className="text-muted-foreground">
          {t(link.expired ? "class.link.expiredOn" : "class.link.expiresOn", {
            date: dateTime(link.expires_at),
          })}
        </span>
        <Badge variant={link.expired || link.paused ? "outline" : "settled"}>
          {t(link.expired ? "class.link.state.expired" : link.paused ? "class.link.state.paused" : "class.link.state.live")}
        </Badge>
      </p>

      {!link.link_stored ? (
        <p className="text-small text-muted-foreground">{t("class.link.notStored")}</p>
      ) : url.isError ? (
        <p role="alert" className="text-small text-destructive">
          {(url.error as Error).message}
        </p>
      ) : text === null ? (
        <Spinner />
      ) : (
        <div className="flex flex-wrap items-center gap-2">
          <code className="min-w-0 flex-1 truncate rounded-md bg-sunk px-2 py-1.5 font-mono text-small">
            {text}
          </code>
          <CopyButton text={text} />
          <Button size="sm" variant="outline" onClick={() => setProjecting(true)}>
            <QrCode />
            {t("class.link.showQr")}
          </Button>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        {link.expired ? null : (
          <Button size="sm" variant="outline" disabled={edit.isPending} onClick={() => pause(!link.paused)}>
            {link.paused ? <Play /> : <Pause />}
            {t(link.paused ? "class.link.resume" : "class.link.pause")}
          </Button>
        )}
        <Button size="sm" variant="outline" disabled={mint.isPending} onClick={renew}>
          {mint.isPending ? <Spinner /> : <RefreshCw />}
          {t("class.link.renew")}
        </Button>
        <Button
          size="sm"
          variant="ghost"
          aria-expanded={editing}
          onClick={() => setEditing((open) => !open)}
        >
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

      {editing ? <LinkTerms link={link} onDone={() => setEditing(false)} /> : null}

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
      <div role="group" aria-label={t("acc.invite.quickExpiry")} className="flex flex-wrap gap-1">
        {EXPIRY_PRESETS.map((preset) => (
          <Button
            key={preset.key}
            type="button"
            size="sm"
            variant="ghost"
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

/**
 * One invitation per name typed, a student's each. What was just minted stays on screen —
 * a link per name, «Copiar todo» and a CSV — until it is put away: a link is a credential.
 */
function PersonalInvites({ slug }: { slug: string | null }) {
  const { t, plural } = useT();
  const toast = useToast();
  const { mint } = useMemberInviteActions();
  const [text, setText] = useState("");
  const [expires, setExpires] = useState(toLocalInput(inDays(TEACHER_INVITE_DEFAULT_DAYS)));
  const [tried, setTried] = useState(false);
  const [minted, setMinted] = useState<MintedMemberInvite[] | null>(null);
  const names = namesOf(text);
  const dateOk = isAhead(expires) && withinTeacherCap(expires);
  const problem =
    names.length === 0
      ? t("class.invites.noNames")
      : names.length > BATCH_MAX
        ? t("class.invites.tooMany", { max: BATCH_MAX })
        : !dateOk
          ? t("class.expiryBounds", { days: TEACHER_LINK_MAX_DAYS })
          : null;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    setTried(true);
    const moment = fromLocalInput(expires);
    if (problem || moment === null) return;
    mint.mutate(
      { names, expires_at: moment.toISOString() },
      {
        onSuccess: ({ invites }) => {
          setMinted(invites);
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
    <section className="surface space-y-4 p-5" aria-labelledby="class-invites-title">
      <div className="space-y-1">
        <h3 id="class-invites-title" className="text-heading">
          {t("class.invites.title")}
        </h3>
        <p className="max-w-3xl text-small text-muted-foreground">{t("class.invites.lead")}</p>
      </div>

      <form onSubmit={submit} className="space-y-3">
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
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <ExpiryField id="class-invites" value={expires} onChange={setExpires} />
        </div>
        {tried && problem ? (
          <p role="alert" className="text-small text-destructive">
            {problem}
          </p>
        ) : null}
        <Button type="submit" size="sm" disabled={mint.isPending}>
          {mint.isPending ? <Spinner /> : <UserPlus />}
          {names.length > 0 ? plural("class.invites.createN", names.length) : t("class.invites.create")}
        </Button>
      </form>

      {minted && minted.length > 0 ? (
        <MintedInvites minted={minted} slug={slug} onDismiss={() => setMinted(null)} />
      ) : null}
    </section>
  );
}

/** The links just minted: one row per name with its own copy, and the batch copied or saved whole. */
function MintedInvites({
  minted,
  slug,
  onDismiss,
}: {
  minted: MintedMemberInvite[];
  slug: string | null;
  onDismiss: () => void;
}) {
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
    <div className="well space-y-3 rounded-inner p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="min-w-0 flex-1 text-body">{t("class.invites.handOver")}</p>
        <CopyButton text={linkLines(minted)} label={t("class.invites.copyAll")} />
        <Button
          size="sm"
          variant="outline"
          onClick={() => saveCsv(t("class.csv.file", { slug: slug ?? "clase" }), csv())}
        >
          <Download />
          {t("class.invites.csv")}
        </Button>
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
      <ul className="rows">
        {minted.map(({ invite, link }) => (
          <li key={invite.id} className="flex items-center gap-2 py-1.5">
            <span className="w-48 shrink-0 truncate font-medium">{invite.label}</span>
            <code className="min-w-0 flex-1 truncate font-mono text-small text-muted-foreground">{link}</code>
            <CopyButton text={link} compact />
          </li>
        ))}
      </ul>
    </div>
  );
}

/** The subject's personal invitations nobody has used yet: copy one again, or withdraw it. */
function UnusedInvites() {
  const { t } = useT();
  const read = useMemberInvites();
  const rows = read.data?.invites ?? [];
  if (read.isLoading) return null;
  if (read.isError) {
    return (
      <LoadError title={t("class.invites.unreadable")} error={read.error} onRetry={() => read.refetch()} />
    );
  }
  if (rows.length === 0) return null;
  return (
    <section className="surface space-y-3 p-5" aria-labelledby="class-unused-title">
      <h3 id="class-unused-title" className="flex items-baseline gap-2 text-heading">
        {t("class.invites.unused")}
        <span className="nums text-small font-normal text-muted-foreground">{rows.length}</span>
      </h3>
      <ul className="rows">
        {rows.map((row) => (
          <UnusedRow key={row.id} row={row} />
        ))}
      </ul>
    </section>
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
    <li className="space-y-2 py-2">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <div className="min-w-48 flex-1">
          <p className="flex flex-wrap items-center gap-1.5">
            <span className="truncate font-medium">{name}</span>
            {expired ? <Badge variant="outline">{t("class.invites.expiredBadge")}</Badge> : null}
          </p>
          <p className="text-small text-muted-foreground">
            {t(expired ? "class.link.expiredOn" : "class.link.expiresOn", { date: dateTime(row.expires_at) })}
            {row.created_by ? ` · ${t("class.invitedBy", { name: row.created_by })}` : ""}
          </p>
        </div>
        <div className="ml-auto flex items-center gap-1">
          {expired || row.link_stored === false ? null : (
            <Button size="sm" variant="ghost" onClick={copy}>
              <Copy />
              {t("acc.copy")}
            </Button>
          )}
          <Button
            variant="ghost"
            size="icon-sm"
            title={t("class.invites.delete")}
            aria-label={t("class.invites.delete")}
            disabled={revoke.isPending}
            onClick={remove}
          >
            <Trash2 />
          </Button>
        </div>
      </div>
      {shown ? <ShownLink id={row.id} onDismiss={() => setShown(false)} /> : null}
    </li>
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
