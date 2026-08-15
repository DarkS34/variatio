import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { useLogin } from "@/state/auth";

import { AuthLayout, FormError } from "./AuthLayout";

export function LoginScreen() {
  const [forgotting, setForgotting] = useState(false);
  return forgotting ? (
    <ForgotForm onBack={() => setForgotting(false)} />
  ) : (
    <LoginForm onForgot={() => setForgotting(true)} />
  );
}

function LoginForm({ onForgot }: { onForgot: () => void }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useLogin();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate({ email: email.trim(), password });
  };

  return (
    <AuthLayout
      title="Entra"
      description="El acceso es por invitación: no hay registro abierto."
      footer={
        <button type="button" onClick={onForgot} className="text-muted-foreground hover:underline">
          He olvidado la contraseña
        </button>
      }
    >
      <form onSubmit={submit} className="flex flex-col gap-4">
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="email">Correo</Label>
          <Input
            id="email"
            type="email"
            autoComplete="username"
            required
            autoFocus
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="password">Contraseña</Label>
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
          Entrar
        </Button>
      </form>
    </AuthLayout>
  );
}

function ForgotForm({ onBack }: { onBack: () => void }) {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await api.forgotPassword(email.trim());
    } catch {
      /* The server answers the same either way; so does this screen. */
    }
    setBusy(false);
    setSent(true);
  };

  return (
    <AuthLayout
      title="Recuperar el acceso"
      description="Te enviamos un enlace para poner una contraseña nueva."
      footer={
        <button type="button" onClick={onBack} className="text-muted-foreground hover:underline">
          Volver a entrar
        </button>
      }
    >
      {sent ? (
        // Never "that address is not registered": this screen is the easiest place to
        // find out which addresses have an account, so it declines to say.
        <p className="text-sm text-muted-foreground">
          Si esa dirección tiene cuenta, el enlace ya va de camino. Caduca en 45 minutos.
        </p>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="forgot-email">Correo</Label>
            <Input
              id="forgot-email"
              type="email"
              autoComplete="username"
              required
              autoFocus
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
          </div>
          <Button type="submit" disabled={busy}>
            {busy ? <Spinner /> : null}
            Enviar el enlace
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
