import { useQueryClient } from "@tanstack/react-query";
import { FolderPlus } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { useRouter } from "@/lib/router";
import { authKeys, useIsUnauthenticated, useLogout, useSession } from "@/state/auth";
import { useCreateWorkspace, useStream } from "@/state/queries";

import { AcceptInvite } from "./AcceptInvite";
import { AuthLayout } from "./AuthLayout";
import { LoginScreen } from "./LoginScreen";
import { ResetPassword } from "./ResetPassword";

/**
 * Nothing else in the app renders until this has an answer.
 *
 * Keeping the gate outside `App` rather than inside each screen is what makes "logged
 * out" a single state instead of one 401 per panel: no query fires, the WebSocket is
 * never opened, and the screens keep assuming there is a session, which is true whenever
 * they exist.
 *
 * Two routes are public because they are the ones you reach *without* an account: the
 * invitation link and the password-reset link.
 */
export function AuthGate({ children }: { children: ReactNode }) {
  const { path } = useRouter();
  const token = new URLSearchParams(window.location.search).get("token") ?? "";

  if (path === "/invitacion") {
    return token ? <AcceptInvite token={token} /> : <MissingToken kind="invitación" />;
  }
  if (path === "/restablecer") {
    return token ? <ResetPassword token={token} /> : <MissingToken kind="enlace" />;
  }

  return <Guarded>{children}</Guarded>;
}

function Guarded({ children }: { children: ReactNode }) {
  const session = useSession();
  const unauthenticated = useIsUnauthenticated(session);
  const client = useQueryClient();
  const stream = useStream();

  // The socket is the other half of the session: when the server closes it with 4401 the
  // cookie is gone or revoked, and the cached `me` is a lie until it is re-asked.
  useEffect(() => {
    if (stream.unauthorised) client.invalidateQueries({ queryKey: authKeys.me });
  }, [stream.unauthorised, client]);

  if (session.isLoading) {
    return (
      <div className="flex min-h-full items-center justify-center">
        <Spinner className="size-6 text-muted-foreground" />
      </div>
    );
  }

  if (unauthenticated) return <LoginScreen />;

  if (session.isError) {
    return (
      <AuthLayout title="El servidor no responde">
        <p className="text-body text-muted-foreground">
          {session.error instanceof Error ? session.error.message : "Error desconocido"}
        </p>
        <Button className="mt-4 w-full" onClick={() => session.refetch()}>
          Reintentar
        </Button>
      </AuthLayout>
    );
  }

  // Authenticated, but a member of nothing at all. A real state — an account can exist
  // before anyone grants it access — and not the same as being logged out, so it does not
  // send them back to the login form. Since a workspace is just an instance and any
  // account may open one, the honest offer here is «créate el tuyo», not «espera».
  if (session.data && session.data.role === null) return <NoWorkspace />;

  return <>{children}</>;
}

function NoWorkspace() {
  const session = useSession();
  const logout = useLogout();
  const create = useCreateWorkspace();
  const [name, setName] = useState("");
  const slug = slugify(name);
  const valid = /^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$/.test(slug) && slug !== "default";

  return (
    <AuthLayout
      title="Todavía no tienes ningún workspace"
      description="Un workspace es una instancia entera: su corpus, su grafo, su perfil y su banco."
    >
      <p className="text-body text-muted-foreground">
        Puedes esperar a que te inviten a uno existente, o empezar el tuyo ahora mismo.
        Entraste como{" "}
        <span className="font-medium text-foreground">{session.data?.user.username}</span>.
      </p>

      <form
        className="mt-4 space-y-2"
        onSubmit={(event) => {
          event.preventDefault();
          if (valid) create.mutate({ slug, name: name.trim() });
        }}
      >
        <Input
          aria-label="Nombre de la asignatura"
          placeholder="Nombre de la asignatura"
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
        {create.isError ? (
          <p className="text-small text-destructive">{(create.error as Error).message}</p>
        ) : slug ? (
          <p className="font-mono text-[11px] text-muted-foreground">{slug}</p>
        ) : null}
        <Button type="submit" className="w-full" disabled={!valid || create.isPending}>
          <FolderPlus />
          Crear mi workspace
        </Button>
      </form>

      <Button variant="outline" className="mt-2 w-full" onClick={() => logout.mutate()}>
        Salir
      </Button>
    </AuthLayout>
  );
}

function slugify(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 64);
}

function MissingToken({ kind }: { kind: string }) {
  return (
    <AuthLayout
      title={`Falta el código de la ${kind}`}
      description="Abre el enlace completo tal y como lo recibiste."
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
