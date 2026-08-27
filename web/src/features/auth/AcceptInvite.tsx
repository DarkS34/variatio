import { useQuery } from "@tanstack/react-query";
import { Eye, EyeOff } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { PROFILES, PROFILE_SELF_LABELS } from "@/lib/evaluator";
import { useRouter } from "@/lib/router";
import type { EvaluatorProfile } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ROLE_HINTS, ROLE_LABELS, useAcceptInvite } from "@/state/auth";

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

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (mismatch || !profile) return;
    accept.mutate({
      token,
      username: username.trim(),
      name: name.trim(),
      password,
      evaluator_profile: profile,
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
          <p className="text-small text-muted-foreground">
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

        {/* Asked here and only here. Whoever invited had no field for it: the link binds the
            access and nothing else, and this is the one moment the person is in front of a
            form — asking mid-comparison gets an answer of convenience. It is not a
            permission, and an administrator corrects it from the panel afterwards. */}
        <div className="flex flex-col gap-1.5">
          <Label id="invite-profile-label">¿Eres estudiante o docente?</Label>
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
                {PROFILE_SELF_LABELS[option]}
              </button>
            ))}
          </div>
          <p className="text-small text-muted-foreground">
            Decide qué se te preguntará cuando compares ejercicios. No cambia lo que puedes
            hacer aquí.
          </p>
        </div>

        <div className="flex flex-col gap-1.5">
          <Label htmlFor="invite-password">Contraseña</Label>
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
              title={visible ? "Ocultar" : "Ver"}
              className="absolute inset-y-0 right-0 flex w-10 items-center justify-center text-muted-foreground transition-colors hover:text-foreground"
            >
              {visible ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          <p className="text-small text-muted-foreground">
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
          {mismatch ? <p className="text-small text-destructive">Las dos no coinciden.</p> : null}
        </div>

        <p className="text-small text-muted-foreground">{ROLE_HINTS[invite.role]}</p>

        <FormError error={accept.error} />

        <Button type="submit" disabled={accept.isPending || mismatch || !profile}>
          {accept.isPending ? <Spinner /> : null}
          Crear la cuenta
        </Button>
      </form>
    </AuthLayout>
  );
}
