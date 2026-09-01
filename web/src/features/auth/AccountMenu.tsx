import {
  Archive,
  BookOpen,
  Compass,
  LogOut,
  Monitor,
  Moon,
  ShieldCheck,
  Sun,
  UserRound,
} from "lucide-react";
import { useEffect, useRef, useState, useSyncExternalStore } from "react";

import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/misc";
import { useRouter } from "@/lib/router";
import { useT, type Key } from "@/lib/i18n";
import { ROLE_LABEL_KEYS, useLogout, useSession } from "@/state/auth";
import { runStore } from "@/state/runStore";
import { themeStore, type ThemePreference } from "@/state/theme";
import { cn } from "@/lib/utils";


export function AccountMenu() {
  const { t } = useT();
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
        aria-label={t("menu.openAccount", { name: user.username })}
        aria-haspopup="menu"
        aria-expanded={open}
        className={cn(
          "flex size-8 items-center justify-center rounded-full border border-border bg-secondary text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
          open && "bg-accent text-foreground ring-2 ring-ring",
        )}
      >
        <UserRound aria-hidden className="size-4" />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-10 z-40 w-64 overflow-hidden rounded-lg border border-border bg-card shadow-lg"
        >
          <div className="p-3">
            <p className="truncate text-body font-medium">{user.name}</p>
            <p className="truncate font-mono text-small text-muted-foreground">
              {user.username}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-1.5">
              {role ? (
                <Badge variant="outline">{t(ROLE_LABEL_KEYS[role])}</Badge>
              ) : null}
              {user.is_admin ? (
                <Badge variant="secondary">{t("account.admin")}</Badge>
              ) : null}
            </div>
          </div>

          <Separator />

          <div className="p-1">
            <MenuItem
              icon={<UserRound className="size-4" />}
              label={t("menu.profile")}
              onClick={() => go("/account")}
            />
            <MenuItem
              icon={<Archive className="size-4" />}
              label={t("nav.myVariants")}
              onClick={() => go("/account/variants")}
            />
            <MenuItem
              icon={<Compass className="size-4" />}
              label={t("tutorial.again")}
              onClick={() => go("/tutorial")}
            />
            <MenuItem
              icon={<BookOpen className="size-4" />}
              label={t("menu.guide")}
              onClick={() => go("/guide")}
            />
          </div>
          {user.is_admin ? (
            <MenuItem
              icon={<ShieldCheck className="size-4" />}
              label={t("menu.admin")}
              onClick={() => go("/admin")}
              tone="admin"
            />
          ) : null}

          <Separator />
          <ThemeRow />
          <Separator />

          <div className="p-1">
            <MenuItem
              icon={<LogOut className="size-4" />}
              label={t("menu.logout")}
              onClick={() => {
                setOpen(false);
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

const THEMES: { value: ThemePreference; label: Key; icon: React.ReactNode }[] =
  [
    {
      value: "system",
      label: "theme.system",
      icon: <Monitor className="size-4" />,
    },
    { value: "light", label: "theme.light", icon: <Sun className="size-4" /> },
    { value: "dark", label: "theme.dark", icon: <Moon className="size-4" /> },
  ];

function ThemeRow() {
  const { t } = useT();
  const preference = useSyncExternalStore(
    themeStore.subscribe,
    themeStore.getSnapshot,
  );
  return (
    <div className="flex items-center justify-between gap-2 px-3 py-2">
      <span className="text-small text-muted-foreground">
        {t("theme.label")}
      </span>
      <div
        role="radiogroup"
        aria-label={t("theme.label")}
        className="flex rounded-md border border-border p-0.5"
      >
        {THEMES.map((theme) => {
          const on = theme.value === preference;
          return (
            <button
              key={theme.value}
              type="button"
              role="radio"
              aria-checked={on}
              aria-label={t(theme.label)}
              title={t(theme.label)}
              onClick={() => themeStore.set(theme.value)}
              className={cn(
                "flex size-7 items-center justify-center rounded transition-colors",
                on
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-accent",
              )}
            >
              {theme.icon}
            </button>
          );
        })}
      </div>
    </div>
  );
}

function MenuItem({
  icon,
  label,
  onClick,
  tone,
}: {
  icon: React.ReactNode;
  label: string;
  onClick: () => void;
  tone?: "admin";
}) {
  const admin = tone === "admin";
  return (
    <button
      role="menuitem"
      onClick={onClick}
      className={cn(
        "flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-body transition-colors",
        admin
          ? "bg-[color-mix(in_oklab,var(--destructive)_10%,var(--card))] text-destructive hover:bg-[color-mix(in_oklab,var(--destructive)_18%,var(--card))]"
          : "hover:bg-accent",
      )}
    >
      <span className={admin ? "text-destructive" : "text-muted-foreground"}>
        {icon}
      </span>
      {label}
    </button>
  );
}
