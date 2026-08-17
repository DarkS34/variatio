import { useQuery } from "@tanstack/react-query";
import { Check, Copy, Eye, EyeOff, Sparkles } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { useRouter } from "@/lib/router";
import { ROLE_HINTS, ROLE_LABELS, useAcceptInvite } from "@/state/auth";

import { AuthLayout, FormError } from "./AuthLayout";

/** No `l`/`I`/`1` and no `O`/`0`: a generated password is read off this screen and typed
 *  by hand at least once, before any manager has had the chance to remember it. */
const ALPHABET = "abcdefghijkmnopqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789.-_";
const GENERATED_LENGTH = 20;

function generatePassword() {
  const draws = new Uint32Array(GENERATED_LENGTH);
  crypto.getRandomValues(draws);
  return Array.from(draws, (draw) => ALPHABET[draw % ALPHABET.length]).join("");
}

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
  const [generated, setGenerated] = useState(false);
  const [copied, setCopied] = useState(false);
  const accept = useAcceptInvite();
  const { navigate } = useRouter();

  useEffect(() => {
    if (accept.isSuccess) navigate("/", { replace: true });
  }, [accept.isSuccess, navigate]);

  if (accept.isSuccess) {
    return (
      <AuthLayout title="Cuenta creada" description="Ya estás dentro; entrando…">
        <Spinner />
      </AuthLayout>
    );
  }

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
  const mismatch = repeat.length > 0 && password !== repeat;

  const suggest = () => {
    const suggestion = generatePassword();
    setPassword(suggestion);
    setRepeat(suggestion);
    setVisible(true);
    setGenerated(true);
    setCopied(false);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (mismatch) return;
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
            name="username"
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
            name="name"
            autoComplete="name"
            required
            value={name}
            onChange={(event) => setName(event.target.value)}
          />
        </div>

        <div className="flex flex-col gap-1.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Label htmlFor="invite-password">Contraseña</Label>
            <button
              type="button"
              onClick={suggest}
              className="flex items-center gap-1 text-xs text-muted-foreground transition-colors hover:text-foreground"
            >
              <Sparkles className="size-3.5" />
              Generar una segura
            </button>
          </div>
          {/* `new-password` on both fields is what makes this a sign-up form to a password
              manager: it is the signal Google Contraseñas reads to offer «Sugerir
              contraseña segura» on focus, and to store the pair afterwards. The button
              above is the same offer without depending on the browser having it. */}
          <div className="relative">
            <Input
              id="invite-password"
              name="new-password"
              type={visible ? "text" : "password"}
              autoComplete="new-password"
              className="pr-10"
              required
              value={password}
              onChange={(event) => {
                setPassword(event.target.value);
                setGenerated(false);
              }}
            />
            <button
              type="button"
              onClick={() => setVisible((was) => !was)}
              title={visible ? "Ocultar" : "Ver"}
              className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
            >
              {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          <p className="text-xs text-muted-foreground">
            Al menos 12 caracteres. Si usas el gestor de contraseñas de Google o del
            navegador, pulsa en el campo y elige «Sugerir contraseña segura».
          </p>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="invite-repeat">Repítela</Label>
          <Input
            id="invite-repeat"
            name="confirm-password"
            type={visible ? "text" : "password"}
            autoComplete="new-password"
            required
            value={repeat}
            onChange={(event) => setRepeat(event.target.value)}
          />
          {mismatch ? <p className="text-xs text-destructive">Las dos no coinciden.</p> : null}
        </div>

        {/* Only after generating one: a password nobody chose has to be copyable before it
            is submitted, or the only record of it is a field about to be cleared. */}
        {generated ? (
          <div className="flex flex-wrap items-center gap-2 rounded-lg border border-border bg-muted/40 p-2">
            <code className="min-w-0 flex-1 truncate font-mono text-xs">{password}</code>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                navigator.clipboard.writeText(password);
                setCopied(true);
                window.setTimeout(() => setCopied(false), 1500);
              }}
            >
              {copied ? <Check /> : <Copy />}
              {copied ? "Copiada" : "Copiar"}
            </Button>
          </div>
        ) : null}

        <p className="text-xs text-muted-foreground">{ROLE_HINTS[invite.role]}</p>

        <FormError error={accept.error} />

        <Button type="submit" disabled={accept.isPending || mismatch}>
          {accept.isPending ? <Spinner /> : null}
          Crear la cuenta
        </Button>
      </form>
    </AuthLayout>
  );
}
