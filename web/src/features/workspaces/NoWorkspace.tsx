import { FolderPlus } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { LANGUAGES, LANGUAGE_NAMES, useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { Input } from "@/components/ui/input";
import { EmptyState, Spinner } from "@/components/ui/misc";
import { useSession } from "@/state/auth";
import { useCreateWorkspace } from "@/state/queries";
import { usePromptLanguage } from "./promptLanguage";

/**
 * What is said to an account that is in no instance.
 *
 * A screen and NOT a gate, which is the whole point: the shell is up and `/guide` and
 * `/account` are reachable, because none of them needs a workspace. What sits in the middle
 * is the one thing there is to do here — start a subject.
 */
export function NoWorkspace() {
  const session = useSession();
  const create = useCreateWorkspace();
  const { t } = useT();
  const [name, setName] = useState("");
  // Whether the form has been submitted once: the error only appears after a press,
  // never while somebody is still typing the first letter.
  const [touched, setTouched] = useState(false);
  // The first workspace of an installation, so this is the most expensive place to get the
  // prompt language wrong: nothing after the first build can change it.
  const [language, setLanguage] = usePromptLanguage();
  const slug = slugify(name);
  const valid = /^[a-z0-9][a-z0-9-]{1,62}[a-z0-9]$/.test(slug);

  // THE EMPTY STATE IS THE SCREEN, so it carries the `h1` and there is no header above it.
  // The heading that was here said "Panel" — `t("nav.dashboard")`, the name of the panel
  // deleted on 2026-08-31, whose entry in the register is "THERE IS NO PANEL" — so the first
  // word an account read after redeeming an invitation named a screen this application has
  // not had for a week, sitting over "Todavía no tienes ninguna asignatura", which is what
  // the page actually says. Deleting it outright left the page with no heading at all, since
  // `EmptyState` titles with a `p`: hence `titleAs`, which puts the `h1` on the sentence that
  // was already the title rather than inventing a second one. `nav.dashboard` had no other
  // reader and left both catalogues with it.
  return (
    <div className="space-y-6">
      <EmptyState
        icon={<FolderPlus />}
        title={t("workspace.noneYet")}
        titleAs="h1"
        action={
          <form
            className="w-full max-w-sm space-y-2 text-left"
            onSubmit={(event) => {
              event.preventDefault();
              setTouched(true);
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
              <p className="font-mono text-[12px] text-muted-foreground">{slug}</p>
            ) : null}
            {/* ENABLED WITH AN EMPTY NAME, AND THAT IS THE POINT. This is the only control
                on the only screen the account can reach, and it greeted everybody greyed
                out with nothing saying why — "prevención de errores" applied so early that
                it stops being prevention and becomes a dead end. It validates on press
                instead, and says what is missing. `create.isPending` still disables it:
                that one is a real reason, and it is visible as a spinner. */}
            <Button type="submit" className="w-full" disabled={create.isPending}>
              {create.isPending ? <Spinner /> : <FolderPlus />}
              {t("noWorkspace.createMine")}
            </Button>
            {touched && !valid ? (
              <p className="text-small text-destructive">{t("workspace.nameRequired")}</p>
            ) : null}
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
