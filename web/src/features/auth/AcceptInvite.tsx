import { useQuery } from "@tanstack/react-query";
import { Eye, EyeOff } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { PROFILES, PROFILE_SELF_LABEL_KEYS } from "@/lib/evaluator";
import { LANGUAGES, LANGUAGE_NAMES, localeStore, useLanguage, type Language } from "@/lib/i18n";
import { useRouter } from "@/lib/router";
import type { EvaluatorProfile } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
import { ROLE_HINT_KEYS, ROLE_LABEL_KEYS, useAcceptInvite } from "@/state/auth";

import { AuthLayout, FormError } from "./AuthLayout";

/**
 * The only way an account comes into existence from the browser.
 *
 * The token is read from the query string and previewed before anything is typed, so an
 * expired or already-used invitation says so instead of failing after a full form.
 *
 * A redeemed invitation is *also* an invalid one, which is why the success branch comes
 * first: accepting adopts the session, and adopting drops every query except the session
 * — including this preview, which the still-mounted screen immediately refetched and got
 * a 404 for. The account had been created and the person was already logged in, and they
 * were being told their link had expired. Landing on the app is both the fix and what
 * should have happened anyway; the effect strips the token from the URL on the way.
 */
export function AcceptInvite({ token }: { token: string }) {
  const { t } = useT();
  const preview = useQuery({
    queryKey: ["auth", "invite", token],
    queryFn: () => api.invitePreview(token),
    retry: false,
  });

  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [visible, setVisible] = useState(false);
  // No default: the two are not a scale with a middle, and a preselected answer is one
  // nobody gave. Nothing is submitted until it is chosen.
  const [profile, setProfile] = useState<EvaluatorProfile | null>(null);
  // Seeded from what the browser already says, so a person whose machine is in English
  // is not greeted in Spanish and then asked to fix it. It is a default and not an
  // answer: the control below is what they actually decide with.
  const [language, setLanguage] = useState<Language>(useLanguage());
  const accept = useAcceptInvite();
  const { navigate } = useRouter();

  useEffect(() => {
    if (accept.isSuccess) navigate("/", { replace: true });
  }, [accept.isSuccess, navigate]);

  if (accept.isSuccess) {
    return (
      <AuthLayout title={t("invite.accountCreated")} description={t("invite.alreadyIn")}>
        <Spinner />
      </AuthLayout>
    );
  }

  if (preview.isLoading) {
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
  const mismatch = repeat.length > 0 && password !== repeat;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (mismatch || !profile) return;
    accept.mutate({
      token,
      username: username.trim(),
      name: name.trim(),
      password,
      evaluator_profile: profile,
      ui_language: language,
    });
  };

  return (
    <AuthLayout
      title={t("invite.create")}
      description={
        invite.workspace
          ? t("invite.toWorkspace", {
            workspace: invite.workspace,
            role: t(ROLE_LABEL_KEYS[invite.role]).toLowerCase(),
          })
          : t("invite.toApp")
      }
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
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

        {/* Asked here and only here. Whoever invited had no field for it: the link binds the
            access and nothing else, and this is the one moment the person is in front of a
            form — asking mid-comparison gets an answer of convenience. It is not a
            permission, and an administrator corrects it from the panel afterwards. */}
        <div className="flex flex-col gap-1.5">
          <Label id="invite-profile-label">{t("invite.teachOrStudy")}</Label>
          <div role="group" aria-labelledby="invite-profile-label" className="flex gap-1">
            {PROFILES.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => setProfile(option)}
                aria-pressed={profile === option}
                className={cn(
                  "h-9 flex-1 border text-small font-medium transition-colors",
                  profile === option
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-dashed border-attention bg-card text-attention hover:bg-accent/60",
                )}
              >
                {t(PROFILE_SELF_LABEL_KEYS[option])}
              </button>
            ))}
          </div>
          <p className="text-small text-muted-foreground">
            {t("invite.profileHint")}
          </p>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label id="invite-language-label">{t("invite.language")}</Label>
          <div role="group" aria-labelledby="invite-language-label" className="flex gap-1">
            {LANGUAGES.map((option) => (
              <button
                key={option}
                type="button"
                onClick={() => {
                  setLanguage(option);
                  // Written through at once: the rest of this form, and the screen behind
                  // it, are already drawn — a choice that only landed on submit would leave
                  // somebody finishing a form in a language they have just said they do not
                  // read.
                  localeStore.set(option);
                }}
                aria-pressed={language === option}
                className={cn(
                  "h-9 flex-1 border text-small font-medium transition-colors",
                  language === option
                    ? "border-primary bg-primary text-primary-foreground"
                    : "border-border bg-card hover:bg-accent/60",
                )}
              >
                {LANGUAGE_NAMES[option]}
              </button>
            ))}
          </div>
          <p className="text-small text-muted-foreground">
            {t("invite.languageHint")}
          </p>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="invite-password">{t("auth.password")}</Label>
          {/* `new-password` on both fields is what makes this a sign-up form to a password
              manager: it is the signal Google Contraseñas reads to offer «Sugerir
              contraseña segura» on focus, and to store the pair afterwards. Generating one
              is the manager's job and not this screen's — one that offered its own had to
              show it in clear so it could be copied before the field was cleared. */}
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

        <p className="text-small text-muted-foreground">{t(ROLE_HINT_KEYS[invite.role])}</p>

        <FormError error={accept.error} />

        <Button type="submit" disabled={accept.isPending || mismatch || !profile}>
          {accept.isPending ? <Spinner /> : null}
          {t("invite.createAccount")}
        </Button>
      </form>
    </AuthLayout>
  );
}
