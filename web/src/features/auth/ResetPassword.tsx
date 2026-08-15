import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { useResetPassword } from "@/state/auth";

import { AuthLayout, FormError } from "./AuthLayout";

export function ResetPassword({ token }: { token: string }) {
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const reset = useResetPassword();

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
        title="Contraseña cambiada"
        description="Has entrado con la nueva. Se ha cerrado la sesión en los demás dispositivos."
      >
        <Button className="w-full" onClick={() => window.location.assign("/")}>
          Continuar
        </Button>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout title="Nueva contraseña" description="El enlace solo sirve una vez.">
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="reset-password">Contraseña</Label>
          <Input
            id="reset-password"
            type="password"
            autoComplete="new-password"
            required
            autoFocus
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <p className="text-xs text-muted-foreground">Al menos 12 caracteres.</p>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="reset-repeat">Repítela</Label>
          <Input
            id="reset-repeat"
            type="password"
            autoComplete="new-password"
            required
            value={repeat}
            onChange={(event) => setRepeat(event.target.value)}
          />
          {mismatch ? <p className="text-xs text-destructive">Las dos no coinciden.</p> : null}
        </div>

        <FormError error={reset.error} />

        <Button type="submit" disabled={reset.isPending || mismatch}>
          {reset.isPending ? <Spinner /> : null}
          Guardar
        </Button>
      </form>
    </AuthLayout>
  );
}
