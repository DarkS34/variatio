import { Search, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type RefObject } from "react";

import { Button } from "@/components/ui/button";
import { ConceptChip } from "@/components/ui/concept-chip";
import { domainColour } from "@/lib/format";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import { searchSyllabus, unitOf, type SyllabusUnit } from "./syllabus";

/**
 * THE CONCEPT A MESSAGE IS ABOUT, CHOSEN IN ONE CLICK.
 *
 * A panel that opens over the box to write in, and the third picker of concepts in the app
 * because the other two answer other questions: `ConceptPicker` puts a set of concepts on a
 * bank item and marks its primary, and `ConceptSelector` is a full-screen board for choosing
 * what an exercise practises. Here a student in the middle of a conversation picks ONE
 * concept, and the panel has to cost them less than typing its name.
 *
 * So it is laid out as the syllabus is remembered — «it was in Tema 5» — with the units
 * numbered down the left in their order and the unit's concepts on the right; a search box
 * finds a name across all of them. Choosing is a single click that closes the panel: there
 * is no set to build and nothing to confirm. From the keyboard it never needs the mouse:
 * typing searches, and the arrows follow the panel as it is drawn — the units are a column,
 * so up and down change unit; a unit's concepts run along lines, so left and right move
 * through them — Enter chooses and Escape leaves. With something typed there is no column of
 * units, left and right are the caret's again, and up and down move through the results.
 *
 * A unit carries the colour it has in the syllabus viewer (`domainColour`), so a unit is the
 * same colour wherever it is drawn.
 */
export function TopicPicker({
  units,
  chosen,
  current,
  startUnit,
  anchor,
  onPick,
  onClose,
}: {
  units: SyllabusUnit[];
  /** The concept already chosen for the message being written, if any. */
  chosen: string | null;
  /** The concepts the conversation stands on now, marked so the student sees where they are. */
  current: string[];
  /** The unit to open on; without one, the unit of what is chosen or current, else the first. */
  startUnit: number | null;
  /** The control that opened the panel: a press on it is its own toggle, not a press outside. */
  anchor: RefObject<HTMLElement | null>;
  onPick: (concept: string) => void;
  onClose: () => void;
}) {
  const { t, plural } = useT();
  const panel = useRef<HTMLDivElement>(null);
  const search = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [unit, setUnit] = useState(() => {
    const own = [chosen, ...current].map((name) => unitOf(units, name)).find((index) => index >= 0);
    return Math.min(Math.max(startUnit ?? own ?? 0, 0), Math.max(units.length - 1, 0));
  });
  // The option the arrows stand on; none until an arrow is pressed.
  const [active, setActive] = useState(-1);

  const searching = query.trim().length > 0;
  const found = useMemo(() => searchSyllabus(units, query), [units, query]);
  const shown = useMemo(
    () => (searching ? found.flatMap((match) => match.concepts) : (units[unit]?.concepts ?? [])),
    [searching, found, units, unit],
  );

  // A finger does not want a keyboard opened over the list it came to tap; a pointer does
  // want to type at once.
  useEffect(() => {
    const coarse = typeof window.matchMedia === "function" && window.matchMedia("(pointer: coarse)").matches;
    if (!coarse) search.current?.focus();
  }, []);

  useEffect(() => {
    const onDown = (event: PointerEvent) => {
      const target = event.target as Node;
      if (panel.current?.contains(target) || anchor.current?.contains(target)) return;
      onClose();
    };
    document.addEventListener("pointerdown", onDown);
    return () => document.removeEventListener("pointerdown", onDown);
  }, [anchor, onClose]);

  useEffect(() => {
    if (active < 0) return;
    panel.current?.querySelector(`[data-option="${active}"]`)?.scrollIntoView({ block: "nearest" });
  }, [active]);

  // On a narrow screen the units are one scrolling row, and the one in use has to be in it:
  // opened on the fifth unit, the row showed the first two.
  useEffect(() => {
    panel.current
      ?.querySelector('nav [aria-current="true"]')
      ?.scrollIntoView({ block: "nearest", inline: "nearest" });
  }, [unit, searching]);

  const toUnit = (next: number) => {
    setUnit(Math.min(Math.max(next, 0), units.length - 1));
    setActive(-1);
  };

  const onKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    } else if ((event.key === "ArrowDown" || event.key === "ArrowUp") && !searching) {
      event.preventDefault();
      toUnit(unit + (event.key === "ArrowDown" ? 1 : -1));
    } else if (
      searching
        ? event.key === "ArrowDown" || event.key === "ArrowUp"
        : event.key === "ArrowRight" || event.key === "ArrowLeft"
    ) {
      event.preventDefault();
      if (shown.length === 0) return;
      const step = event.key === "ArrowDown" || event.key === "ArrowRight" ? 1 : -1;
      setActive((at) => (at < 0 ? (step > 0 ? 0 : shown.length - 1) : (at + step + shown.length) % shown.length));
    } else if (event.key === "Enter" && event.target === search.current) {
      // With something typed, Enter takes the first result: the search is the fast road.
      const index = active >= 0 ? active : searching ? 0 : -1;
      if (index >= 0 && shown[index]) {
        event.preventDefault();
        onPick(shown[index]);
      }
    }
  };

  let option = -1;
  const options = (names: string[]) => (
    <ul className="flex flex-wrap gap-1.5">
      {names.map((name) => {
        option += 1;
        const index = option;
        const isChosen = name === chosen;
        const isCurrent = !isChosen && current.includes(name);
        return (
          <li key={name} className="max-w-full">
            <button
              type="button"
              data-option={index}
              aria-pressed={isChosen}
              title={isCurrent ? t("tutor.topic.current") : undefined}
              onClick={() => onPick(name)}
              className={cn(
                "max-w-full rounded-full text-left",
                index === active && "outline outline-2 outline-offset-2 outline-ring",
              )}
            >
              <ConceptChip
                tone={isChosen ? "primary" : "default"}
                colour={isCurrent ? "var(--foreground)" : undefined}
                className={cn("cursor-pointer", !isChosen && "hover:bg-accent")}
              >
                {name}
              </ConceptChip>
            </button>
          </li>
        );
      })}
    </ul>
  );

  return (
    <div
      ref={panel}
      role="dialog"
      aria-label={t("tutor.topic.picker")}
      onKeyDown={onKey}
      className="absolute inset-x-0 bottom-full z-20 mb-2 flex max-h-[min(26rem,62dvh)] flex-col overflow-hidden rounded-inner bg-popover text-popover-foreground shadow-overlay animate-fade-in"
    >
      <div className="flex items-center gap-2 border-b border-border px-3">
        <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden />
        <input
          ref={search}
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setActive(-1);
          }}
          aria-label={t("tutor.topic.search")}
          placeholder={t("tutor.topic.search")}
          // One frame, the panel's: the stylesheet's floor outline for a bare input would
          // draw a second one inside it.
          style={{ outline: "none" }}
          className="h-10 min-w-0 flex-1 bg-transparent text-body placeholder:text-muted-foreground"
        />
        <Button variant="ghost" size="icon-sm" aria-label={t("common.close")} onClick={onClose}>
          <X />
        </Button>
      </div>

      {searching ? (
        <div className="thin-scroll min-h-0 flex-1 space-y-3 overflow-y-auto p-3">
          {found.length === 0 ? (
            <p className="text-small text-muted-foreground">{t("tutor.topic.none")}</p>
          ) : (
            found.map((match) => (
              <section key={match.name} className="space-y-1.5">
                <UnitName number={match.number} total={units.length} name={match.name} />
                {options(match.concepts)}
              </section>
            ))
          )}
        </div>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col sm:grid sm:grid-cols-[minmax(0,15rem)_minmax(0,1fr)]">
          <nav
            aria-label={t("tutor.topic.units")}
            className="thin-scroll flex shrink-0 overflow-x-auto border-b border-border sm:flex-col sm:overflow-y-auto sm:overflow-x-hidden sm:border-b-0 sm:border-r"
          >
            {units.map((entry, index) => (
              <button
                key={entry.name}
                type="button"
                aria-current={index === unit ? "true" : undefined}
                onClick={() => toUnit(index)}
                className={cn(
                  "flex shrink-0 items-baseline gap-2 border-b-2 border-transparent px-3 py-2 text-left transition-colors hover:bg-accent sm:border-b-0 sm:border-l-2",
                  index === unit && "border-foreground bg-accent",
                )}
              >
                <span className="nums w-4 shrink-0 text-small text-muted-foreground">{index + 1}</span>
                <UnitDot index={index} total={units.length} />
                <span className="max-w-48 truncate sm:max-w-none sm:flex-1 sm:whitespace-normal">
                  {entry.name}
                </span>
                <span className="nums hidden text-small text-muted-foreground sm:inline">
                  {entry.concepts.length}
                </span>
              </button>
            ))}
          </nav>
          <div className="thin-scroll min-h-0 flex-1 space-y-2 overflow-y-auto p-3">
            {units[unit] ? (
              <>
                {/* Only where the units are a row of tabs that cuts their names: beside the
                    full list, the row in use already says all of this. */}
                <div className="flex flex-wrap items-baseline justify-between gap-x-3 sm:hidden">
                  <UnitName number={unit + 1} total={units.length} name={units[unit].name} />
                  <span className="text-small text-muted-foreground">
                    {plural("tutor.topic.count", units[unit].concepts.length, {
                      n: units[unit].concepts.length,
                    })}
                  </span>
                </div>
                {options(units[unit].concepts)}
              </>
            ) : null}
          </div>
        </div>
      )}

      <p className="hidden border-t border-border px-3 py-1.5 text-small text-muted-foreground sm:block">
        {t(searching ? "tutor.topic.keysSearch" : "tutor.topic.keys")}
      </p>
    </div>
  );
}

/** A unit's name with its place in the syllabus and its own colour, as the viewer draws it. */
function UnitName({ number, total, name }: { number: number; total: number; name: string }) {
  return (
    <p className="flex items-baseline gap-2 font-medium">
      <span className="nums text-muted-foreground">{number}</span>
      <UnitDot index={number - 1} total={total} />
      <span>{name}</span>
    </p>
  );
}

/** A unit's colour: the one it has in the syllabus viewer and wherever else it is drawn. */
export function UnitDot({ index, total }: { index: number; total: number }) {
  return (
    <span
      aria-hidden
      className="size-2 shrink-0 translate-y-[-1px] rounded-full"
      style={{ background: domainColour(index, total) }}
    />
  );
}
