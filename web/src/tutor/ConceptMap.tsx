import { Waypoints } from "lucide-react";
import { useMemo, useSyncExternalStore } from "react";

import { Diagram, type NodeStyle } from "@/components/Diagram";
import { useT } from "@/lib/i18n";

import { conceptMapSource, isDrawable, narrowed, type ConceptMapData } from "./conceptMap";

/**
 * How a map's nodes are painted, in the palette's own grammar of position: what is behind
 * the student is settled, what is ahead is dashed and dimmed, and the one thing to act on —
 * the concept itself, or the prerequisite a reply sent the student to review — is the
 * attention colour: the coral FILL with its dark label for the concept, the coral as a line
 * for the prerequisite. A constant, as `Diagram` asks.
 */
const STYLES: Record<string, NodeStyle> = {
  focus: { fill: "--attention-fill", stroke: "--attention-fill", text: "--attention-fill-foreground", bold: true },
  anchor: { fill: "--card", stroke: "--foreground", text: "--foreground", bold: true },
  known: { fill: "--card", stroke: "--settled", text: "--foreground" },
  review: { fill: "--card", stroke: "--attention", text: "--foreground", bold: true },
  later: { fill: "--card", stroke: "--muted-foreground", text: "--muted-foreground", dashed: true },
  tied: { fill: "--card", stroke: "--border", text: "--foreground" },
  more: { fill: "--muted", stroke: "--muted", text: "--muted-foreground" },
};

// Below this width three columns of boxes shrink into text nobody can read, so the map
// stands up — what comes before above the concept, what comes later under it — and the
// relations that are not about order are written under it instead of drawn.
const NARROW = "(max-width: 640px)";

function subscribeToWidth(listener: () => void): () => void {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return () => {};
  const media = window.matchMedia(NARROW);
  media.addEventListener("change", listener);
  return () => media.removeEventListener("change", listener);
}

function isNarrow(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia(NARROW).matches
  );
}

/**
 * The map of one concept under a tutor's reply: where it sits in the syllabus.
 *
 * The server decides WHEN a reply carries one — the first time the conversation stands on a
 * concept, and when a reply sends the student back to a prerequisite — so this only draws
 * what it is given, and draws nothing when an older record has no map to give. The map
 * stays a drawing: its Mermaid is written here from the graph, so there is no source of
 * anybody's to show, and the diagram's switch to its code is off.
 */
export function ConceptMap({ map }: { map: ConceptMapData | null | undefined }) {
  const { t } = useT();
  const narrow = useSyncExternalStore(subscribeToWidth, isNarrow, () => false);

  const code = useMemo(
    () =>
      isDrawable(map)
        ? conceptMapSource(
            narrow ? narrowed(map) : map,
            {
              before: t("tutor.map.before"),
              after: t("tutor.map.after"),
              more: (n) => t("tutor.map.more", { n }),
            },
            narrow ? "TD" : "LR",
          )
        : null,
    [map, narrow, t],
  );
  if (!code || !isDrawable(map)) return null;
  // What the narrow drawing left out is written under it, so nothing is dropped.
  const written = narrow ? (map.links ?? []) : [];

  return (
    <figure className="space-y-1.5">
      <figcaption className="flex flex-wrap items-center gap-1.5 text-small text-muted-foreground">
        <Waypoints className="size-3.5" aria-hidden />
        <span>
          {map.review
            ? t("tutor.map.review", { name: map.review, concept: map.concept })
            : t("tutor.map.title", { name: map.concept })}
        </span>
      </figcaption>
      <Diagram code={code} classes={STYLES} sourceToggle={false} />
      {written.length > 0 ? (
        <p className="text-small text-muted-foreground">
          {written.map((link) => `${link.name} (${link.relation})`).join(" · ")}
          {map.hidden?.links ? ` · ${t("tutor.map.more", { n: map.hidden.links })}` : ""}
        </p>
      ) : null}
    </figure>
  );
}
