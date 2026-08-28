import { FolderPlus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { LANGUAGES, LANGUAGE_NAMES, useLanguage, useT, type Language } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/ui/misc";
import { useSession } from "@/state/auth";
import { useCreateWorkspace } from "@/state/queries";

/**
 * What the panel says to an account that is in no instance.
 *
 * It is a screen and not a gate, and that is the whole point of it. Until 2026-08-26 the
 * installation had a workspace called `default` that every entry point fell back to, so
 * «no tengo ninguno» was not a state the app could be in: an account either landed in
 * somebody's instance or was stopped by a full-page notice outside the shell, before the
 * navigation, the account menu and the guide had rendered. None of those needs a
 * workspace. So the message moved inside: the shell is up, `/guide` and `/account` are
 * reachable, and what sits in the middle of the panel is the one thing there is to do
 * here — start an instance, which is what a workspace is.
 */
export function NoWorkspace() {
  const session = useSession();
  const create = useCreateWorkspace();
  const { t } = useT();
  const [name, setName] = useState("");
  // The first workspace of an installation, so this is the most expensive place to get the
  // prompt language wrong: nothing after the first build can change it.
  const [language, setLanguage] = useState<Language>(useLanguage());
  const slug = slugify(name);
  const valid = /^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$/.test(slug);

  return (
    <div className="space-y-6">
      <header className="flex items-center gap-2">
        <h1 className="font-display font-expanded text-display">{t("nav.dashboard")}</h1>
      </header>

      <EmptyState
        icon={<FolderPlus />}
        title={t("workspace.noneYet")}
        action={
          <form
            className="w-full max-w-sm space-y-2 text-left"
            onSubmit={(event) => {
              event.preventDefault();
              if (valid) create.mutate({ slug, name: name.trim(), language });
            }}
          >
            <Input
              aria-label={t("workspace.subjectName")}
              placeholder={t("workspace.subjectName")}
              value={name}
              onChange={(event) => setName(event.target.value)}
            />

            <div className="flex flex-col gap-1">
              <span className="text-small text-muted-foreground">
                {t("workspace.language.title")}
              </span>
              <div
                role="group"
                aria-label={t("workspace.language.title")}
                className="flex gap-1"
              >
                {LANGUAGES.map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setLanguage(option)}
                    aria-pressed={language === option}
                    className={cn(
                      "h-9 flex-1 border text-small font-medium transition-colors",
                      language === option
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-border bg-card hover:bg-accent/60",
                    )}
                  >
                    {LANGUAGE_NAMES[option]}
                  </button>
                ))}
              </div>
              <span className="text-small text-muted-foreground">
                {t("workspace.language.onlyAtCreation")}
              </span>
            </div>
            {create.isError ? (
              <p className="text-small text-destructive">{(create.error as Error).message}</p>
            ) : slug ? (
              <p className="font-mono text-[11px] text-muted-foreground">{slug}</p>
            ) : null}
            <Button type="submit" className="w-full" disabled={!valid || create.isPending}>
              <FolderPlus />
              {t("noWorkspace.createMine")}
            </Button>
          </form>
        }
      >
        <p>
          {t("noWorkspace.bodyA")}{" "}
          <span className="font-medium text-foreground">{session.data?.user.username}</span>
          {t("noWorkspace.bodyB")}
        </p>
      </EmptyState>
    </div>
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
