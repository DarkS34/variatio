import { LogOut, ShieldCheck, Sparkles, UserRound } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/misc";
import { useRouter } from "@/lib/router";
import { ROLE_LABELS, useLogout, useSession } from "@/state/auth";
import { runStore } from "@/state/runStore";
import { cn } from "@/lib/utils";

/**
 * Who is logged in, what they may do here, and where the rest of it lives.
 *
 * Everything the menu used to *do* is now a page: the password and the saved variants are
 * tabs of «Mi perfil», and administering the installation is its own screen, moved out of
 * the navbar so that the tabs up there stay the chain and nothing else. What is left is a
 * list of destinations plus the one action that belongs nowhere else — leaving.
 */
export function AccountMenu() {
  const session = useSession();
  const logout = useLogout();
  const { navigate } = useRouter();
  const [open, setOpen] = useState(false);
  const holder = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!holder.current?.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", away);
    return () => document.removeEventListener("mousedown", away);
  }, [open]);

  const user = session.data?.user;
  if (!user) return null;
  const role = session.data?.role ?? null;

  const go = (path: string) => {
    setOpen(false);
    navigate(path);
  };

  return (
    <div className="relative" ref={holder}>
      <button
        onClick={() => setOpen((was) => !was)}
        title={user.username}
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          "flex size-8 items-center justify-center rounded-full bg-secondary text-xs font-semibold uppercase text-secondary-foreground transition-colors hover:bg-accent",
          open && "ring-2 ring-ring",
        )}
      >
        {initials(user.name || user.username)}
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-10 z-40 w-64 overflow-hidden rounded-lg border border-border bg-card shadow-lg"
        >
          <div className="p-3">
            <p className="truncate text-sm font-medium">{user.name}</p>
            <p className="truncate font-mono text-xs text-muted-foreground">{user.username}</p>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {role ? <Badge variant="outline">{ROLE_LABELS[role]}</Badge> : null}
              {user.is_admin ? <Badge variant="secondary">Administrador</Badge> : null}
            </div>
          </div>

          <Separator />

          <div className="p-1">
            <MenuItem
              icon={<UserRound className="size-4" />}
              label="Perfil"
              onClick={() => go("/perfil")}
            />
            <MenuItem
              icon={<Sparkles className="size-4" />}
              label="Variantes guardadas"
              onClick={() => go("/perfil/variantes")}
            />
            {/* La instalación entera: cuentas, invitaciones, workspaces y el estudio. Vive
                aquí y no en la barra porque aparece para una cuenta de toda la instalación
                y la barra es la cadena de artefactos. */}
            {user.is_admin ? (
              <MenuItem
                icon={<ShieldCheck className="size-4" />}
                label="Administración"
                onClick={() => go("/administracion")}
              />
            ) : null}
          </div>

          <Separator />

          <div className="p-1">
            <MenuItem
              icon={<LogOut className="size-4" />}
              label="Salir"
              onClick={() => {
                setOpen(false);
                // The socket carries the same session; leaving it retrying would keep
                // knocking with a cookie the server has just revoked.
                runStore.disconnect();
                logout.mutate();
              }}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}

function MenuItem({
  icon,
  label,
  onClick,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      role="menuitem"
      onClick={onClick}
      className="flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm transition-colors hover:bg-accent"
    >
      <span className="text-muted-foreground">{icon}</span>
      {label}
    </button>
  );
}

function initials(name: string) {
  const parts = name.split(/[\s@._-]+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts[1]?.[0] ?? "")).slice(0, 2) || "?";
}
