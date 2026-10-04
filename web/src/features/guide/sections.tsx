import {
  Activity,
  Compass,
  FileText,
  Files,
  Layers,
  Library,
  LifeBuoy,
  MessagesSquare,
  Network,
  Play,
  Scale,
  ShieldCheck,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { lazy, useMemo, type ComponentType, type ReactNode } from "react";

import { useT, withCatalogues, type Key, type Language } from "@/lib/i18n";
import type { Features } from "@/lib/types";
import { useFeatures } from "@/state/auth";

/**
 * The guide's registry: what sections exist, in what order, and under which group.
 *
 * THE BODIES ARE A TREE PER LANGUAGE AND NOT A KEY PER PARAGRAPH. Everywhere else in the
 * app a sentence is a catalogue entry, because a sentence is a label sitting between two
 * controls. Here a section is a page of prose with its own headings, its own tables and
 * its own asides, and cutting it into three hundred keys would translate the words while
 * losing the writing: a paragraph that has to be rephrased in English, or split, or given
 * a different example, cannot be a `{n}`-shaped substitution of the Spanish one.
 *
 * What stays in the catalogue is what the NAVIGATION needs — the section names and the
 * group headings — because those are read by `GuideScreen`'s search and index, not by the
 * page itself.
 */
export interface GuideSection {
  slug: string;
  labelKey: Key;
  groupKey: Key;
  icon: LucideIcon;
  /**
   * The optional function the section explains, whose folder holds its body. Closed to the
   * account, the section is not in the index, the search or the routing, and its body is
   * never fetched.
   */
  feature?: keyof Features;
}

/**
 * THE TREES ARE FETCHED, THE REGISTRY IS NOT.
 *
 * Each prose tree is ~46 kB of the guide's 102 kB chunk, and a reader needs one of them.
 * `GUIDE_SECTIONS` below stays static because the index, the search and the "Siguiente"
 * link are drawn from it before any body is read.
 *
 * `React.lazy` wraps the LOOKUP rather than the module, which is what lets both 1 300-line
 * files stay exactly as they are: the promise resolves to a component that takes a slug
 * and renders that entry of the tree it just loaded.
 *
 * What this gives up is the runtime `?? ES[slug]` fallback for a slug the English tree has
 * not caught up with — it cannot survive the split, because restoring it would have
 * `en/sections` import `es/sections` and re-merge the two chunks. It guards a state the
 * build already forbids: `scripts/check-i18n.mjs` fails when the two trees do not answer
 * for the same set of slugs, so the gate is what holds the property now.
 */
function tree(load: () => Promise<{ BODIES: Record<string, () => ReactNode> }>) {
  return lazy(async () => {
    const { BODIES } = await withCatalogues(load());
    const Body: ComponentType<{ slug: string }> = ({ slug }) => {
      const Section = BODIES[slug];
      return Section ? <Section /> : null;
    };
    return { default: Body };
  });
}

/**
 * Where a section's body lives: the guide's own trees, or the folder of the function the
 * section explains. A function's sections are fetched with the function's code and never
 * with the guide's, so an account it is closed to downloads none of them.
 */
type Home = "guide" | keyof Features;

const TREES: Record<Home, Record<Language, ComponentType<{ slug: string }>>> = {
  guide: {
    es: tree(() => import("./es/sections")),
    en: tree(() => import("./en/sections")),
  },
  evaluation: {
    es: tree(() => import("@/evaluation/guide/es")),
    en: tree(() => import("@/evaluation/guide/en")),
  },
  tutor: {
    es: tree(() => import("@/tutor/guide/es")),
    en: tree(() => import("@/tutor/guide/en")),
  },
};

export const GUIDE_SECTIONS = [
  {
    slug: "start",
    labelKey: "guide.sec.start",
    groupKey: "guide.group.start",
    icon: Compass,
  },
  {
    slug: "workspace",
    labelKey: "guide.sec.workspace",
    groupKey: "guide.group.start",
    icon: Layers,
  },
  // First of the construction, because it is genuinely the first thing a new workspace does
  // and the one step that decides how long all three builds feel. Step 1 of the bar, though
  // not a stage: it produces no artifact and nobody approves it.
  {
    slug: "raw",
    labelKey: "guide.sec.raw",
    groupKey: "guide.group.prepare",
    icon: Files,
  },
  {
    slug: "profile",
    labelKey: "guide.sec.profile",
    groupKey: "guide.group.prepare",
    icon: FileText,
  },
  {
    slug: "graph",
    labelKey: "guide.sec.graph",
    groupKey: "guide.group.prepare",
    icon: Network,
  },
  {
    slug: "bank",
    labelKey: "guide.sec.bank",
    groupKey: "guide.group.prepare",
    icon: Library,
  },
  { slug: "generate", labelKey: "guide.sec.generate", groupKey: "guide.group.use", icon: Play },
  {
    slug: "evaluate",
    labelKey: "guide.sec.evaluate",
    groupKey: "guide.group.use",
    icon: Scale,
    feature: "evaluation",
  },
  {
    slug: "tutor",
    labelKey: "guide.sec.tutor",
    groupKey: "guide.group.use",
    icon: MessagesSquare,
    feature: "tutor",
  },
  {
    slug: "runs",
    labelKey: "guide.sec.runs",
    groupKey: "guide.group.daily",
    icon: Activity,
  },
  {
    slug: "account",
    labelKey: "guide.sec.account",
    groupKey: "guide.group.daily",
    icon: UserRound,
  },
  // In "Día a día" rather than "Fase de pruebas": running the installation is not something
  // done with a built subject. One section for the panel's six tabs, the two optional
  // functions' tabs included.
  {
    slug: "admin",
    labelKey: "guide.sec.admin",
    groupKey: "guide.group.daily",
    icon: ShieldCheck,
  },
  {
    slug: "troubleshooting",
    labelKey: "guide.sec.troubleshooting",
    groupKey: "guide.group.daily",
    icon: LifeBuoy,
  },
] as const satisfies readonly GuideSection[];

/**
 * The slugs, as a union rather than as `string`.
 *
 * `GuideScreen` falls back to the first section for a slug it does not know, which is
 * right for a URL somebody typed and wrong for a link the application wrote: a renamed
 * section would go on "working", landing every reader on "Empezar". `GuideLink` takes this
 * type, so the rename is a build error at every call site instead.
 */
export type GuideSlug = (typeof GUIDE_SECTIONS)[number]["slug"];

/** The sections this account may read, in registry order: none of a function closed to it. */
export function sectionsFor(features: Features): GuideSection[] {
  return GUIDE_SECTIONS.filter(
    (section: GuideSection) => section.feature === undefined || features[section.feature],
  );
}

/**
 * The index, the search and the routing of the guide for this account.
 *
 * A slug left out here is one the screen does not know, so a link to it falls back the way
 * a URL somebody mistyped does.
 */
export function useGuideSections(): GuideSection[] {
  const { evaluation, tutor } = useFeatures();
  return useMemo(() => sectionsFor({ evaluation, tutor }), [evaluation, tutor]);
}

/**
 * The section's body in the reader's language, as a component that suspends while its
 * tree is on the way. `GuideScreen` puts the boundary around this and nothing else, so a
 * section change never blanks the nav beside it.
 */
export function useGuideBody(section: GuideSection): () => ReactNode {
  const { language } = useT();
  const home = TREES[section.feature ?? "guide"];
  const Tree = home[language] ?? home.es;
  return () => <Tree slug={section.slug} />;
}
