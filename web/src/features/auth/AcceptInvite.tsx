import { useQuery } from "@tanstack/react-query";
import { Eye, EyeOff } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { LanguageFlag } from "@/components/ui/flag";
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
import { useStripTokenFromUrl } from "./token";


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
  const [profile, setProfile] = useState<EvaluatorProfile | null>(null);
  const [language, setLanguage] = useState<Language>(useLanguage());
  const accept = useAcceptInvite();
  const { navigate } = useRouter();
  useStripTokenFromUrl();

  useEffect(() => {
    if (accept.isSuccess) navigate("/tutorial", { replace: true });
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
                  "inline-flex h-9 flex-1 items-center justify-center gap-2 border",
                  "text-small font-medium transition-colors",
                  language === option
                    ? "border-primary bg-primary text-primary-foreground"
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
