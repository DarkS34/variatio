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
  const [email, setEmail] = useState("");
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
  const bound = Boolean(invite.email);

  // Redeeming an invitation aimed at an existing address only adds the membership: it is
  // not a way to set somebody else's password, so the screen says what actually happened.
  if (accept.isSuccess && !accept.data.created) {
    return (
      <AuthLayout
        title="Ya tienes cuenta"
        description={`Te hemos añadido a «${invite.workspace}». Entra con tu contraseña de siempre.`}
        footer={
          <a href="/" className="text-muted-foreground hover:underline">
            Ir a la pantalla de entrada
          </a>
        }
      >
        <Button className="w-full" onClick={() => window.location.assign("/")}>
          Entrar
        </Button>
      </AuthLayout>
    );
  }

  const submit = (event: FormEvent) => {
    event.preventDefault();
    accept.mutate({
      token,
      name: name.trim(),
      email: bound ? undefined : email.trim(),
      password,
    });
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
          <Label htmlFor="invite-name">Nombre</Label>
          <Input
            id="invite-name"
            required
            autoFocus
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="invite-email">Correo</Label>
          <Input
            id="invite-email"
            type="email"
            autoComplete="username"
            required
            readOnly={bound}
            value={bound ? invite.email! : email}
            onChange={(event) => setEmail(event.target.value)}
            className={bound ? "text-muted-foreground" : undefined}
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
