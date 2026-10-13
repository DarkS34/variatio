import { Globe } from "lucide-react";

import { LANGUAGES, LANGUAGE_NAMES, localeStore, useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/**
 * The page's language: a globe and two codes, quiet, so it never reads as an action beside
 * the one that is. The store is the application's own, so the demo switches with the page.
 */
export function LanguageSwitch() {
  const { t, language } = useT();
  return (
    <div role="group" aria-label={t("landing.language")} className="flex items-center gap-0.5">
      <Globe aria-hidden className="mr-1 size-4 text-muted-foreground" />
      {LANGUAGES.map((option) => (
        <button
          key={option}
          type="button"
          lang={option}
          aria-label={LANGUAGE_NAMES[option]}
          title={LANGUAGE_NAMES[option]}
          aria-pressed={language === option}
          onClick={() => localeStore.set(option)}
          className={cn(
            "h-7 rounded-md px-2 font-condensed text-small font-semibold uppercase transition-colors",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
            language === option
              ? "bg-sunk text-foreground"
              : "text-muted-foreground hover:text-foreground",
          )}
        >
          {option}
        </button>
      ))}
    </div>
  );
}
