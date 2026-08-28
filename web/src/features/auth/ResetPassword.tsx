import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { useResetPassword } from "@/state/auth";

import { AuthLayout, FormError } from "./AuthLayout";
import { useStripTokenFromUrl } from "./token";
import { useT } from "@/lib/i18n";

export function ResetPassword({ token }: { token: string }) {
  const { t } = useT();
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const reset = useResetPassword();
  useStripTokenFromUrl();

  const mismatch = repeat.length > 0 && password !== repeat;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (mismatch) return;
    reset.mutate({ token, password });
  };

  // Following the link proved control of the mailbox, so the server logs them straight
  // in; every other device was signed out in the same transaction.
  if (reset.isSuccess) {
    return (
      <AuthLayout
        title={t("reset.done")}
        description={t("reset.doneBody")}
      >
        <Button className="w-full" onClick={() => window.location.assign("/")}>
          {t("common.continue")}
        </Button>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title={t("reset.newPassword")} description={t("reset.singleUse")}>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="reset-password">{t("auth.password")}</Label>
          <Input
            id="reset-password"
            type="password"
            autoComplete="new-password"
            required
            autoFocus
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <p className="text-small text-muted-foreground">{t("password.next.help")}</p>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="reset-repeat">{t("password.repeat")}</Label>
          <Input
            id="reset-repeat"
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

        <FormError error={reset.error} />

        <Button type="submit" disabled={reset.isPending || mismatch}>
          {reset.isPending ? <Spinner /> : null}
          {t("common.save")}
        </Button>
      </form>
    </AuthLayout>
  );
}
