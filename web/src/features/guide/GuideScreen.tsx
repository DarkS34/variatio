import { ArrowRight, ChevronDown, Search } from "lucide-react";
import { Suspense, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator, Skeleton } from "@/components/ui/misc";
import { Link } from "@/lib/router";
import { fold } from "@/lib/text";
import { cn } from "@/lib/utils";
import { useT, type Key } from "@/lib/i18n";
import { GUIDE_SECTIONS, useGuideBody, type GuideSection } from "./sections";

function grouped(sections: readonly GuideSection[]): { key: Key; sections: GuideSection[] }[] {
  const groups: { key: Key; sections: GuideSection[] }[] = [];
  for (const section of sections) {
    const last = groups[groups.length - 1];
    if (last && last.key === section.groupKey) last.sections.push(section);
    else groups.push({ key: section.groupKey, sections: [section] });
  }
  return groups;
}

export function GuideScreen({ slug }: { slug: string }) {
  const { t } = useT();
  const [query, setQuery] = useState("");
  const [navOpen, setNavOpen] = useState(false);

  const position = GUIDE_SECTIONS.findIndex((section) => section.slug === slug);
  const active = GUIDE_SECTIONS[position] ?? GUIDE_SECTIONS[0];
  const next = GUIDE_SECTIONS[(position < 0 ? 0 : position) + 1] ?? null;

  const groups = useMemo(() => {
    const needle = fold(query.trim());
    if (!needle) return grouped(GUIDE_SECTIONS);
    return grouped(
      GUIDE_SECTIONS.filter(
        (section) =>
          fold(t(section.labelKey)).includes(needle) ||
          fold(t(section.groupKey)).includes(needle),
      ),
    );
  }, [query, t]);

  const Body = useGuideBody(active.slug);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1.5">
          <h1 className="font-display font-expanded text-display">{t("guide.title")}</h1>
          <p className="max-w-[74ch] text-body text-muted-foreground">{t("guide.intro")}</p>
        </div>

        <div className="relative w-full sm:w-64">
          <Search
            aria-hidden
            className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground"
          />
          <Input
            aria-label={t("guide.search")}
            placeholder={t("guide.search")}
            className="pl-9"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </header>

      <Separator />

      {/* The index is a column beside the text on a laptop and a folded list on a phone.
          Folded rather than merely stacked: fourteen rows of navigation above the first
          paragraph turns "leer la guía" into "pasar la guía", and the section you are on
          is already named on the button that opens it. */}
      <div className="grid items-start gap-4 lg:grid-cols-[16rem_minmax(0,1fr)] lg:gap-8">
        <Button
          variant="outline"
          className="w-full justify-between lg:hidden"
          aria-expanded={navOpen}
          onClick={() => setNavOpen((was) => !was)}
        >
          <span className="min-w-0 truncate">
            {t("guide.sectionsOf", { label: t(active.labelKey) })}
          </span>
          <ChevronDown className={cn("transition-transform", navOpen && "rotate-180")} />
        </Button>

        <nav
          aria-label={t("guide.nav")}
          className={cn(
            "space-y-4 lg:sticky lg:top-20 lg:block",
            navOpen ? "block" : "hidden",
          )}
        >
          {groups.map((group) => (
            <div key={group.key} className="space-y-0.5">
              <p className="px-2.5 pb-1 text-micro font-condensed uppercase text-muted-foreground">
                {t(group.key)}
              </p>
              {group.sections.map((section) => {
                const Icon = section.icon;
                const on = section.slug === active.slug;
                return (
                  <Link
                    key={section.slug}
                    to={`/guide/${section.slug}`}
                    aria-current={on ? "page" : undefined}
                    onClick={() => setNavOpen(false)}
                    className={cn(
                      "flex items-center gap-2 border-l-2 border-transparent px-2.5 py-1.5 text-body text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                      on && "border-primary bg-accent font-medium text-foreground",
                    )}
                  >
                    <Icon className="size-4 shrink-0" />
                    <span className="min-w-0 truncate">{t(section.labelKey)}</span>
                  </Link>
                );
              })}
            </div>
          ))}

          {groups.length === 0 ? (
            <p className="px-2.5 text-small text-muted-foreground">
              {t("guide.noMatch")}
            </p>
          ) : null}
        </nav>

        <div className="min-w-0 space-y-6">
          {/* The boundary goes HERE and not around the screen. `App` already wraps every
              route in one, but that one would replace the whole page — nav, search and
              all — while a prose tree loads, which reads as having navigated away rather
              than as a section arriving. */}
          <Suspense fallback={<Skeleton className="h-96" />}>
            <Body />
          </Suspense>

          {next ? (
            <>
              <Separator />
              <Link
                to={`/guide/${next.slug}`}
                className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card p-4 transition-colors hover:bg-accent"
              >
                <span>
                  <span className="block text-micro font-condensed uppercase text-muted-foreground">
                    {t("guide.next")}
                  </span>
                  <span className="text-body font-medium">{t(next.labelKey)}</span>
                </span>
                <ArrowRight aria-hidden className="size-4 shrink-0 text-muted-foreground" />
              </Link>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
