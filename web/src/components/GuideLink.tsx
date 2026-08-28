import { BookOpen } from "lucide-react";

import { GUIDE_SECTIONS, type GuideSlug } from "@/features/guide/sections";
import { useT } from "@/lib/i18n";
import { Link } from "@/lib/router";
import { cn } from "@/lib/utils";

/**
 * THE WAY FROM A SCREEN TO THE PAGE THAT EXPLAINS IT.
 *
 * The guide is written and complete and almost nobody arrives at it, because reaching it
 * means leaving what you are doing, opening a menu and choosing among eleven sections —
 * from a screen that already knows which one it needs. This is that link, beside the
 * title, on every screen that has a section to point at.
 *
 * It takes a `GuideSlug` and not a string, so a section that is renamed or removed breaks
 * the build at every call site rather than silently landing readers on «Empezar»:
 * `GuideScreen` falls back to the first section for an unknown slug, which is the right
 * behaviour for a typed URL and the wrong one for a link we wrote ourselves.
 *
 * It is a LINK and not a button, and it sits on the title's baseline rather than in the
 * screen's action row: the actions of a screen change its instance, and this one changes
 * nothing. `InfoHint` stays where it is and answers a different question — an (i) explains
 * one control in one sentence, this offers the page behind the whole screen.
 */
export function GuideLink({ slug, className }: { slug: GuideSlug; className?: string }) {
  const { t } = useT();
  const section = GUIDE_SECTIONS.find((entry) => entry.slug === slug);
  if (!section) return null;

  return (
    <Link
      to={`/guide/${slug}`}
      className={cn(
        "inline-flex shrink-0 items-center gap-1.5 border-b border-muted-foreground/35 pb-px text-small text-muted-foreground transition-colors hover:border-foreground hover:text-foreground",
        className,
      )}
    >
      <BookOpen aria-hidden className="size-3.5 shrink-0" />
      {t("guide.linkTo", { section: t(section.labelKey) })}
    </Link>
  );
}
