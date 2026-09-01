import {
  ArrowDown,
  ArrowUp,
  ChevronDown,
  ChevronRight,
  MoreHorizontal,
  Pencil,
  Plus,
  Trash2,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { useStageLocked } from "@/components/StageGate";
import { InfoHint } from "@/components/ui/hint";
import { Switch } from "@/components/ui/misc";
import { domainColour } from "@/lib/format";
import type { KgConcept } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

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
// THREE COLUMNS LEFT ON 2026-09-01, by explicit user request, and one arrived. «Currículo»
// went with the curriculum editor itself; «Descr.» reported whether a description exists,
// which is now written by the build and edited on the concept; and «Grado» is a number out
// of graph theory that decides nothing for a teacher. What replaces them is the one thing a
// person actually judges row by row — whether the concept works as a label — said in words
// and a tick rather than only by the shape of a dot.
//
// IT IS A CONTROL AGAIN SINCE 2026-09-01 (explicit user request), reversing the
// «this column reports» of 2026-08-27. What that decision weighed was 36 px of chrome on
// every one of 131 rows against a dot that already said the same thing; what it did not
// weigh is that the state it reports is the one a person sets ROW BY ROW while reading the
// syllabus down — the taggability review is a pass over the whole list — and the setting
// lived one click away, inside the concept. The switch is now the only place it is set.
// It is drawn at EVERY width, unlike the tick it replaces: a control hidden on a phone is
// a state that cannot be changed there at all, which is what the dialog's switch used to
// cover.
// The wide track is 11rem and was 9: «SIRVE DE ETIQUETA» measures 143.3 px at `micro` with
// its tracking, so with the (i) beside it the header wrapped to two lines inside a row
// 32 px tall. 143.3 + 4 gap + 14 icon + the 8 px this column keeps to ITS OWN RIGHT is
// 169.3, which is what sets 11rem rather than 10.5. The 32 px come out of the name column,
// which is `minmax(0,1fr)`.
const COLUMNS =
  "grid grid-cols-[1.25rem_minmax(0,1fr)_2.25rem_1rem] items-center gap-x-2 px-2 " +
  "md:grid-cols-[1.5rem_minmax(0,1fr)_11rem_1.25rem] md:px-3";

/**
 * WHERE A CONCEPT FALLS RELATIVE TO WHAT THE COURSE HAS COVERED — no longer drawn.
 *
 * The three places (covered / frontier / ahead) are still exactly what the generator
 * computes on every prompt, and `CurriculumPlace` survives as the name of that calculation
 * because the canvas's curriculum layout reads it. What went (2026-09-01, explicit user
 * request) is the COLUMN reporting it row by row and the key under the map explaining what
 * the three marks mean. It is derived from the taught-concepts list, and that list stopped
 * being edited here at the same time — a legend for a state nothing on the screen sets is a
 * paragraph explaining a colour that never appears.
 */

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
  selected,
  locked,
  onSelect,
  onSetTaggable,
}: {
  concept: KgConcept;
  colour: string;
  selected: boolean;
  locked: boolean;
  onSelect: () => void;
  onSetTaggable: (next: boolean) => void;
}) {
  const { t } = useT();

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
      {/* The same code as the canvas: filled is a taggable target, hollow is structure. It
          carries the name of the state as well as the shape now that it is the only place
          the row says it — shape alone is not a label. */}
      <span
        className="flex justify-center"
        title={concept.taggable ? t("kg.taggable") : t("canvas.notTaggable")}
      >
        <span
          className="block size-2 rounded-full"
          role="img"
          aria-label={concept.taggable ? t("kg.taggable") : t("canvas.notTaggable")}
          style={concept.taggable ? { background: colour } : { border: `1.5px solid ${colour}` }}
        />
      </span>

      <span
        className={cn("truncate text-body", !concept.taggable && "text-muted-foreground")}
        title={concept.name}
      >
        {concept.name}
      </span>

      {/* The switch, and `stopPropagation` around it: the whole row is a button that opens
          the concept, so without it flipping the state would also open what it is about.
          The mouse-down is stopped as well as the click — the row's own handler is on
          `onClick`, but a nested control that only stops the click still lets a drag out of
          the switch land as a selection. */}
      <span
        className="flex justify-start pr-2"
        onClick={(event) => event.stopPropagation()}
        onMouseDown={(event) => event.stopPropagation()}
        onKeyDown={(event) => event.stopPropagation()}
      >
        <Switch
          checked={concept.taggable}
          disabled={locked}
          label={t("kg.taggable")}
          onCheckedChange={(next) => onSetTaggable(next)}
        />
      </span>

      <ChevronRight className="size-3.5 text-muted-foreground" />
    </div>
  );
}

export function ConceptOutline({
  concepts,
  units,
  groups,
  unitStats,
  filtering,
  selected,
  onSelect,
  onRenameUnit,
  onMoveUnit,
  onDeleteUnit,
  onAddConcept,
  onSetTaggable,
}: {
  concepts: KgConcept[];
  /** Unit names in the order of the syllabus. */
  units: string[];
  /** The canvas's own domain order, so a row's dot is the colour of its node. */
  groups: string[];
  /** The unit as it stands in the graph, NOT as the filter left it. A search narrows what is
   *  drawn and changes nothing about what a unit contains, so the count in «eliminar la
   *  unidad y sus N» has to come from the whole thing. */
  unitStats: (unit: string) => { total: number };
  /** Whether `concepts` is a NARROWED list. It is what makes a search work against units
   *  that are shut by default: a query that draws six headers and no rows reads as «no hay
   *  nada», which is the opposite of what it found. */
  filtering: boolean;
  selected: string | null;
  onSelect: (name: string | null) => void;
  onRenameUnit: (name: string) => void;
  onMoveUnit: (name: string, delta: number) => void;
  onDeleteUnit: (name: string, count: number) => void;
  onAddConcept: (unit: string) => void;
  /** Mark a concept as serving — or not serving — as a label. It is the row's own switch
   *  since 2026-09-01: the concept card no longer carries one. */
  onSetTaggable: (name: string, next: boolean) => void;
}) {
  const { plural, t } = useT();
  const locked = useStageLocked();

  /**
   * UNITS ARE SHUT UNTIL SOMETHING OPENS THEM.
   *
   * A real syllabus is six to eight units of ten to thirty concepts, so open-by-default
   * meant the list arrived as a hundred and thirty rows and the units — which are the thing
   * you navigate by — were six headings lost inside it. Shut, the first screen IS the
   * syllabus: the units in the order they are taught, each with its count and its coverage.
   *
   * `overrides` holds only what a person has DECIDED, so it never fights the two states
   * that open a unit on their own — a search narrowing the list, and the unit holding the
   * concept that is selected. A click always wins over both, in either direction, which is
   * what keeps «lo cerré a propósito» from being undone by the next keystroke.
   */
  const [overrides, setOverrides] = useState<Map<string, boolean>>(new Map());
  const selectedUnit = useMemo(
    () => concepts.find((concept) => concept.name === selected)?.domain ?? null,
    [concepts, selected],
  );

  // Choosing a concept — on the map, most of the time — is NEWER than having shut its unit
  // a minute ago, so it wins over the override rather than losing to it. Without this,
  // clicking a node answered with an inspector on the right and a list on the left that
  // refused to show the row it was about.
  //
  // It writes `true` rather than DELETING the entry, and that is the whole difference
  // between opening a unit and lending it out: with the entry deleted the unit fell back
  // to its default the moment the concept was deselected, so closing the concept's dialog
  // shut the list under it and the person lost the place they were reading. Opening is a
  // decision like any other, whoever made it — a click on the row or a click on the map.
  useEffect(() => {
    if (!selectedUnit) return;
    setOverrides((current) => {
      if (current.get(selectedUnit) === true) return current;
      const next = new Map(current);
      next.set(selectedUnit, true);
      return next;
    });
  }, [selectedUnit]);

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
        <span className="flex items-center gap-1 pr-2">
          <span className="hidden md:inline">{t("outline.column.taggable")}</span>
          {/* The (i) moved here with the control it explains: it hung off the concept
              card's switch, and that switch is gone. On a narrow screen the column has no
              room for its own name and this is the only thing left to name it. */}
          <InfoHint label={t("kg.taggable.hintLabel")}>{t("kg.taggable.hint")}</InfoHint>
        </span>
        <span />
      </div>

      {shown.map(([unit, items]) => {
        const order = units.indexOf(unit);
        const colour = domainColour(Math.max(0, groups.indexOf(unit)), Math.max(1, groups.length));
        const open = overrides.get(unit) ?? (filtering || unit === selectedUnit);
        const undescribed = items.filter((concept) => !concept.description).length;
        const { total } = unitStats(unit);
        const partial = items.length !== total;

        return (
          <div key={unit}>
            <div className="flex items-center gap-2.5 border-t border-border bg-muted/45 py-2 pl-2 pr-3">
              <span className="w-[3px] self-stretch" style={{ background: colour }} />
              <button
                type="button"
                onClick={() =>
                  setOverrides((current) => {
                    const next = new Map(current);
                    next.set(unit, !open);
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
                    selected={selected === concept.name}
                    locked={locked}
                    onSelect={() => onSelect(concept.name)}
                    onSetTaggable={(next) => onSetTaggable(concept.name, next)}
                  />
                ))
              : null}
          </div>
        );
      })}
    </div>
  );
}
