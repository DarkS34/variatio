import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { useLogin } from "@/state/auth";

import { AuthLayout, FormError } from "./AuthLayout";
import { useT } from "@/lib/i18n";

/**
 * The one door in: a username, a password, and nothing else.
 *
 * There is no "he olvidado mi contraseña": most accounts here have no address at all, so
 * the link promised a mail nobody could receive. The way back in is an administrator handing
 * over a reset link from "Cuentas y accesos". `/reset` and `POST /api/auth/forgot` are
 * untouched — screenless, not gone — so a link already issued still works and nothing about
 * the enumeration defences moved.
 */
export function LoginScreen() {
  const { t } = useT();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const login = useLogin();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate({ username: username.trim(), password });
  };

  return (
    <AuthLayout title={t("auth.login")} description={t("auth.byInvitation")}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="username">{t("auth.username")}</Label>
          <Input
            id="username"
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
          <Label htmlFor="password">{t("auth.password")}</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>

        <FormError error={login.error} />

        <Button type="submit" disabled={login.isPending}>
          {login.isPending ? <Spinner /> : null}
          {t("common.enter")}
        </Button>
      </form>
    </AuthLayout>
  );
}
