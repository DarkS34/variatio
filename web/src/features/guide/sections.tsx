import {
  Activity,
  Compass,
  FileText,
  Layers,
  Library,
  LifeBuoy,
  Network,
  Play,
  Scale,
  Send,
  UserRound,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

import { useT, type Key, type Language } from "@/lib/i18n";
import { BODIES as EN } from "./en/sections";
import { BODIES as ES } from "./es/sections";

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

const TREES: Record<Language, Record<string, () => ReactNode>> = { es: ES, en: EN };

export const GUIDE_SECTIONS: GuideSection[] = [
  {
    slug: "empezar",
    labelKey: "guide.sec.empezar",
    groupKey: "guide.group.start",
    icon: Compass,
  },
  {
    slug: "workspace",
    labelKey: "guide.sec.workspace",
    groupKey: "guide.group.start",
    icon: Layers,
  },
  {
    slug: "perfil",
    labelKey: "guide.sec.perfil",
    groupKey: "guide.group.prepare",
    icon: FileText,
  },
  {
    slug: "grafo",
    labelKey: "guide.sec.grafo",
    groupKey: "guide.group.prepare",
    icon: Network,
  },
  {
    slug: "banco",
    labelKey: "guide.sec.banco",
    groupKey: "guide.group.prepare",
    icon: Library,
  },
  { slug: "generar", labelKey: "guide.sec.generar", groupKey: "guide.group.use", icon: Play },
  { slug: "evaluar", labelKey: "guide.sec.evaluar", groupKey: "guide.group.use", icon: Scale },
  {
    slug: "ejecucion",
    labelKey: "guide.sec.ejecucion",
    groupKey: "guide.group.daily",
    icon: Activity,
  },
  {
    slug: "cuenta",
    labelKey: "guide.sec.cuenta",
    groupKey: "guide.group.daily",
    icon: UserRound,
  },
  // Administrator-only, and it sits in «Día a día» rather than «Usarla» because it is not
  // something an evaluator ever does: it is the work that makes their queue exist.
  {
    slug: "repartir",
    labelKey: "guide.sec.repartir",
    groupKey: "guide.group.daily",
    icon: Send,
  },
  {
    slug: "problemas",
    labelKey: "guide.sec.problemas",
    groupKey: "guide.group.daily",
    icon: LifeBuoy,
  },
];

/**
 * The section's body in the reader's language.
 *
 * A tree that has not caught up with a new section falls back to Spanish rather than
 * rendering nothing: a missing translation is a section written in the wrong language,
 * which is readable, and an empty page is not.
 */
export function useGuideBody(slug: string): () => ReactNode {
  const { language } = useT();
  return TREES[language][slug] ?? ES[slug] ?? (() => null);
}
