import { ArrowRight, Search } from "lucide-react";
import { useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/misc";
import { Link } from "@/lib/router";
import { cn } from "@/lib/utils";
import { GUIDE_SECTIONS, type GuideSection } from "./sections";

const fold = (text: string) =>
  Array.from(text.normalize("NFD"))
    .filter((glyph) => glyph.charCodeAt(0) < 0x300 || glyph.charCodeAt(0) > 0x36f)
    .join("")
    .toLowerCase();

function grouped(sections: GuideSection[]): { title: string; sections: GuideSection[] }[] {
  const groups: { title: string; sections: GuideSection[] }[] = [];
  for (const section of sections) {
    const last = groups[groups.length - 1];
    if (last && last.title === section.group) last.sections.push(section);
    else groups.push({ title: section.group, sections: [section] });
  }
  return groups;
}

export function GuideScreen({ slug }: { slug: string }) {
  const [query, setQuery] = useState("");

  const position = GUIDE_SECTIONS.findIndex((section) => section.slug === slug);
  const active = GUIDE_SECTIONS[position] ?? GUIDE_SECTIONS[0];
  const next = GUIDE_SECTIONS[(position < 0 ? 0 : position) + 1] ?? null;

  const groups = useMemo(() => {
    const needle = fold(query.trim());
    if (!needle) return grouped(GUIDE_SECTIONS);
    return grouped(
      GUIDE_SECTIONS.filter(
        (section) =>
          fold(section.label).includes(needle) || fold(section.group).includes(needle),
      ),
    );
  }, [query]);

  const Body = active.body;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="space-y-1.5">
          <h1 className="font-display font-expanded text-display">Guía</h1>
          <p className="max-w-[74ch] text-body text-muted-foreground">
            Qué hace cada parte del sistema, en qué orden se usan y qué mirar cuando algo no sale.
            Nada de lo que hay aquí cambia el estado de tu instancia: es lectura.
          </p>
        </div>

        <div className="relative w-64">
          <Search
            aria-hidden
            className="pointer-events-none absolute left-3 top-2.5 size-4 text-muted-foreground"
          />
          <Input
            aria-label="Buscar una sección"
            placeholder="Buscar una sección"
            className="pl-9"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>
      </header>

      <Separator />

      <div className="grid items-start gap-8 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <nav aria-label="Secciones de la guía" className="space-y-4 lg:sticky lg:top-20">
          {groups.map((group) => (
            <div key={group.title} className="space-y-0.5">
              <p className="px-2.5 pb-1 text-micro font-condensed uppercase text-muted-foreground">
                {group.title}
              </p>
              {group.sections.map((section) => {
                const Icon = section.icon;
                const on = section.slug === active.slug;
                return (
                  <Link
                    key={section.slug}
                    to={`/guia/${section.slug}`}
                    aria-current={on ? "page" : undefined}
                    className={cn(
                      "flex items-center gap-2 border-l-2 border-transparent px-2.5 py-1.5 text-body text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                      on && "border-primary bg-accent font-medium text-foreground",
                    )}
                  >
                    <Icon className="size-4 shrink-0" />
                    <span className="min-w-0 truncate">{section.label}</span>
                  </Link>
                );
              })}
            </div>
          ))}

          {groups.length === 0 ? (
            <p className="px-2.5 text-small text-muted-foreground">
              Nada coincide con esa búsqueda.
            </p>
          ) : null}
        </nav>

        <div className="min-w-0 space-y-6">
          <Body />

          {next ? (
            <>
              <Separator />
              <Link
                to={`/guia/${next.slug}`}
                className="flex items-center justify-between gap-3 rounded-lg border border-border bg-card p-4 transition-colors hover:bg-accent"
              >
                <span>
                  <span className="block text-micro font-condensed uppercase text-muted-foreground">
                    Siguiente
                  </span>
                  <span className="text-body font-medium">{next.label}</span>
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
