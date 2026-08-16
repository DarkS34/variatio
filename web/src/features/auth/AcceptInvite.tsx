import { useQuery } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { ROLE_HINTS, ROLE_LABELS, useAcceptInvite } from "@/state/auth";

import { AuthLayout, FormError } from "./AuthLayout";

/**
 * The only way an account comes into existence from the browser.
 *
 * The token is read from the query string and previewed before anything is typed, so an
 * expired or already-used invitation says so instead of failing after a full form.
 */
export function AcceptInvite({ token }: { token: string }) {
  const preview = useQuery({
    queryKey: ["auth", "invite", token],
    queryFn: () => api.invitePreview(token),
    retry: false,
  });

  const [name, setName] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const accept = useAcceptInvite();

  if (preview.isLoading) {
    return (
      <AuthLayout title="Invitación">
        <Spinner />
      </AuthLayout>
    );
  }

  if (preview.isError) {
    return (
      <AuthLayout
        title="Esa invitación ya no vale"
        description="Puede que se haya usado o que haya caducado. Pide otra a quien te invitó."
        footer={
          <a href="/" className="text-muted-foreground hover:underline">
            Ir a la pantalla de entrada
          </a>
        }
      >
        <FormError error={preview.error} />
      </AuthLayout>
    );
  }

  const invite = preview.data!;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    accept.mutate({ token, username: username.trim(), name: name.trim(), password });
  };

  return (
    <AuthLayout
      title="Crea tu cuenta"
      description={
        invite.workspace
          ? `Te han invitado a «${invite.workspace}» con permiso de ${ROLE_LABELS[invite.role].toLowerCase()}.`
          : "Te han invitado al generador de variantes."
      }
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="invite-username">Usuario</Label>
          <Input
            id="invite-username"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            required
            autoFocus
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Con esto entrarás. Minúsculas, cifras, punto, guion o guion bajo.
          </p>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="invite-name">Nombre visible</Label>
          <Input
            id="invite-name"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="invite-password">Contraseña</Label>
          <Input
            id="invite-password"
            type="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
          <p className="text-xs text-muted-foreground">
            Al menos 12 caracteres. Una frase que recuerdes vale más que un jeroglífico corto.
          </p>
        </div>

        <p className="text-xs text-muted-foreground">{ROLE_HINTS[invite.role]}</p>

        <FormError error={accept.error} />

        <Button type="submit" disabled={accept.isPending}>
          {accept.isPending ? <Spinner /> : null}
          Crear la cuenta
        </Button>
      </form>
    </AuthLayout>
  );
}
