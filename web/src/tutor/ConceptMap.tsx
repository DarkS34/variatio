import { Waypoints } from "lucide-react";
import { useId, useLayoutEffect, useRef, useState, type ReactNode, type RefObject } from "react";

import { ConceptChip } from "@/components/ui/concept-chip";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import {
  curve,
  isDrawable,
  pointsIn,
  rail,
  reviewOf,
  sideOf,
  type Box,
  type ConceptMapData,
  type ConceptMapLink,
} from "./conceptMap";

// How a chip is drawn, in the palette's grammar of position: what is behind the student is
// settled, what is ahead is dashed and dimmed, and the one thing to act on — the
// prerequisite a reply sent the student to review — is the attention colour.
const KNOWN = "border-settled/70";
const LATER = "border-dashed text-muted-foreground";

// Where the lines of one side meet before the concept, and how far a line stops short of
// what it touches.
const JOIN = 20;
const GAP = 6;
// The rail a narrow figure runs its other relations down, inside the room it keeps for it.
const RAIL_X = 8;

/** One line of the figure: its path, whether it is another relation than the order, and its arrows. */
interface Line {
  d: string;
  dotted?: boolean;
  start?: boolean;
  end?: boolean;
}

/**
 * THE MAP OF ONE CONCEPT UNDER A TUTOR'S REPLY: WHERE IT SITS IN THE SYLLABUS.
 *
 * The server decides WHEN a reply carries one — the first time the conversation stands on a
 * concept, and when a reply sends the student back to a prerequisite — so this only draws
 * what it is given, and draws nothing when an older record has no map to give.
 *
 * A graph read left to right in the order things are learnt: what the concept takes as
 * known, each joined by a line into one arrow to the concept, the concept in ink, and one
 * line out that opens into what comes later. Every other relation of the graph is a dotted
 * branch with the graph's own label on it, on the side its direction reads from: «Caso base
 * se engloba en» to the left, «se engloba en Abstracción» to the right.
 *
 * The chips are the app's own and the lines are drawn over them by measuring where the
 * layout put them, so every colour is a token and the theme follows. Narrower than the
 * container's `@xl`, the same figure stands up — what is known above, what comes later
 * below — and the other relations go under everything, reached by a rail down its left.
 */
export function ConceptMap({ map }: { map: ConceptMapData | null | undefined }) {
  const { t } = useT();
  const stage = useRef<HTMLDivElement>(null);
  const lines = useLines(stage, map);
  const tip = `tip-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  if (!isDrawable(map)) return null;

  const before = map.before ?? [];
  const after = map.after ?? [];
  const links = map.links ?? [];
  const hidden = map.hidden ?? {};
  const review = reviewOf(map);
  const inward = links.filter(pointsIn);
  const outward = links.filter((link) => !pointsIn(link));
  const moreLinks = hidden.links ? t("tutor.map.more", { n: hidden.links }) : null;
  const title = review
    ? t("tutor.map.review", { name: review, concept: map.concept })
    : t("tutor.map.title", { name: map.concept });

  return (
    <figure aria-label={title} className="well @container p-4 sm:px-5">
      {review ? (
        <figcaption className="mb-4 flex items-center gap-1.5 text-small text-muted-foreground">
          <Waypoints className="size-3.5 shrink-0" aria-hidden />
          <span>{title}</span>
        </figcaption>
      ) : null}

      <div ref={stage} className={cn("relative", links.length > 0 && "@max-xl:pl-7")}>
        <svg
          aria-hidden
          className="pointer-events-none absolute inset-0 size-full overflow-visible text-input"
        >
          <defs>
            <marker
              id={tip}
              viewBox="0 0 8 8"
              refX="7"
              refY="4"
              markerWidth="8"
              markerHeight="8"
              markerUnits="userSpaceOnUse"
              orient="auto-start-reverse"
            >
              <path
                d="M1.5 1L7 4L1.5 7"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </marker>
          </defs>
          {lines.map((line, index) => (
            <path
              key={index}
              d={line.d}
              fill="none"
              stroke="currentColor"
              strokeWidth={line.dotted ? 1.75 : 1.25}
              strokeDasharray={line.dotted ? "0 5" : undefined}
              strokeLinecap="round"
              markerStart={line.start ? `url(#${tip})` : undefined}
              markerEnd={line.end ? `url(#${tip})` : undefined}
            />
          ))}
        </svg>

        <div className="flex flex-col items-center gap-6 @xl:flex-row @xl:justify-center @xl:gap-16">
          {before.length > 0 || inward.length > 0 ? (
            <div className="flex flex-col items-center gap-5 @xl:items-end">
              {before.length > 0 ? (
                <Group
                  side="before"
                  caption={t("tutor.map.before")}
                  more={hidden.before ? t("tutor.map.more", { n: hidden.before }) : null}
                >
                  {before.map((name) => (
                    <Node key={name} side="before">
                      {name === review ? (
                        <ConceptChip tone="attention">{name}</ConceptChip>
                      ) : (
                        <ConceptChip className={KNOWN}>{name}</ConceptChip>
                      )}
                    </Node>
                  ))}
                </Group>
              ) : null}
              <Tied links={inward} wide more={outward.length === 0 ? moreLinks : null} />
            </div>
          ) : null}

          <span
            data-map="concept"
            className="rounded-full bg-ink px-4 py-1.5 text-center text-body font-semibold text-ink-foreground"
          >
            {map.concept}
          </span>

          {after.length > 0 || outward.length > 0 ? (
            <div className="flex flex-col items-center gap-5 @xl:items-start">
              {after.length > 0 ? (
                <Group
                  side="after"
                  caption={t("tutor.map.after")}
                  more={hidden.after ? t("tutor.map.more", { n: hidden.after }) : null}
                >
                  {after.map((name) => (
                    <Node key={name} side="after">
                      <ConceptChip className={LATER}>{name}</ConceptChip>
                    </Node>
                  ))}
                </Group>
              ) : null}
              <Tied links={outward} wide more={moreLinks} />
            </div>
          ) : null}

          <Tied links={[...inward, ...outward]} more={moreLinks} />
        </div>
      </div>
    </figure>
  );
}

/**
 * The lines of the figure, traced from where the layout put its chips: once drawn, again
 * whenever the figure changes size — a narrower panel, the switch to the stacked layout —
 * and once the type has loaded, since a chip is as wide as its name.
 */
function useLines(stage: RefObject<HTMLDivElement | null>, map: ConceptMapData | null | undefined): Line[] {
  const [lines, setLines] = useState<Line[]>([]);
  useLayoutEffect(() => {
    const node = stage.current;
    if (!node) return;
    let alive = true;
    const draw = () => {
      if (alive) setLines(trace(node));
    };
    draw();
    void document.fonts?.ready.then(draw);
    const observer = typeof ResizeObserver === "function" ? new ResizeObserver(draw) : null;
    observer?.observe(node);
    return () => {
      alive = false;
      observer?.disconnect();
    };
  }, [stage, map]);
  return lines;
}

/**
 * Read the boxes the layout drew and trace the lines between them.
 *
 * Beside the concept, each known chip curves into one point short of it and one arrow goes
 * in; one line leaves it and opens into the later chips, an arrow on each. Over and under
 * it, on the stacked figure, a side is one straight arrow from its group. Every other
 * relation is a dotted line of its own between the concept and its label, curving to the
 * side or running down the rail, its arrow pointing the way the graph does.
 */
function trace(stage: HTMLElement): Line[] {
  const origin = stage.getBoundingClientRect();
  const shown = (selector: string) =>
    [...stage.querySelectorAll<HTMLElement>(selector)].flatMap((element) => {
      const rect = element.getBoundingClientRect();
      if (rect.width === 0 && rect.height === 0) return [];
      const box: Box = {
        left: rect.left - origin.left,
        top: rect.top - origin.top,
        right: rect.right - origin.left,
        bottom: rect.bottom - origin.top,
      };
      return [{ element, box }];
    });
  const [concept] = shown('[data-map="concept"]');
  if (!concept) return [];
  const c = concept.box;
  const mid = (box: Box) => (box.top + box.bottom) / 2;
  const cx = (c.left + c.right) / 2;
  const cy = mid(c);
  const lines: Line[] = [];

  const known = shown('[data-map="before"]').map(({ box }) => box);
  if (known.length > 0) {
    if (known.every((box) => sideOf(box, c) === "left")) {
      const join = c.left - JOIN;
      for (const box of known) lines.push({ d: curve(box.right + GAP, mid(box), join, cy) });
      lines.push({ d: `M${join} ${cy}H${c.left - 3}`, end: true });
    } else {
      const [group] = shown('[data-group="before"]');
      if (group) lines.push({ d: `M${cx} ${group.box.bottom + GAP}V${c.top - 3}`, end: true });
    }
  }

  const later = shown('[data-map="after"]').map(({ box }) => box);
  if (later.length > 0) {
    if (later.every((box) => sideOf(box, c) === "right")) {
      const join = c.right + JOIN;
      lines.push({ d: `M${c.right + 3} ${cy}H${join}` });
      for (const box of later) lines.push({ d: curve(join, cy, box.left - GAP, mid(box)), end: true });
    } else {
      const [group] = shown('[data-group="after"]');
      if (group) lines.push({ d: `M${cx} ${c.bottom + 3}V${group.box.top - GAP}`, end: true });
    }
  }

  for (const { element, box } of shown('[data-map="tied"]')) {
    const side = sideOf(box, c);
    const d =
      side === "right"
        ? curve(c.right + 3, cy, box.left - GAP, mid(box))
        : side === "left"
          ? curve(c.left - 3, cy, box.right + GAP, mid(box))
          : rail(c.left - 3, cy, RAIL_X, box.left - GAP, mid(box));
    const direction = element.dataset.direction;
    lines.push({ d, dotted: true, start: direction === "in", end: direction === "out" });
  }
  return lines;
}

/** One side of the learning order: its caption, its chips, and the count of what the cap left out. */
function Group({
  side,
  caption,
  more,
  children,
}: {
  side: "before" | "after";
  caption: string;
  more: string | null;
  children: ReactNode;
}) {
  const end = side === "before";
  return (
    <div
      data-group={side}
      className={cn("flex flex-col items-center gap-2", end ? "@xl:items-end" : "@xl:items-start")}
    >
      <p className="text-micro font-condensed uppercase text-muted-foreground">{caption}</p>
      <div
        className={cn(
          "flex flex-wrap justify-center gap-2 @xl:flex-col",
          end ? "@xl:items-end" : "@xl:items-start",
        )}
      >
        {children}
      </div>
      {more ? <p className="text-small text-muted-foreground">{more}</p> : null}
    </div>
  );
}

/** A chip a line of the learning order reaches. */
function Node({ side, children }: { side: "before" | "after"; children: ReactNode }) {
  return (
    <span data-map={side} className="inline-flex">
      {children}
    </span>
  );
}

/**
 * The other relations, each a chip with the graph's label on the line that reaches it,
 * worded the way the graph points: «Caso base se engloba en» towards the concept, «se
 * engloba en Abstracción» away from it.
 *
 * Drawn in two places, one shown at a time: beside the concept on a wide figure (`wide`,
 * each side its own), and under everything on a narrow one. A hidden copy has no box, and
 * the tracing skips it.
 */
function Tied({
  links,
  wide = false,
  more,
}: {
  links: ConceptMapLink[];
  wide?: boolean;
  more: string | null;
}) {
  if (links.length === 0) return null;
  return (
    <div
      className={cn(
        "flex-col gap-2",
        wide ? "hidden @xl:flex" : "flex self-stretch @xl:hidden",
        wide && links.every(pointsIn) ? "items-end" : "items-start",
      )}
    >
      {links.map((link) => {
        const label = (
          <span className="whitespace-nowrap text-small text-muted-foreground">{link.relation}</span>
        );
        const chip = <ConceptChip>{link.name}</ConceptChip>;
        return (
          <span
            key={`${link.direction}-${link.relation}-${link.name}`}
            data-map="tied"
            data-direction={link.direction}
            className="flex items-center gap-2"
          >
            {pointsIn(link) ? chip : label}
            {pointsIn(link) ? label : chip}
          </span>
        );
      })}
      {more ? <p className="text-small text-muted-foreground">{more}</p> : null}
    </div>
  );
}
