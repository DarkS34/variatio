import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  ChevronRight,
  KeyRound,
  Languages,
  Library,
  Trash2,
  UserRound,
  X,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { WorkspaceContext } from "@/features/context/WorkspaceContext";
import { useToast } from "@/components/ui/toast";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Dialog } from "@/components/ui/dialog";
import { GuideLink } from "@/components/GuideLink";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label } from "@/components/ui/input";
import { Alert, Skeleton, Spinner } from "@/components/ui/misc";
import { useRadioGroup } from "@/components/ui/radio";
import { Tabs } from "@/components/ui/tabs";
import { FormError } from "@/features/auth/AuthLayout";
import { SubjectExercises } from "@/features/generations/GenerationsPanel";
import { LANGUAGES, LANGUAGE_NAMES, useT, type Key, type Language } from "@/lib/i18n";
import { useRouter } from "@/lib/router";
import { cn } from "@/lib/utils";
import {
  ROLE_LABEL_KEYS,
  useChangePassword,
  useSession,
  useSetLanguage,
  useUpdateProfile,
} from "@/state/auth";
import {
  useActiveWorkspace,
  useDeleteWorkspace,
  useSwitchWorkspace,
  useWorkspaces,
} from "@/state/queries";
import type { WorkspaceRow } from "@/lib/types";

/**
 * Everything that belongs to the person using the app, in one page: one tab per question.
 *
 * None of it is a step of the chain — the navbar is the chain — so none of it belongs in
 * the navbar. There is deliberately no list of open sessions: this is a closed group with
 * accounts handed out by hand, and changing the password already revokes every other
 * session in the same transaction.
 *
 * The tab lives in the URL and not in state, so each stays a link that can be sent,
 * bookmarked and reloaded.
 */
export const ACCOUNT_TABS = [
  { value: "cuenta", label: "tabs.account", path: "/account" },
  // One tab for the subjects and the exercises: an exercise is saved inside the subject it
  // was generated in, so each subject opens its own beside the list.
  { value: "workspaces", label: "tabs.workspaces", path: "/account/workspaces" },
] as const satisfies readonly { value: string; label: Key; path: string }[];

export type AccountTab = (typeof ACCOUNT_TABS)[number]["value"];

export function AccountScreen({ tab }: { tab: AccountTab }) {
  const { t } = useT();
  const session = useSession();
  const { navigate } = useRouter();
  const user = session.data?.user;

  if (!user) return <Skeleton className="h-96" />;

  return (
    <div className="space-y-5">
      {/* Three lines, and who you are is the third: the title, its (i) and the guide link
          are about the SCREEN, while the username and the administrator badge are about the
          ACCOUNT it is showing. In one flow the identity wraps onto the guide link's line
          and reads as part of it. */}
      <header className="space-y-1.5">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1.5">
          <h1 className="font-display font-expanded text-display">{t("account.title")}</h1>
          <InfoHint label={t("account.whatIsHere")}>{t("account.whatIsHere.body")}</InfoHint>
        </div>
        <GuideLink slug="account" />
        <div className="flex flex-wrap items-center gap-2 pt-1.5">
          <span className="font-mono text-body text-muted-foreground">{user.username}</span>
          {user.is_admin ? <Badge variant="secondary">{t("account.admin")}</Badge> : null}
        </div>
      </header>

      <Tabs
        items={ACCOUNT_TABS.map(({ value, label }) => ({ value, label: t(label) }))}
        value={tab}
        onChange={(next) => {
          const target = ACCOUNT_TABS.find((item) => item.value === next);
          if (target) navigate(target.path);
        }}
      />

      {tab === "cuenta" ? <AccountTabView /> : null}
      {tab === "workspaces" ? <MyWorkspacesTab /> : null}
    </div>
  );
}

/* Cuenta ------------------------------------------------------------------------------ */

/**
 * What this account READS the app in.
 *
 * Deliberately a card here and not a row in the avatar menu, unlike the theme: the theme
 * is a property of the screen somebody is sitting at and changes twice a day, while this
 * is a property of the person and is set once. The warning under it is the point of the
 * card — the obvious reading of "idioma" is that it changes everything, and it changes
 * exactly one half: what the workspace's prompts are written in is the workspace's own
 * declaration, fixed when it was created.
 */
function LanguageCard() {
  const { t, language } = useT();
  const setLanguage = useSetLanguage();
  const toast = useToast();

  const choose = (next: Language) => {
    if (next === language) return;
    setLanguage.mutate(next, {
      onSuccess: () =>
        toast({ title: t("language.changed", { name: LANGUAGE_NAMES[next] }) }),
    });
  };

  const radios = useRadioGroup(LANGUAGES, language, choose);

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <Languages className="size-4 text-muted-foreground" />
          {t("language.title")}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <p className="text-small text-muted-foreground">{t("language.help")}</p>

        <div
          role="radiogroup"
          aria-label={t("language.title")}
          className="flex flex-wrap gap-2"
          {...radios.group}
        >
          {LANGUAGES.map((code) => (
            <Button
              key={code}
              {...radios.radio(code)}
              role="radio"
              aria-checked={code === language}
              variant={code === language ? "default" : "outline"}
              disabled={setLanguage.isPending}
              onClick={() => choose(code)}
            >
              {setLanguage.isPending && setLanguage.variables === code ? (
                <Spinner />
              ) : code === language ? (
                <Check />
              ) : null}
              {LANGUAGE_NAMES[code]}
            </Button>
          ))}
        </div>

        <Alert tone="attention" title={t("language.warning.title")}>
          {t("language.warning.body")}
        </Alert>
        <p className="text-small text-muted-foreground">{t("language.notPrompts")}</p>

        <FormError error={setLanguage.error} />
      </CardContent>
    </Card>
  );
}

/**
 * The three cards of "Cuenta", in two columns that are each their own stack.
 *
 * Two columns and NOT three cells of a grid: a grid row is as tall as its tallest cell, so
 * the third card starts below the foot of the second and leaves a hand's width of nothing.
 * A flex stack starts each card where the one above it ended. The pairing is by SIZE and
 * not by subject — the tall password card alone, the two short ones sharing the other
 * track — and below `lg` all three stack in this same order.
 */
function AccountTabView() {
  return (
    <div className="grid items-start gap-4 lg:grid-cols-2">
      <div className="flex flex-col gap-4">
        <IdentityCard />
        <LanguageCard />
      </div>
      <PasswordCard />
    </div>
  );
}

/**
 * The fields an account may change about itself.
 *
 * The username is not one of them and is shown as text: it is what every message prints and
 * what every row points at, so renaming it would quietly rewrite who wrote what. The
 * address is optional — invitations are handed over by hand here — and says what it is FOR
 * rather than pretending to be a second identity.
 *
 * It is only offered where it could arrive: with no SMTP the reset link is logged and
 * handed back in the response, so the field would collect something nothing will ever read.
 * HIDDEN there and not removed — the column, `/forgot` and `mail.py` are untouched, so
 * configuring `SMTP_HOST` brings it back with no migration.
 *
 * The `||` is the half that matters and is not belt-and-braces: an account that already
 * HAS an address keeps seeing it even where nothing can deliver, because hiding a field
 * that holds data is hiding data — there would be no way left to read it or clear it.
 */
function IdentityCard() {
  const { t } = useT();
  const session = useSession();
  const update = useUpdateProfile();
  const toast = useToast();
  const user = session.data?.user;
  const [name, setName] = useState(user?.name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");

  if (!user) return null;
  const dirty = name.trim() !== user.name || (email.trim() || null) !== user.email;
  const offerEmail = (session.data?.mail_configured ?? false) || Boolean(user.email);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    update.mutate(
      { name: name.trim(), email: email.trim() || null },
      { onSuccess: () => toast({ title: t("common.saved") }) },
    );
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <UserRound className="size-4 text-muted-foreground" />
          {t("account.identity.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <Label>{t("account.identity.username")}</Label>
            <p className="rounded-md border border-dashed border-border px-3 py-2 font-mono text-body text-muted-foreground">
              {user.username}
            </p>
            <p className="text-small text-muted-foreground">
              {t("account.identity.usernameLocked")}
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="account-name">{t("account.identity.name")}</Label>
            <Input
              id="account-name"
              value={name}
              maxLength={200}
              onChange={(event) => setName(event.target.value)}
            />
            <p className="text-small text-muted-foreground">
              {t("account.identity.nameHelp")}
            </p>
          </div>

          {offerEmail ? (
            <div className="space-y-1.5">
              <Label htmlFor="account-email">{t("account.identity.email")}</Label>
              <Input
                id="account-email"
                type="email"
                autoComplete="email"
                placeholder={t("account.identity.email.placeholder")}
                value={email}
                onChange={(event) => setEmail(event.target.value)}
              />
              <p className="text-small text-muted-foreground">
                {session.data?.mail_configured
                  ? t("account.identity.email.help")
                  : t("account.identity.email.help.noMail")}
              </p>
            </div>
          ) : null}

          <FormError error={update.error} />

          <div className="flex items-center gap-2">
            <Button type="submit" disabled={!dirty || update.isPending}>
              {update.isPending ? <Spinner /> : null}
              {t("common.save")}
            </Button>
            {update.isSuccess && !dirty ? (
              <span className="flex items-center gap-1 text-small text-settled">
                <Check className="size-3.5" />
                {t("common.saved")}
              </span>
            ) : null}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

/** The old dialog, on the page. Same contract, said out loud: changing the password signs
 *  out every other device, because the usual reason to change it is a suspicion. */
function PasswordCard() {
  const { t } = useT();
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const change = useChangePassword();

  const mismatch = repeat.length > 0 && next !== repeat;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (mismatch) return;
    change.mutate(
      { current, next },
      {
        onSuccess: () => {
          setCurrent("");
          setNext("");
          setRepeat("");
          toast({
            title: t("password.changed.title"),
            description: t("password.changed.body"),
          });
        },
      },
    );
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-4 text-muted-foreground" />
          {t("password.title")}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <p className="text-small text-muted-foreground">{t("password.help")}</p>

          <div className="space-y-1.5">
            <Label htmlFor="current-password">{t("password.current")}</Label>
            <Input
              id="current-password"
              type="password"
              autoComplete="current-password"
              required
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="next-password">{t("password.next")}</Label>
            <Input
              id="next-password"
              type="password"
              autoComplete="new-password"
              required
              value={next}
              onChange={(event) => setNext(event.target.value)}
            />
            <p className="text-small text-muted-foreground">{t("password.next.help")}</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="repeat-password">{t("password.repeat")}</Label>
            <Input
              id="repeat-password"
              type="password"
              autoComplete="new-password"
              required
              value={repeat}
              onChange={(event) => setRepeat(event.target.value)}
            />
            {mismatch ? (
              <p className="text-small text-destructive">{t("password.mismatch")}</p>
            ) : null}
          </div>

          <FormError error={change.error} />

          <div className="flex items-center gap-2">
            <Button type="submit" disabled={change.isPending || mismatch}>
              {change.isPending ? <Spinner /> : null}
              {t("password.submit")}
            </Button>
            {change.isSuccess ? (
              <span className="flex items-center gap-1 text-small text-settled">
                <Check className="size-3.5" />
                {t("password.changed")}
              </span>
            ) : null}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

/* Asignaturas y ejercicios ------------------------------------------------------------ */

/** How long the list takes to give the exercises their column: `--motion-overlay`. */
const SPLIT_MS = 240;

/**
 * Which instances this account may enter, on what grounds, the exercises it generated in
 * each, and the one thing it may do to them: dispose of the ones it owns.
 *
 * TWO COLUMNS, AND ONLY ONCE A SUBJECT IS CHOSEN (the user's call, 2026-10-04). Unfolded
 * under their subject, the exercises were rows of the same block as the subjects and read as
 * more of them. The screen opens on the subjects alone, across the whole width; «Ejercicios»
 * on a row narrows that list into a column and opens the row's exercises beside it. The two
 * are then two materials: the subjects are the rows of one block, the exercises are blocks
 * of their own on the ground. Nothing remembers the choice.
 *
 * Below `lg` there is no room for two columns: the exercises take the list's place and a
 * button leads back to it.
 *
 * ONLY THE ACCOUNT'S OWN, for an administrator like for anybody (the user's call,
 * 2026-10-04): the subjects a membership row gives it and the exercises it generated itself.
 * A subject an administrator reaches only through the bypass is not theirs and has no row
 * here; it is entered from the switcher and read — its exercises, everybody's — from
 * «Administración → Asignaturas».
 *
 * It reads `/api/workspaces` and not the session's membership list, which are different
 * questions for an administrator: the session appends whichever workspace they are standing
 * in and labels it "Propietario", which is what the bypass grants and not what anybody
 * wrote in a row. The listing carries `as_admin`, which is what leaves those out.
 *
 * Membership itself is read-only — only the installation's administrator writes those rows,
 * so offering to change one here would be offering a 403 — and renaming is deliberately not
 * here either. Deleting belongs here and not in the switcher: a destructive action one row
 * from the control you press twenty times a day is a mis-click waiting to happen.
 */
function MyWorkspacesTab() {
  const { t } = useT();
  const session = useSession();
  const listing = useWorkspaces();
  const active = useActiveWorkspace();
  const switching = useSwitchWorkspace();
  const [target, setTarget] = useState<WorkspaceRow | null>(null);
  const { chosen, shown, moving, choose } = useSplit();
  const mine = (listing.data?.workspaces ?? []).filter((workspace) => !workspace.as_admin);
  const current = active ?? listing.data?.active ?? null;
  // A subject that left the list (deleted, access withdrawn) takes its column with it.
  const open = mine.find((workspace) => workspace.slug === shown) ?? null;
  const split = open !== null && chosen !== null;

  return (
    <div className="space-y-4">
      {listing.isLoading ? <Spinner /> : null}

      {/* Not to an ADMINISTRATOR, who with no membership of their own lands here too — and
          "an administrator can give you access" is addressed to the one person who does the
          giving. The notice is for the account that has to WAIT for somebody. An
          administrator with no workspace at all is not left in the dark either: `/` draws
          `NoWorkspace` with its create button. */}
      {!listing.isLoading && mine.length === 0 && !session.data?.user.is_admin ? (
        <Alert tone="attention" title={t("access.none.title")}>
          <p>{t("access.none.body")}</p>
        </Alert>
      ) : null}

      {/* The administrator with no subject of their own is told where the installation's
          are, so a list left empty on purpose does not read as one that failed to load. */}
      {!listing.isLoading && mine.length === 0 && session.data?.user.is_admin ? (
        <p className="text-small text-muted-foreground">{t("access.none.admin")}</p>
      ) : null}

      {mine.length > 0 ? (
        <div className="lg:flex lg:items-start">
          {/* The width is the one thing that moves: the list persists across the choice, so
              the browser animates it from the whole row to its column and back. Cleared of
              the sticky header like the panel's own list of sections. */}
          <nav
            aria-label={t("acc.ws.list")}
            className={cn(
              "surface p-2 lg:shrink-0 lg:transition-[width] lg:duration-[240ms] lg:ease-[var(--ease)] motion-reduce:transition-none",
              split ? "hidden lg:sticky lg:top-40 lg:block lg:w-[22rem] xl:top-24" : "w-full",
            )}
          >
            <ul className="space-y-1">
              {mine.map((workspace) => (
                <SubjectRow
                  key={workspace.slug}
                  workspace={workspace}
                  inUse={workspace.slug === current}
                  compact={split}
                  chosen={split && workspace.slug === chosen}
                  entering={switching.isPending}
                  onExercises={() => choose(workspace.slug)}
                  onEnter={() => switching.mutate(workspace.slug)}
                  onDelete={() => setTarget(workspace)}
                />
              ))}
            </ul>
          </nav>

          {open ? (
            // Clipped only while the column moves, and with room for the cards' shadows:
            // the content keeps a width of its own, so it is uncovered and not reflowed.
            <section
              aria-labelledby="subject-exercises"
              className={cn(
                "min-w-0 lg:-m-6 lg:flex-1 lg:p-6 lg:pl-13",
                moving && "lg:overflow-hidden",
                chosen === null && "hidden lg:block",
              )}
            >
              <div className="animate-fade-in space-y-5 lg:min-w-[30rem]">
                <ExercisesHeader
                  workspace={open}
                  inUse={open.slug === current}
                  entering={switching.isPending}
                  onEnter={() => switching.mutate(open.slug)}
                  onClose={() => choose(null)}
                />
                <SubjectExercises key={open.slug} slug={open.slug} inUse={open.slug === current} />
              </div>
            </section>
          ) : null}
        </div>
      ) : null}

      {target ? (
        <DeleteMineDialog workspace={target} here={target.slug === current} onClose={() => setTarget(null)} />
      ) : null}
    </div>
  );
}

/**
 * The subject whose exercises are open, and the one still drawn while its column closes.
 *
 * `shown` trails `chosen` by one transition on the way out, so the exercises leave with the
 * column instead of vanishing before it; `moving` is true while the column changes width.
 */
function useSplit() {
  const [chosen, setChosen] = useState<string | null>(null);
  const [trail, setTrail] = useState<string | null>(null);
  const [moving, setMoving] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const choose = (slug: string | null) => {
    if ((slug === null) !== (chosen === null)) {
      setMoving(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => {
        setMoving(false);
        if (slug === null) setTrail(null);
      }, SPLIT_MS);
    }
    if (slug !== null) setTrail(slug);
    setChosen(slug);
  };

  return { chosen, shown: chosen ?? trail, moving, choose };
}

/**
 * One subject of the list, in the two shapes the list takes.
 *
 * Whole, across the page: what the subject is — its name, the permission held, its context —
 * and what can be done with it. `compact`, in the column beside the exercises: a name, the
 * permission and the count, the whole row one button that moves the exercises to it. The
 * chosen row is the sunk tint, as in every list of the app that sits beside what it opens.
 */
function SubjectRow({
  workspace,
  inUse,
  compact,
  chosen,
  entering,
  onExercises,
  onEnter,
  onDelete,
}: {
  workspace: WorkspaceRow;
  inUse: boolean;
  compact: boolean;
  chosen: boolean;
  entering: boolean;
  onExercises: () => void;
  onEnter: () => void;
  onDelete: () => void;
}) {
  const { plural, t } = useT();
  const role = workspace.role ? t(ROLE_LABEL_KEYS[workspace.role]) : t("role.undeclared");
  const count =
    workspace.exercises === undefined ? null : plural("form.items", workspace.exercises);

  if (compact)
    return (
      <li>
        <button
          type="button"
          aria-current={chosen ? "true" : undefined}
          onClick={onExercises}
          className={cn(
            "flex w-full items-center gap-3 rounded-inner px-3 py-2.5 text-left transition-colors",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
            chosen ? "bg-sunk" : "hover:bg-accent",
          )}
        >
          <span className="min-w-0 flex-1">
            <span
              className={cn(
                "block truncate text-body font-medium",
                chosen ? "text-foreground" : "text-muted-foreground",
              )}
            >
              {workspace.name}
            </span>
            <span className="block truncate text-small text-muted-foreground">
              {role}
              {inUse ? ` · ${t("access.inUse")}` : ""}
            </span>
          </span>
          {workspace.exercises !== undefined ? (
            <span className="nums shrink-0 text-small text-muted-foreground">
              {workspace.exercises}
            </span>
          ) : null}
          <ChevronRight
            aria-hidden
            className={cn("size-4 shrink-0", chosen ? "text-foreground" : "text-muted-foreground")}
          />
        </button>
      </li>
    );

  return (
    <li className="mx-3 space-y-3 border-b border-border py-4 last:border-b-0">
      <div className="flex flex-wrap items-start gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1 space-y-0.5">
          <p className="flex flex-wrap items-center gap-2 text-heading">
            {workspace.name}
            {inUse ? <Badge variant="secondary">{t("access.inUse")}</Badge> : null}
          </p>
          <p className="text-small text-muted-foreground">
            <span className="font-mono">{workspace.slug}</span> · {role}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1">
          <Button size="sm" variant="outline" onClick={onExercises}>
            <Library />
            {count ?? t("generations.title")}
            <ChevronRight />
          </Button>
          {inUse ? null : (
            <Button size="sm" variant="ghost" disabled={entering} onClick={onEnter}>
              {t("ws.enter")}
              <ArrowRight />
            </Button>
          )}
          {/* Only over what you own. An administrator disposes of anybody's from
              "Administración", where the whole installation is on one screen. */}
          {workspace.role === "owner" ? (
            <Button
              size="icon-sm"
              variant="ghost"
              title={t("acc.ws.delete", { name: workspace.name })}
              onClick={onDelete}
            >
              <Trash2 />
            </Button>
          ) : null}
        </div>
      </div>

      {/* The subject's context, beside the instance it describes. It is the whole reason
          this list is more than a row of slugs: two workspaces called "Compiladores" and
          "CS0" say nothing about which course each one is. */}
      <WorkspaceContext slug={workspace.slug} />
    </li>
  );
}

/**
 * What heads the exercises' column: whose they are, and the two ways out of it.
 *
 * The subject is named here because the row that names it may have scrolled away, and
 * below `lg` is not on screen at all: there the way back to the list leads the header.
 */
function ExercisesHeader({
  workspace,
  inUse,
  entering,
  onEnter,
  onClose,
}: {
  workspace: WorkspaceRow;
  inUse: boolean;
  entering: boolean;
  onEnter: () => void;
  onClose: () => void;
}) {
  const { t } = useT();
  return (
    <header className="space-y-3">
      <Button size="sm" variant="ghost" className="-ml-3 lg:hidden" onClick={onClose}>
        <ArrowLeft />
        {t("acc.ws.backToList")}
      </Button>
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0 space-y-0.5">
          <p className="text-small text-muted-foreground">{t("generations.title")}</p>
          <h2 id="subject-exercises" className="font-display font-expanded text-title">
            {workspace.name}
          </h2>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          {inUse ? null : (
            <Button size="sm" variant="ghost" disabled={entering} onClick={onEnter}>
              {t("ws.enter")}
              <ArrowRight />
            </Button>
          )}
          <Button
            size="icon-sm"
            variant="ghost"
            className="hidden lg:inline-flex"
            title={t("acc.ws.closeExercises")}
            aria-label={t("acc.ws.closeExercises")}
            onClick={onClose}
          >
            <X />
          </Button>
        </div>
      </div>
    </header>
  );
}

/**
 * What goes and what stays, said before it happens and confirmed by typing the slug.
 *
 * The slug rather than an "are you sure": this deletes a course's worth of work, and a
 * dialog whose confirmation is one click away from the button that opened it is not a
 * confirmation. It is the same device the administrator's own deletion uses.
 *
 * WHETHER THE FILE TREE SURVIVES DEPENDS ON WHO ELSE IS IN IT, and saying which is half the
 * point of the dialog. Nobody else has access: the documents go too, because otherwise an
 * abandoned instance piles up on disk under a slug that is on record nowhere. Somebody else
 * does: they stay, because those are that person's lecture notes and they are losing the
 * instance without having asked.
 *
 * The rule is stated rather than resolved, and that is deliberate: the listing behind this
 * dialog knows each workspace's role and not its roster, and asking the server for a member
 * count to phrase one sentence buys a round trip for something the sentence can just say.
 */
function DeleteMineDialog({
  workspace,
  here,
  onClose,
}: {
  workspace: WorkspaceRow;
  here: boolean;
  onClose: () => void;
}) {
  const { t } = useT();
  const remove = useDeleteWorkspace();
  const toast = useToast();
  const [typed, setTyped] = useState("");

  return (
    <Dialog
      open
      onClose={onClose}
      title={t("acc.ws.deleteTitle", { name: workspace.name })}
      description={t("ws.cannotUndo")}
      className="max-w-lg"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button
            variant="destructive"
            disabled={typed !== workspace.slug || remove.isPending}
            onClick={() =>
              remove.mutate(workspace.slug, {
                onSuccess: ({ landed }) => {
                  onClose();
                  toast({
                    title: t("ws.deleted"),
                    description: !here
                      ? t("acc.ws.deletedOther", { slug: workspace.slug })
                      : landed
                        ? t("acc.ws.deletedMoved", { slug: workspace.slug, next: landed })
                        : t("acc.ws.deletedHere", { slug: workspace.slug }),
                    tone: "attention",
                  });
                },
              })
            }
          >
            {remove.isPending ? <Spinner /> : <Trash2 />}
            {t("common.delete")}
          </Button>
        </>
      }
    >
      <div className="space-y-3 text-body">
        <p>{t("acc.ws.whatGoes")}</p>
        <p className="text-small text-muted-foreground">{t("acc.ws.filesStay")}</p>
        <div className="space-y-1">
          <Label htmlFor="confirm-slug">
            {t("ws.typeToConfirm")}
            <span className="font-mono normal-case">{workspace.slug}</span>
            {t("ws.typeToConfirm.tail")}
          </Label>
          <Input
            id="confirm-slug"
            autoFocus
            autoComplete="off"
            value={typed}
            onChange={(event) => setTyped(event.target.value)}
            className="font-mono"
          />
        </div>
        <FormError error={remove.error} />
      </div>
    </Dialog>
  );
}
