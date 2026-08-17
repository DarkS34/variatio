import { useState, type FormEvent } from "react";
import { ArrowRight, Check, KeyRound, UserRound } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label } from "@/components/ui/input";
import { Alert, Skeleton, Spinner } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import { FormError } from "@/features/auth/AuthLayout";
import { GenerationsPanel } from "@/features/generations/GenerationsPanel";
import { useRouter } from "@/lib/router";
import {
  ROLE_HINTS,
  ROLE_LABELS,
  useChangePassword,
  useSession,
  useUpdateProfile,
} from "@/state/auth";
import { useActiveWorkspace, useSwitchWorkspace, useWorkspaces } from "@/state/queries";

/**
 * Everything that belongs to the person using the app, in one place.
 *
 * It exists because these three things were scattered: the password was a dialog in the
 * avatar menu, the saved variants were a route of their own, and which instances an
 * account may enter was nowhere at all. None of them is a step of the chain — the navbar
 * is the chain — so none of them belongs in the navbar, and a menu of four destinations
 * is a menu, not an answer. This is the answer: one page, one tab per question.
 *
 * The list of open sessions used to be a fourth card and is gone (2026-08-17, explicit
 * user request). It answered a question nobody here was asking — this is a closed group
 * with accounts handed out by hand — and «cerrar las demás» is already covered by changing
 * the password, which revokes every other session as part of the same transaction.
 *
 * The tab lives in the URL rather than in state so that «mis variantes» stays a link that
 * can be sent, bookmarked and reloaded.
 */
export const ACCOUNT_TABS = [
  { value: "cuenta", label: "Cuenta", path: "/perfil" },
  { value: "variantes", label: "Variantes", path: "/perfil/variantes" },
  { value: "accesos", label: "Accesos", path: "/perfil/accesos" },
] as const;

export type AccountTab = (typeof ACCOUNT_TABS)[number]["value"];

export function AccountScreen({ tab }: { tab: AccountTab }) {
  const session = useSession();
  const { navigate } = useRouter();
  const user = session.data?.user;

  if (!user) return <Skeleton className="h-96" />;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="text-xl font-semibold tracking-tight">Mi perfil</h1>
        <InfoHint label="Qué hay aquí">
          Tu cuenta y lo que es tuyo: los datos con los que entras, las variantes que has
          generado y los workspaces a los que tienes acceso. Nada de esto es parte de la
          cadena de artefactos, por eso no está en la barra de arriba.
        </InfoHint>
        <span className="font-mono text-sm text-muted-foreground">{user.username}</span>
        {user.is_admin ? <Badge variant="secondary">Administrador</Badge> : null}
      </header>

      <Tabs
        items={ACCOUNT_TABS.map(({ value, label }) => ({ value, label }))}
        value={tab}
        onChange={(next) => {
          const target = ACCOUNT_TABS.find((item) => item.value === next);
          if (target) navigate(target.path);
        }}
      />

      {tab === "cuenta" ? <AccountTabView /> : null}
      {tab === "variantes" ? <GenerationsPanel /> : null}
      {tab === "accesos" ? <AccessTab /> : null}
    </div>
  );
}

/* Cuenta ------------------------------------------------------------------------------ */

function AccountTabView() {
  return (
    <div className="grid items-start gap-4 lg:grid-cols-2">
      <IdentityCard />
      <PasswordCard />
    </div>
  );
}

/**
 * The two fields an account may change about itself.
 *
 * The username is not one of them and is shown as text: it is what every message prints
 * and what every row points at, so renaming it would quietly rewrite who wrote what. The
 * address is optional on purpose — invitations are handed over by hand here — and it says
 * what it is *for* rather than pretending to be a second identity.
 */
function IdentityCard() {
  const session = useSession();
  const update = useUpdateProfile();
  const user = session.data?.user;
  const [name, setName] = useState(user?.name ?? "");
  const [email, setEmail] = useState(user?.email ?? "");

  if (!user) return null;
  const dirty = name.trim() !== user.name || (email.trim() || null) !== user.email;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    update.mutate({ name: name.trim(), email: email.trim() || null });
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <UserRound className="size-4 text-muted-foreground" />
          Datos de la cuenta
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <Label>Usuario</Label>
            <p className="rounded-md border border-dashed border-border px-3 py-2 font-mono text-sm text-muted-foreground">
              {user.username}
            </p>
            <p className="text-xs text-muted-foreground">
              No se puede cambiar: es lo que identifica todo lo que has hecho.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="account-name">Nombre</Label>
            <Input
              id="account-name"
              value={name}
              maxLength={200}
              onChange={(event) => setName(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Como apareces para el resto en este workspace.
            </p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="account-email">Correo (opcional)</Label>
            <Input
              id="account-email"
              type="email"
              autoComplete="email"
              placeholder="sin correo"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">
              Solo sirve para recibir el enlace de restablecer la contraseña. No se entra
              con él y no lo ve nadie más.
            </p>
          </div>

          <FormError error={update.error} />

          <div className="flex items-center gap-2">
            <Button type="submit" disabled={!dirty || update.isPending}>
              {update.isPending ? <Spinner /> : null}
              Guardar
            </Button>
            {update.isSuccess && !dirty ? (
              <span className="flex items-center gap-1 text-xs text-[var(--success)]">
                <Check className="size-3.5" />
                Guardado
              </span>
            ) : null}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

/** The old dialog, on the page. Same contract, said out loud: changing the password signs
 *  out every other device, because the usual reason to change it is a suspicion. */
function PasswordCard() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const change = useChangePassword();

  const mismatch = repeat.length > 0 && next !== repeat;

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (mismatch) return;
    change.mutate(
      { current, next },
      {
        onSuccess: () => {
          setCurrent("");
          setNext("");
          setRepeat("");
        },
      },
    );
  };

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="flex items-center gap-2">
          <KeyRound className="size-4 text-muted-foreground" />
          Contraseña
        </CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={submit} className="space-y-4">
          <p className="text-xs text-muted-foreground">
            Al cambiarla se cierra la sesión en el resto de dispositivos; esta pestaña
            sigue abierta con una sesión nueva.
          </p>

          <div className="space-y-1.5">
            <Label htmlFor="current-password">Contraseña actual</Label>
            <Input
              id="current-password"
              type="password"
              autoComplete="current-password"
              required
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="next-password">Nueva</Label>
            <Input
              id="next-password"
              type="password"
              autoComplete="new-password"
              required
              value={next}
              onChange={(event) => setNext(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">Al menos 12 caracteres.</p>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="repeat-password">Repítela</Label>
            <Input
              id="repeat-password"
              type="password"
              autoComplete="new-password"
              required
              value={repeat}
              onChange={(event) => setRepeat(event.target.value)}
            />
            {mismatch ? <p className="text-xs text-destructive">Las dos no coinciden.</p> : null}
          </div>

          <FormError error={change.error} />

          <div className="flex items-center gap-2">
            <Button type="submit" disabled={change.isPending || mismatch}>
              {change.isPending ? <Spinner /> : null}
              Cambiar la contraseña
            </Button>
            {change.isSuccess ? (
              <span className="flex items-center gap-1 text-xs text-[var(--success)]">
                <Check className="size-3.5" />
                Cambiada
              </span>
            ) : null}
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

/* Accesos ----------------------------------------------------------------------------- */

/**
 * Which instances this account may enter, and on what grounds.
 *
 * It reads `/api/workspaces` rather than the session's membership list, because those two
 * are not the same question for an administrator: the session appends whichever workspace
 * they are standing in even when they are not a member of it, and it labels that
 * «Propietario» — which is what the bypass grants, not what anybody wrote in a row. The
 * listing carries `as_admin`, so the row can say «por administración» and be true.
 *
 * Read-only on purpose: a membership is a row only the installation's administrator
 * writes, and a screen that offered to change it here would be offering a 403.
 */
function AccessTab() {
  const listing = useWorkspaces();
  const active = useActiveWorkspace();
  const switching = useSwitchWorkspace();
  const workspaces = listing.data?.workspaces ?? [];
  const current = active ?? listing.data?.active ?? null;
  const mine = workspaces.filter((workspace) => !workspace.as_admin);

  return (
    <div className="space-y-4">
      <Alert tone="info" title="Los accesos los concede quien administra la instalación">
        <p>
          No hay registro abierto: se entra por invitación, y quien te da acceso a una
          instancia es la misma persona. Aquí solo se lee lo que ya tienes concedido.
        </p>
      </Alert>

      {listing.isLoading ? <Spinner /> : null}

      {!listing.isLoading && mine.length === 0 ? (
        <Alert tone="warning" title="Tu cuenta no es miembro de ningún workspace">
          <p>
            Puedes entrar en la aplicación, pero no verás ninguna instancia hasta que te
            den acceso a una — o hasta que crees la tuya desde el selector de arriba.
          </p>
        </Alert>
      ) : null}

      {workspaces.length > 0 ? (
        <ul className="divide-y divide-border rounded-xl border border-border">
          {workspaces.map((workspace) => (
            <li key={workspace.slug} className="flex flex-wrap items-center gap-3 p-3">
              <div className="min-w-0 flex-1">
                <p className="flex flex-wrap items-center gap-2 truncate text-sm font-medium">
                  {workspace.name}
                  <span className="font-mono text-xs text-muted-foreground">
                    {workspace.slug}
                  </span>
                  {workspace.slug === current ? (
                    <Badge variant="secondary">en uso</Badge>
                  ) : null}
                </p>
                <p className="text-xs text-muted-foreground">
                  {workspace.as_admin
                    ? "No eres miembro: entras porque administras la instalación."
                    : workspace.role
                      ? ROLE_HINTS[workspace.role]
                      : "Sin permiso declarado."}
                </p>
              </div>
              {workspace.as_admin ? (
                <Badge variant="secondary">por administración</Badge>
              ) : workspace.role ? (
                <Badge variant="outline">{ROLE_LABELS[workspace.role]}</Badge>
              ) : null}
              {workspace.slug === current ? null : (
                <Button
                  size="sm"
                  variant="ghost"
                  disabled={switching.isPending}
                  onClick={() => switching.mutate(workspace.slug)}
                >
                  Entrar
                  <ArrowRight />
                </Button>
              )}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
