import { useQuery } from "@tanstack/react-query";
import { Eye, EyeOff, LogIn, LogOut, RotateCcw } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { LanguageFlag } from "@/components/ui/flag";
import { Input, Label } from "@/components/ui/input";
import { Alert, Spinner } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { useToast } from "@/components/ui/toast";
import { api } from "@/lib/api";
import { LANGUAGES, LANGUAGE_NAMES, localeStore, useLanguage, type Language } from "@/lib/i18n";
import { HELP_HIDDEN } from "@/lib/help";
import { useRouter } from "@/lib/router";
import { cn } from "@/lib/utils";
import { useT, type Key } from "@/lib/i18n";
import type { EvaluatorProfile, InvitePreview, Session } from "@/lib/types";
import {
  ROLE_HINT_KEYS,
  ROLE_LABEL_KEYS,
  useAcceptInvite,
  useIsUnauthenticated,
  useJoin,
  useLoginAndJoin,
  useLogout,
  useSession,
} from "@/state/auth";

import { AuthLayout, FormError } from "./AuthLayout";
import { useStripTokenFromUrl } from "./token";

const PROFILE_IS_KEYS: Record<EvaluatorProfile, Key> = {
  teacher: "invite.profileIs.teacher",
  student: "invite.profileIs.student",
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
    // The tutorial opened a new account until it was hidden (`lib/help.ts`).
    if (accept.isSuccess) navigate(HELP_HIDDEN ? "/" : "/tutorial", { replace: true });
  }, [accept.isSuccess, navigate]);

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

  if (accept.isSuccess || joined) {
    return (
      <AuthLayout
        title={accept.isSuccess ? t("invite.accountCreated") : t("invite.title")}
        description={t("invite.alreadyIn")}
      >
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
        <FormError error={preview.error} />
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
  if (!invite.workspace) return <>{t("invite.toApp")}</>;
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
 * The registration the link was made for: language, username, name and password. Nothing
 * about what the account will be — the link decided it, and the form says it.
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
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [visible, setVisible] = useState(false);
  const [language, setLanguage] = useState<Language>(useLanguage());
  const mismatch = repeat.length > 0 && password !== repeat;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (mismatch) return;
    accept.mutate({
      token,
      username: username.trim(),
      name: name.trim(),
      password,
      ui_language: language,
    });
  };

  return (
    <form onSubmit={submit} className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        <Label id="invite-language-label">{t("invite.language")}</Label>
        <div role="group" aria-labelledby="invite-language-label" className="flex gap-1">
          {LANGUAGES.map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => {
                setLanguage(option);
                localeStore.set(option);
              }}
              aria-pressed={language === option}
              className={cn(
                "rounded-md inline-flex h-9 flex-1 items-center justify-center gap-2 border",
                "text-small font-medium transition-colors",
                language === option
                  ? "border-ink bg-ink text-ink-foreground"
                  : "border-border bg-card hover:bg-accent/60",
              )}
            >
              <LanguageFlag language={option} />
              {LANGUAGE_NAMES[option]}
            </button>
          ))}
        </div>
        <p className="text-small text-muted-foreground">
          {t("invite.languageHint")}
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="invite-username">{t("auth.username")}</Label>
        <Input
          id="invite-username"
          name="username"
          autoComplete="username"
          autoCapitalize="none"
          spellCheck={false}
          required
          autoFocus
          value={username}
          onChange={(event) => setUsername(event.target.value)}
        />
        <p className="text-small text-muted-foreground">
          {t("invite.usernameHelp")}
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="invite-name">{t("invite.visibleName")}</Label>
        <Input
          id="invite-name"
          name="name"
          autoComplete="name"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="invite-password">{t("auth.password")}</Label>
        <div className="relative">
          <Input
            id="invite-password"
            name="new-password"
            type={visible ? "text" : "password"}
            autoComplete="new-password"
            className="pr-10"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <button
            type="button"
            onClick={() => setVisible((was) => !was)}
            title={visible ? t("password.hide") : t("password.show")}
            className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
          >
            {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </div>
        <p className="text-small text-muted-foreground">
          {t("invite.passwordHelp")}
        </p>
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor="invite-repeat">{t("password.repeat")}</Label>
        <Input
          id="invite-repeat"
          name="confirm-password"
          type={visible ? "text" : "password"}
          autoComplete="new-password"
          required
          value={repeat}
          onChange={(event) => setRepeat(event.target.value)}
        />
        {mismatch ? (
          <p className="text-small text-destructive">{t("password.mismatch")}</p>
        ) : null}
      </div>

      <p className="text-small text-muted-foreground">
        {/* What the account will be, said and never asked: the invitation decided it. */}
        {invite.profile ? `${t(PROFILE_IS_KEYS[invite.profile])} ` : ""}
        {t(ROLE_HINT_KEYS[invite.role])}
      </p>

      <FormError error={accept.error} />

      <Button type="submit" disabled={accept.isPending || mismatch || paused}>
        {accept.isPending ? <Spinner /> : null}
        {t("invite.createAccount")}
      </Button>
    </form>
  );
}
