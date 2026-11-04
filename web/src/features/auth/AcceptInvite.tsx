import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Check,
  Eye,
  EyeOff,
  GraduationCap,
  LogIn,
  LogOut,
  Presentation,
  RotateCcw,
} from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { CopyButton } from "@/components/CopyLink";
import { Button } from "@/components/ui/button";
import { ChoicePill } from "@/components/ui/choice";
import { LanguageFlag } from "@/components/ui/flag";
import { Input, Label } from "@/components/ui/input";
import { Alert } from "@/components/ui/alert";
import { useRadioGroup } from "@/components/ui/radio";
import { Spinner } from "@/components/ui/spinner";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { api, ApiError } from "@/lib/api";
import { LANGUAGES, LANGUAGE_NAMES, localeStore, useLanguage, type Language } from "@/lib/i18n";
import { useRouter } from "@/lib/router";
import {
  PASSWORD_MIN,
  passwordAccepted,
  passwordChecks,
  usernameFromName,
  type PasswordChecks,
} from "@/lib/signup";
import { cn } from "@/lib/utils";
import { useT, type Key } from "@/lib/i18n";
import type { EvaluatorProfile, InvitePreview, Role, Session } from "@/lib/types";
import {
  ROLE_LABEL_KEYS,
  useAcceptInvite,
  useIsUnauthenticated,
  useJoin,
  useLoginAndJoin,
  useLogout,
  useSession,
} from "@/state/auth";

import { FormError } from "@/components/ui/form-error";

import { AuthLayout } from "./AuthLayout";
import { useStripTokenFromUrl } from "./token";

const PROFILE_TITLE_KEYS: Record<EvaluatorProfile, Key> = {
  teacher: "invite.profile.teacher",
  student: "invite.profile.student",
};

/** What the role a link carries lets the person do in the subject it names. */
const CAN_KEYS: Record<Role, Key> = {
  viewer: "invite.can.viewer",
  editor: "invite.can.editor",
  owner: "invite.can.owner",
};

/** What the account does when the invitation names no subject: the application alone. */
const APP_KEYS: Record<EvaluatorProfile, Key> = {
  teacher: "invite.can.app.teacher",
  student: "invite.can.app.student",
};

type Path = "create" | "existing";

/**
 * What a link opens: a personal invitation or a class link, read before anything is spent.
 *
 * Two ways through it. With a session in the tab, the account joins the subject the link
 * names («Unirme»), or logs out because it is somebody else's tab. Without one, the person
 * creates an account — the form the link was made for — or, when the link names a subject,
 * logs in with the account they already have and joins in the same gesture. The lead line
 * says who invites, to which subject and as what, in both.
 */
export function AcceptInvite({ token }: { token: string }) {
  const { t } = useT();
  const preview = useQuery({
    queryKey: ["auth", "invite", token],
    queryFn: () => api.invitePreview(token),
    retry: false,
  });
  const session = useSession();
  const unauthenticated = useIsUnauthenticated(session);
  const accept = useAcceptInvite();
  const join = useJoin();
  const loginAndJoin = useLoginAndJoin();
  const toast = useToast();
  const { navigate } = useRouter();
  useStripTokenFromUrl();

  const joined = join.data ?? loginAndJoin.data;

  useEffect(() => {
    if (!joined) return;
    // Named from the answer: adopting it dropped every query but the session, the preview too.
    const workspace =
      joined.workspaces.find((row) => row.slug === joined.active_workspace)?.name ?? "";
    toast({
      title: t(joined.already ? "invite.joinedAlready" : "invite.joined", { workspace }),
      tone: "settled",
    });
    navigate("/", { replace: true });
    // `toast` and `t` are new on every render; the effect is about the answer arriving.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [joined, navigate]);

  if (accept.isSuccess) return <AccountReady session={accept.data} />;

  if (joined) {
    return (
      <AuthLayout title={t("invite.title")} description={t("invite.alreadyIn")}>
        <Spinner />
      </AuthLayout>
    );
  }

  if (preview.isLoading || session.isLoading) {
    return (
      <AuthLayout title={t("invite.title")}>
        <Spinner />
      </AuthLayout>
    );
  }

  if (preview.isError) {
    return (
      <AuthLayout
        title={t("invite.dead")}
        description={t("invite.deadBody")}
        footer={
          <a href="/" className="text-muted-foreground hover:underline">
            {t("auth.backToLogin")}
          </a>
        }
      >
        {/* A 404 is the dead link the title already names; the API's sentence would only repeat it. */}
        {preview.error instanceof ApiError && preview.error.status === 404 ? null : (
          <FormError error={preview.error} />
        )}
      </AuthLayout>
    );
  }

  const invite = preview.data!;
  const paused = invite.paused === true;
  const recheck = () => preview.refetch();

  if (session.data && !unauthenticated) {
    return (
      <JoinAs
        session={session.data}
        invite={invite}
        paused={paused}
        onRecheck={recheck}
        busy={join.isPending}
        // A login that worked and a join that did not lands here, its reason with it.
        error={join.isPending ? null : (join.error ?? loginAndJoin.error)}
        onJoin={() => join.mutate(token)}
      />
    );
  }

  return (
    <SignedOut
      token={token}
      invite={invite}
      paused={paused}
      onRecheck={recheck}
      accept={accept}
      loginAndJoin={loginAndJoin}
    />
  );
}

/** Who invites, to which subject and as what: the line both ways through the link open with. */
function InvitedBy({ invite }: { invite: InvitePreview }) {
  const { t } = useT();
  if (!invite.workspace) {
    return <>{invite.inviter ? t("invite.toAppFrom", { inviter: invite.inviter }) : t("invite.toApp")}</>;
  }
  const role = t(ROLE_LABEL_KEYS[invite.role]).toLowerCase();
  return (
    <>
      {invite.inviter
        ? t("invite.from", { inviter: invite.inviter, workspace: invite.workspace, role })
        : t("invite.toWorkspace", { workspace: invite.workspace, role })}
    </>
  );
}

/** A class link its teacher paused: nothing goes through it until it is resumed. */
function PausedNotice({ onRecheck }: { onRecheck: () => void }) {
  const { t } = useT();
  return (
    // The button under the sentence, not beside it: the card is narrow, and beside it the
    // sentence wrapped into a column of two words.
    <Alert tone="attention" title={t("invite.paused")}>
      <p>{t("invite.pausedBody")}</p>
      <Button size="sm" variant="outline" className="mt-2" onClick={onRecheck}>
        <RotateCcw />
        {t("invite.checkAgain")}
      </Button>
    </Alert>
  );
}

/**
 * The link opened in a tab that already has a session: join with it, or leave it.
 *
 * A link with no subject — an administrator's invitation to create an account and nothing
 * else — has nothing to join; it says so, and offers the way back and the way out.
 */
function JoinAs({
  session,
  invite,
  paused,
  onRecheck,
  busy,
  error,
  onJoin,
}: {
  session: Session;
  invite: InvitePreview;
  paused: boolean;
  onRecheck: () => void;
  busy: boolean;
  error: unknown;
  onJoin: () => void;
}) {
  const { t } = useT();
  const { navigate } = useRouter();
  const logout = useLogout();
  const username = session.user.username;

  const leave = (
    <Button variant="ghost" disabled={logout.isPending} onClick={() => logout.mutate()}>
      <LogOut />
      {t("invite.notMe", { username })}
    </Button>
  );

  if (!invite.workspace) {
    return (
      <AuthLayout
        title={t("invite.forNewAccount")}
        description={t("invite.forNewAccountBody", { username })}
      >
        <div className="flex flex-col gap-2">
          <Button onClick={() => navigate("/", { replace: true })}>{t("invite.goToApp")}</Button>
          {leave}
        </div>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout
      title={t("invite.joinAs", { workspace: invite.workspace, username })}
      description={<InvitedBy invite={invite} />}
    >
      <div className="flex flex-col gap-3">
        {paused ? <PausedNotice onRecheck={onRecheck} /> : null}
        <FormError error={error} />
        <Button disabled={busy || paused} onClick={onJoin}>
          {busy ? <Spinner /> : <LogIn />}
          {t("invite.join")}
        </Button>
        {leave}
      </div>
    </AuthLayout>
  );
}

/**
 * The link opened with no session: create the account it was made for, or — when it names a
 * subject — log in with the one you already have and join with it.
 */
function SignedOut({
  token,
  invite,
  paused,
  onRecheck,
  accept,
  loginAndJoin,
}: {
  token: string;
  invite: InvitePreview;
  paused: boolean;
  onRecheck: () => void;
  accept: ReturnType<typeof useAcceptInvite>;
  loginAndJoin: ReturnType<typeof useLoginAndJoin>;
}) {
  const { t } = useT();
  const [path, setPath] = useState<Path>("create");
  // Joining needs a subject to join: an invitation to the application alone only creates.
  const joinable = !!invite.workspace;

  return (
    <AuthLayout
      wide
      title={path === "create" ? t("invite.create") : t("invite.signIn")}
      description={<InvitedBy invite={invite} />}
    >
      <div className="flex flex-col gap-4">
        {joinable ? (
          <Tabs
            className="self-start"
            value={path}
            onChange={(next) => setPath(next as Path)}
            items={[
              { value: "create", label: t("invite.tab.create") },
              { value: "existing", label: t("invite.tab.existing") },
            ]}
          />
        ) : null}
        {paused ? <PausedNotice onRecheck={onRecheck} /> : null}
        {path === "create" || !joinable ? (
          <CreateAccount token={token} invite={invite} paused={paused} accept={accept} />
        ) : (
          <SignInAndJoin token={token} paused={paused} loginAndJoin={loginAndJoin} />
        )}
      </div>
    </AuthLayout>
  );
}

/**
 * Log in with an existing account and join: the login screen's two fields, and the same
 * uniform answer when they are wrong.
 */
function SignInAndJoin({
  token,
  paused,
  loginAndJoin,
}: {
  token: string;
  paused: boolean;
  loginAndJoin: ReturnType<typeof useLoginAndJoin>;
}) {
  const { t } = useT();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    loginAndJoin.mutate({ username: username.trim(), password, token });
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <p className="text-small text-muted-foreground">{t("invite.existingHint")}</p>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="join-username">{t("auth.username")}</Label>
        <Input
          id="join-username"
          name="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          required
          autoFocus
          value={username}
          onChange={(event) => setUsername(event.target.value)}
        />
      </div>
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="join-password">{t("auth.password")}</Label>
        <Input
          id="join-password"
          name="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
      </div>

      <FormError error={loginAndJoin.error} />

      <Button type="submit" disabled={loginAndJoin.isPending || paused}>
        {loginAndJoin.isPending ? <Spinner /> : null}
        {t("invite.signInAndJoin")}
      </Button>
    </form>
  );
}

/**
 * The registration the link was made for: what the account will be, the language, the name
 * and the password (the user's request, 2026-11-04).
 *
 * What the account will be comes FIRST and is said, never asked: the invitation decided it.
 * The name is the one identity asked for: the server makes the username from it
 * (`queries.username_from_name`), the form shows the one it will be as the name is typed,
 * and the screen after it says the one it is. The password is typed once, with a way to see
 * it, and its rules tick as they are met (`lib/signup.passwordChecks`, the server's rules
 * mirrored): the button waits until they all are, so the server's refusal is never the first
 * thing a person learns of a rule.
 */
function CreateAccount({
  token,
  invite,
  paused,
  accept,
}: {
  token: string;
  invite: InvitePreview;
  paused: boolean;
  accept: ReturnType<typeof useAcceptInvite>;
}) {
  const { t } = useT();
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [visible, setVisible] = useState(false);
  const [language, setLanguage] = useState<Language>(useLanguage());
  const choose = (option: Language) => {
    setLanguage(option);
    localeStore.set(option);
  };
  const languages = useRadioGroup(LANGUAGES, language, choose);
  const username = usernameFromName(name);
  const checks = passwordChecks(password, { name: name.trim(), username });
  const ready = name.trim().length > 0 && passwordAccepted(checks);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!ready) return;
    accept.mutate({ token, name: name.trim(), password, ui_language: language });
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-5">
      <ProfileStrip invite={invite} />

      <div className="flex flex-col gap-1.5">
        <Label id="invite-language-label">{t("invite.language")}</Label>
        <div
          role="radiogroup"
          aria-labelledby="invite-language-label"
          className="grid grid-cols-2 gap-2"
          {...languages.group}
        >
          {LANGUAGES.map((option) => (
            <ChoicePill
              key={option}
              {...languages.radio(option)}
              chosen={language === option}
              onClick={() => choose(option)}
            >
              <LanguageFlag language={option} />
              {LANGUAGE_NAMES[option]}
            </ChoicePill>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="invite-name">{t("invite.name")}</Label>
        <Input
          id="invite-name"
          name="name"
          autoComplete="name"
          maxLength={200}
          required
          autoFocus
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        {/* For the password manager: the username it saves beside the new password. */}
        <input type="text" name="username" autoComplete="username" value={username} readOnly hidden />
        <p className="text-small text-muted-foreground" aria-live="polite">
          {username ? (
            <>
              {t("invite.signInAs")}{" "}
              <span className="rounded-sm bg-sunk px-1.5 py-0.5 font-mono text-foreground">{username}</span>
              <span className="block pt-1">{t("invite.signInAsNote")}</span>
            </>
          ) : (
            t("invite.nameHelp")
          )}
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="invite-password">{t("auth.password")}</Label>
        <div className="relative">
          <Input
            id="invite-password"
            name="new-password"
            type={visible ? "text" : "password"}
            autoComplete="new-password"
            aria-describedby="invite-password-rules"
            className="pr-10"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <button
            type="button"
            onClick={() => setVisible((was) => !was)}
            aria-label={visible ? t("password.hide") : t("password.show")}
            title={visible ? t("password.hide") : t("password.show")}
            className="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-md text-muted-foreground transition-colors hover:text-foreground"
          >
            {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </div>
        <PasswordRules id="invite-password-rules" checks={checks} />
        <p className="text-small text-muted-foreground">{t("invite.passwordTip")}</p>
      </div>

      <FormError error={accept.error} />

      <Button type="submit" size="lg" disabled={accept.isPending || paused || !ready}>
        {accept.isPending ? <Spinner /> : null}
        {t("invite.createAccount")}
      </Button>
    </form>
  );
}

/**
 * What the account will be, at the head of the form: its profile as a title, and what it lets
 * the person do, said for the subject the link names or for the application alone.
 */
function ProfileStrip({ invite }: { invite: InvitePreview }) {
  const { t } = useT();
  const profile = invite.profile ?? (invite.role === "viewer" ? "student" : "teacher");
  const Icon = profile === "teacher" ? Presentation : GraduationCap;
  const lines = invite.workspace
    ? [
        t(CAN_KEYS[invite.role], { workspace: invite.workspace }),
        ...(profile === "teacher" ? [t("invite.can.ownSubjects")] : []),
      ]
    : [t(APP_KEYS[profile])];
  return (
    <div className="flex items-start gap-3 rounded-inner bg-sunk p-3">
      <span
        aria-hidden
        className="flex size-9 shrink-0 items-center justify-center rounded-md bg-ink text-ink-foreground"
      >
        <Icon className="size-4" />
      </span>
      <div className="min-w-0 space-y-0.5">
        <p className="text-body font-medium">{t(PROFILE_TITLE_KEYS[profile])}</p>
        <p className="text-small text-muted-foreground">{lines.join(" ")}</p>
      </div>
    </div>
  );
}

/** The password's rules, each ticked as it is met: what the server would refuse, said first. */
function PasswordRules({ id, checks }: { id: string; checks: PasswordChecks }) {
  const { t } = useT();
  const rules: { met: boolean; label: string; detail?: string }[] = [
    {
      met: checks.length,
      label: t("password.rule.length", { n: PASSWORD_MIN }),
      detail: checks.count > 0 && !checks.length ? `${checks.count}/${PASSWORD_MIN}` : undefined,
    },
    { met: checks.personal && checks.count > 0, label: t("password.rule.personal") },
    { met: checks.obvious, label: t("password.rule.obvious") },
  ];
  return (
    <ul id={id} aria-live="polite" className="space-y-1 pt-1">
      {rules.map((rule) => (
        <li
          key={rule.label}
          className={cn(
            "flex items-start gap-2 text-small transition-colors",
            rule.met ? "text-foreground" : "text-muted-foreground",
          )}
        >
          <span
            aria-hidden
            className={cn(
              "mt-0.5 flex size-4 shrink-0 items-center justify-center rounded-full transition-colors",
              rule.met ? "bg-settled text-background" : "border border-input",
            )}
          >
            {rule.met ? <Check className="size-3" strokeWidth={3} /> : null}
          </span>
          <span className="min-w-0 flex-1">
            <span className="sr-only">{rule.met ? t("password.rule.met") : t("password.rule.unmet")} </span>
            {rule.label}
          </span>
          {rule.detail ? <span className="nums shrink-0">{rule.detail}</span> : null}
        </li>
      ))}
    </ul>
  );
}

/**
 * The account is made: the username the server chose, said once, big and copyable, because
 * nobody typed it and it is what the next login asks for. «Empezar» goes in.
 */
function AccountReady({ session }: { session: Session }) {
  const { t } = useT();
  const { navigate } = useRouter();
  const username = session.user.username;
  // The form showed the name before its number: a namesake made it another, and that is said.
  const previewed = usernameFromName(session.user.name ?? "");
  const numbered = previewed !== "" && previewed !== username;
  return (
    <AuthLayout wide title={t("invite.ready.title")} description={t("invite.ready.lead")}>
      <div className="flex flex-col gap-5">
        <div className="flex items-center gap-3 rounded-inner bg-sunk p-3">
          <div className="min-w-0 flex-1 space-y-0.5">
            <p className="text-micro font-condensed uppercase text-muted-foreground">
              {t("invite.ready.username")}
            </p>
            <p className="truncate font-mono text-heading">{username}</p>
          </div>
          <CopyButton text={username} />
        </div>
        {numbered ? (
          <p className="text-small text-muted-foreground">{t("invite.ready.numbered", { previewed })}</p>
        ) : null}
        <Button size="lg" autoFocus onClick={() => navigate("/", { replace: true })}>
          {t("invite.ready.go")}
          <ArrowRight />
        </Button>
      </div>
    </AuthLayout>
  );
}
