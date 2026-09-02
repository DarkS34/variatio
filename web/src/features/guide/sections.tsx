import {
  Activity,
  Compass,
  FileText,
  Files,
  Layers,
  Library,
  LifeBuoy,
  Network,
  Play,
  Scale,
  ShieldCheck,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import { lazy, type ComponentType, type ReactNode } from "react";

import { useT, type Key, type Language } from "@/lib/i18n";

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
}

/**
 * THE TREES ARE FETCHED, THE REGISTRY IS NOT.
 *
 * Each prose tree is ~46 kB of the guide's 102 kB chunk, and a reader needs one of them.
 * `GUIDE_SECTIONS` below stays static because the index, the search and the «Siguiente»
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
    const { BODIES } = await load();
    const Body: ComponentType<{ slug: string }> = ({ slug }) => {
      const Section = BODIES[slug];
      return Section ? <Section /> : null;
    };
    return { default: Body };
  });
}

const TREES: Record<Language, ComponentType<{ slug: string }>> = {
  es: tree(() => import("./es/sections")),
  en: tree(() => import("./en/sections")),
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
  // First of «Preparar», because it is genuinely the first thing a new workspace does and
  // the one step that decides how long all three builds feel. It is not a stage — it
  // produces no artifact and nobody approves it — which is why it is here and not on the
  // rail.
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
  { slug: "evaluate", labelKey: "guide.sec.evaluate", groupKey: "guide.group.use", icon: Scale },
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
  // The other two administrator-only sections, and both sit in «Día a día» rather than
  // «Fase de pruebas» because neither is something an evaluator ever does. This one first: it is the
  // panel as a whole, and «repartir» is one of its five tabs read in detail.
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
 * section would go on «working», landing every reader on «Empezar». `GuideLink` takes this
 * type, so the rename is a build error at every call site instead.
 */
export type GuideSlug = (typeof GUIDE_SECTIONS)[number]["slug"];

/**
 * The section's body in the reader's language, as a component that suspends while its
 * tree is on the way. `GuideScreen` puts the boundary around this and nothing else, so a
 * section change never blanks the nav beside it.
 */
export function useGuideBody(slug: string): () => ReactNode {
  const { language } = useT();
  const Tree = TREES[language] ?? TREES.es;
  return () => <Tree slug={slug} />;
}
