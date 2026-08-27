import {
  ArrowDown,
  ArrowUp,
  Check,
  ChevronDown,
  ChevronRight,
  MoreHorizontal,
  Pencil,
  Plus,
  Trash2,
  TriangleAlert,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { useStageLocked } from "@/components/StageGate";
import { Switch } from "@/components/ui/misc";
import { domainColour } from "@/lib/format";
import type { KgConcept } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT, type Key } from "@/lib/i18n";

/**
 * The graph as the syllabus it is: one section per unit, one row per concept.
 *
 * The picture cannot answer the questions curation actually asks — which of these 131 do I
 * still have to judge, which have no description, how far has the course got — because a
 * force layout puts the answer wherever physics leaves it. A list can: every concept is on
 * one line, in the order the units are taught, with each decision in its own column.
 *
 * The columns are the four things that are decided here and nowhere else. `Currículo` is the
 * only one that is not stored on the concept: it is where the concept falls relative to what
 * the course has covered, which is the same calculation the generator performs when it
 * writes a prompt (assumed_known / target / forbidden).
 */

export type CurriculumPlace = "covered" | "frontier" | "ahead";

/** The grid, declared once: the header and every row read from the same string, so a column
 *  cannot drift from its own heading. */
//
// Below `md` it is FOUR columns and not seven, and the three that go are chosen rather
// than truncated: where a concept falls in the curriculum, whether it has a description
// and its degree are all things you read while comparing rows on a wide screen. What is
// left is the row's identity and the one control that acts on it — the taggability
// switch — because a column you cannot press is worth less on a phone than one you can.
// The cells themselves carry `hidden md:…`, so a hidden cell occupies no track and the
// four that remain land on the four the narrow template declares.
const COLUMNS =
  "grid grid-cols-[1.25rem_minmax(0,1fr)_2.5rem_1rem] items-center gap-x-2 px-2 " +
  "md:grid-cols-[1.5rem_minmax(0,1fr)_7rem_5.5rem_5.5rem_3rem_1.25rem] md:px-3";

// `hint` is what a row says on hover, `means` what the key says under the map. They are
// deliberately two fields and not one split in half: the row explains the state, the key
// explains the consequence, and deriving one from the other is how a legend ends up
// wording itself by accident.
const PLACE: Record<CurriculumPlace, { labelKey: Key; hintKey: Key; meansKey: Key }> = {
  covered: {
    labelKey: "place.covered",
    hintKey: "place.covered.hint",
    meansKey: "place.covered.means",
  },
  frontier: {
    labelKey: "place.frontier",
    hintKey: "place.frontier.hint",
    meansKey: "place.frontier.means",
  },
  ahead: {
    labelKey: "place.ahead",
    hintKey: "place.ahead.hint",
    meansKey: "place.ahead.means",
  },
};

function PlaceMark({ place }: { place: CurriculumPlace }) {
  if (place === "covered") return <Check className="size-3.5 shrink-0 text-settled" />;
  return (
    <span
      className={cn(
        "size-2.5 shrink-0 rounded-full",
        place === "frontier" ? "bg-attention" : "border-[1.5px] border-muted-foreground",
      )}
    />
  );
}

/** What the three marks mean, beside the list that uses them. Colour is never the only
 *  channel — each state also has its own shape — but neither says what it is FOR. */
export function FrontierKey() {
  const { t } = useT();
  return (
    <div className="space-y-1.5">
      {(["covered", "frontier", "ahead"] as const).map((place) => (
        <p key={place} className="flex items-start gap-2 text-small">
          <span className="mt-1 flex w-3.5 shrink-0 justify-center">
            <PlaceMark place={place} />
          </span>
          <span>
            <span
              className={cn(
                "font-medium",
                place === "covered" && "text-settled",
                place === "frontier" && "text-attention",
              )}
            >
              {t(PLACE[place].labelKey)}
            </span>
            <span className="text-muted-foreground"> — {t(PLACE[place].meansKey)}</span>
          </span>
        </p>
      ))}
    </div>
  );
}

function UnitMenu({
  unit,
  count,
  first,
  last,
  onRename,
  onMove,
  onDelete,
  onAddConcept,
}: {
  unit: string;
  count: number;
  first: boolean;
  last: boolean;
  onRename: () => void;
  onMove: (delta: number) => void;
  onDelete: () => void;
  onAddConcept: () => void;
}) {
  const { plural, t } = useT();
  const [open, setOpen] = useState(false);
  const holder = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!holder.current?.contains(event.target as Node)) setOpen(false);
    };
    const key = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", key);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", key);
    };
  }, [open]);

  const item =
    "flex w-full items-center gap-2 px-3 py-1.5 text-left text-body transition-colors hover:bg-accent disabled:pointer-events-none disabled:opacity-40 [&_svg]:size-3.5 [&_svg]:shrink-0 [&_svg]:text-muted-foreground";

  const run = (action: () => void) => () => {
    setOpen(false);
    action();
  };

  return (
    <div className="relative" ref={holder}>
      <button
        type="button"
        onClick={() => setOpen((was) => !was)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={t("outline.unitActions", { unit })}
        className={cn(
          "flex size-6 items-center justify-center text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
          open && "bg-accent text-foreground",
        )}
      >
        <MoreHorizontal className="size-4" />
      </button>

      {open ? (
        <div
          role="menu"
          className="absolute right-0 top-7 z-30 w-60 overflow-hidden border border-border bg-popover py-1 shadow-overlay"
        >
          <button type="button" role="menuitem" className={item} onClick={run(onAddConcept)}>
            <Plus />
            {t("outline.addConcept")}
          </button>
          <button type="button" role="menuitem" className={item} onClick={run(onRename)}>
            <Pencil />
            {t("outline.renameUnit")}
          </button>
          <button
            type="button"
            role="menuitem"
            className={item}
            disabled={first}
            onClick={run(() => onMove(-1))}
          >
            <ArrowUp />
            {t("outline.moveEarlier")}
          </button>
          <button
            type="button"
            role="menuitem"
            className={item}
            disabled={last}
            onClick={run(() => onMove(1))}
          >
            <ArrowDown />
            {t("outline.moveLater")}
          </button>
          <button
            type="button"
            role="menuitem"
            className={cn(item, "text-destructive")}
            onClick={run(onDelete)}
          >
            <Trash2 />
            {plural("outline.deleteUnit", count)}
          </button>
        </div>
      ) : null}
    </div>
  );
}

function ConceptRow({
  concept,
  colour,
  place,
  selected,
  onSelect,
  onTaggable,
}: {
  concept: KgConcept;
  colour: string;
  place: CurriculumPlace | null;
  selected: boolean;
  onSelect: () => void;
  onTaggable: (next: boolean) => void;
}) {
  const { t } = useT();
  const locked = useStageLocked();

  return (
    <div
      role="button"
      tabIndex={0}
      aria-selected={selected}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.target !== event.currentTarget) return;
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          onSelect();
        }
      }}
      className={cn(
        COLUMNS,
        "h-9 cursor-pointer border-t border-border/55 transition-colors hover:bg-accent",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-ring",
        selected && "bg-primary/[0.09]",
      )}
    >
      {/* The same code as the canvas: filled is a taggable target, hollow is structure. */}
      <span className="flex justify-center">
        <span
          className="block size-2 rounded-full"
          style={concept.taggable ? { background: colour } : { border: `1.5px solid ${colour}` }}
        />
      </span>

      <span
        className={cn("truncate text-body", !concept.taggable && "text-muted-foreground")}
        title={concept.name}
      >
        {concept.name}
      </span>

      {place ? (
        <span className="hidden items-center gap-1.5 md:flex" title={t(PLACE[place].hintKey)}>
          <PlaceMark place={place} />
          <span
            className={cn(
              "truncate text-small",
              place === "covered" && "text-settled",
              place === "frontier" && "font-medium text-attention",
              place === "ahead" && "text-muted-foreground",
            )}
          >
            {t(PLACE[place].labelKey)}
          </span>
        </span>
      ) : (
        <span className="hidden md:block" />
      )}

      <span className="hidden md:block">
        {concept.description ? (
          <Check className="size-3.5 text-settled" aria-label={t("outline.withDescription")} />
        ) : (
          <TriangleAlert className="size-3.5 text-attention" aria-label={t("outline.withoutDescription")} />
        )}
      </span>

      {/* The switch is the row's own control, so it must not also open the concept. */}
      <span
        onClick={(event) => event.stopPropagation()}
        onKeyDown={(event) => event.stopPropagation()}
      >
        <Switch
          checked={concept.taggable}
          disabled={locked}
          onCheckedChange={onTaggable}
          label={t("outline.taggableOf", { name: concept.name })}
        />
      </span>

      <span className="nums hidden text-right text-small text-muted-foreground md:block">
        {concept.degree}
      </span>

      <ChevronRight className="size-3.5 text-muted-foreground" />
    </div>
  );
}

export function ConceptOutline({
  concepts,
  units,
  groups,
  place,
  unitStats,
  hasCurriculum,
  selected,
  onSelect,
  onTaggable,
  onRenameUnit,
  onMoveUnit,
  onDeleteUnit,
  onAddConcept,
}: {
  concepts: KgConcept[];
  /** Unit names in the order of the syllabus. */
  units: string[];
  /** The canvas's own domain order, so a row's dot is the colour of its node. */
  groups: string[];
  place: (name: string) => CurriculumPlace | null;
  /** The unit as it stands in the graph, NOT as the filter left it. A search narrows what is
   *  drawn and changes nothing about what a unit contains, so coverage and — above all — the
   *  count in «eliminar la unidad y sus N» have to come from the whole thing. */
  unitStats: (unit: string) => { total: number; covered: number };
  hasCurriculum: boolean;
  selected: string | null;
  onSelect: (name: string | null) => void;
  onTaggable: (name: string, next: boolean) => void;
  onRenameUnit: (name: string) => void;
  onMoveUnit: (name: string, delta: number) => void;
  onDeleteUnit: (name: string, count: number) => void;
  onAddConcept: (unit: string) => void;
}) {
  const { plural, t } = useT();
  const locked = useStageLocked();
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());

  const byUnit = useMemo(() => {
    const map = new Map<string, KgConcept[]>();
    for (const unit of units) map.set(unit, []);
    for (const concept of concepts) {
      if (!map.has(concept.domain)) map.set(concept.domain, []);
      map.get(concept.domain)!.push(concept);
    }
    return map;
  }, [concepts, units]);

  // A unit the filter emptied is not drawn at all: a header over nothing reads as a unit
  // whose concepts were deleted.
  const shown = [...byUnit.entries()].filter(([, items]) => items.length > 0);

  if (shown.length === 0) {
    return (
      <p className="px-3 py-10 text-center text-small text-muted-foreground">
        {t("outline.noMatch")}
      </p>
    );
  }

  return (
    <div>
      <div className={cn(COLUMNS, "h-8 text-micro font-condensed uppercase text-muted-foreground")}>
        <span />
        <span>{t("outline.column.concept")}</span>
        <span className="hidden md:block">{hasCurriculum ? t("outline.column.curriculum") : ""}</span>
        <span className="hidden md:block">{t("outline.column.description")}</span>
        <span>{t("outline.column.taggable")}</span>
        <span className="hidden text-right md:block">{t("outline.column.degree")}</span>
        <span />
      </div>

      {shown.map(([unit, items]) => {
        const order = units.indexOf(unit);
        const colour = domainColour(Math.max(0, groups.indexOf(unit)), Math.max(1, groups.length));
        const open = !collapsed.has(unit);
        const undescribed = items.filter((concept) => !concept.description).length;
        const { total, covered } = unitStats(unit);
        const partial = items.length !== total;

        return (
          <div key={unit}>
            <div className="flex items-center gap-2.5 border-t border-border bg-muted/45 py-2 pl-2 pr-3">
              <span className="w-[3px] self-stretch" style={{ background: colour }} />
              <button
                type="button"
                onClick={() =>
                  setCollapsed((current) => {
                    const next = new Set(current);
                    if (next.has(unit)) next.delete(unit);
                    else next.add(unit);
                    return next;
                  })
                }
                aria-expanded={open}
                className="flex min-w-0 items-center gap-2.5 text-left transition-colors hover:text-muted-foreground"
              >
                {open ? (
                  <ChevronDown className="size-3.5 shrink-0 text-muted-foreground" />
                ) : (
                  <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
                )}
                <span className="truncate text-body font-semibold">{unit}</span>
                <span className="shrink-0 text-micro font-condensed uppercase text-muted-foreground">
                  {partial
                    ? t("outline.partialCount", { shown: items.length, total })
                    : plural("outline.conceptCount", total)}
                  {undescribed > 0 ? t("outline.undescribed", { n: undescribed }) : ""}
                </span>
              </button>

              <span className="flex-1" />

              {hasCurriculum ? (
                <span
                  className="flex shrink-0 items-center gap-2"
                  title={t("outline.coverageTitle", {
                    covered: plural("outline.conceptCount", covered),
                    total,
                  })}
                >
                  <span className="h-1 w-20 bg-muted">
                    <span
                      className="block h-full bg-settled"
                      style={{ width: `${Math.round((covered / Math.max(1, total)) * 100)}%` }}
                    />
                  </span>
                  <span className="nums text-micro font-condensed uppercase text-settled">
                    {t("outline.covered", { covered, total })}
                  </span>
                </span>
              ) : null}

              {locked ? null : (
                <UnitMenu
                  unit={unit}
                  count={total}
                  first={order <= 0}
                  last={order < 0 || order >= units.length - 1}
                  onRename={() => onRenameUnit(unit)}
                  onMove={(delta) => onMoveUnit(unit, delta)}
                  onDelete={() => onDeleteUnit(unit, total)}
                  onAddConcept={() => onAddConcept(unit)}
                />
              )}
            </div>

            {open
              ? items.map((concept) => (
                  <ConceptRow
                    key={concept.name}
                    concept={concept}
                    colour={colour}
                    place={place(concept.name)}
                    selected={selected === concept.name}
                    onSelect={() => onSelect(concept.name)}
                    onTaggable={(next) => onTaggable(concept.name, next)}
                  />
                ))
              : null}
          </div>
        );
      })}
    </div>
  );
}
