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
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const login = useLogin();

  const submit = (event: FormEvent) => {
    event.preventDefault();
    login.mutate({ username: username.trim(), password });
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
          <Label htmlFor="username">Usuario</Label>
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
  const [username, setUsername] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    try {
      await api.forgotPassword(username.trim());
    } catch {
      /* The server answers the same either way; so does this screen. */
    }
    setBusy(false);
    setSent(true);
  };

  return (
    <AuthLayout
      title="Recuperar el acceso"
      description="Se genera un enlace de un solo uso para poner una contraseña nueva."
      footer={
        <button type="button" onClick={onBack} className="text-muted-foreground hover:underline">
          Volver a entrar
        </button>
      }
    >
      {sent ? (
        // Never "that account does not exist": this screen is the easiest place to find
        // out which names have an account, so it declines to say. The second sentence is
        // not a hedge either — most accounts here have no address at all, and the link
        // reaches its owner through whoever administra la instalación.
        <p className="text-body text-muted-foreground">
          Si esa cuenta existe, el enlace ya está emitido y caduca en 45 minutos. Llega por
          correo solo si la cuenta tiene una dirección asociada; si no, pídeselo a quien
          administra la instalación.
        </p>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="forgot-username">Usuario</Label>
            <Input
              id="forgot-username"
              autoComplete="username"
              autoCapitalize="none"
              spellCheck={false}
              required
              autoFocus
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </div>
          <Button type="submit" disabled={busy}>
            {busy ? <Spinner /> : null}
            Pedir el enlace
          </Button>
        </form>
      )}
    </AuthLayout>
  );
}
