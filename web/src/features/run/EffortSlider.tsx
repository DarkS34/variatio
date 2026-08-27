import { useRef, useState } from "react";

import { cn } from "@/lib/utils";
import { EFFORT_LABELS, type EffortLevel } from "./effort";
import { useT } from "@/lib/i18n";

/**
 * How much the model deliberates, as one rule you drag along.
 *
 * It replaced four segmented buttons, and the reason is not decoration: effort is an
 * ORDERED quantity, and four buttons of equal weight drew it as four unrelated options.
 * A track says «more to the right» before a single word is read, which is exactly what
 * the levels mean and what the warning above «Medio» is about.
 *
 * The handle is a playhead — a short rule crossing the track — and not the usual circle.
 * A circle would be the one round thing on a screen whose radius is zero, and a bar has
 * a second advantage here: it is four pixels wide, so every stop can sit at a plain
 * percentage instead of at a percentage corrected by half a handle. The ends are the only
 * exception, and only for the LABELS: «Bajo» is flush left and «Máximo» flush right,
 * because centring them on their own stop would hang half of each word outside the widget.
 *
 * The whole box is the grab area, labels included, so clicking the word «Alto» lands on
 * «Alto». Pointer capture is what keeps the drag alive once the cursor leaves the box,
 * which is most of them.
 */
export function EffortSlider({
  levels,
  value,
  onChange,
}: {
  levels: EffortLevel[];
  value: EffortLevel;
  onChange: (next: EffortLevel) => void;
}) {
  const { t } = useT();
  const track = useRef<HTMLDivElement>(null);
  const [dragging, setDragging] = useState(false);

  const last = Math.max(1, levels.length - 1);
  const index = Math.max(0, levels.indexOf(value));
  const at = (i: number) => `${(i / last) * 100}%`;

  const move = (to: number) => {
    const next = levels[Math.min(levels.length - 1, Math.max(0, to))];
    if (next && next !== value) onChange(next);
  };

  // Snap to the nearest stop rather than to the one just passed: dragging should land on
  // the level the handle is closest to, which is what the eye is aiming at.
  const pick = (clientX: number) => {
    const rect = track.current?.getBoundingClientRect();
    if (!rect || rect.width === 0) return;
    move(Math.round(((clientX - rect.left) / rect.width) * last));
  };

  return (
    <div
      role="slider"
      tabIndex={0}
      aria-label={t("effort.label")}
      aria-orientation="horizontal"
      aria-valuemin={0}
      aria-valuemax={levels.length - 1}
      aria-valuenow={index}
      aria-valuetext={t(EFFORT_LABELS[value])}
      onPointerDown={(event) => {
        setDragging(true);
        pick(event.clientX);
        // Last, and that is the point: `setPointerCapture` throws if the pointer is already
        // captured elsewhere, and taking it first would take the plain click down with it.
        // Losing the capture costs a drag that leaves the box; losing the click costs the
        // control.
        event.currentTarget.setPointerCapture(event.pointerId);
      }}
      onPointerMove={(event) => {
        if (dragging) pick(event.clientX);
      }}
      onPointerUp={(event) => {
        event.currentTarget.releasePointerCapture(event.pointerId);
        setDragging(false);
      }}
      onPointerCancel={() => setDragging(false)}
      onKeyDown={(event) => {
        const step =
          event.key === "ArrowLeft" || event.key === "ArrowDown"
            ? -1
            : event.key === "ArrowRight" || event.key === "ArrowUp"
              ? 1
              : 0;
        if (step !== 0) {
          event.preventDefault();
          move(index + step);
        } else if (event.key === "Home") {
          event.preventDefault();
          move(0);
        } else if (event.key === "End") {
          event.preventDefault();
          move(levels.length - 1);
        }
      }}
      className={cn(
        // `touch-none` so a drag on a phone moves the handle instead of scrolling the page,
        // and the 2px gutter is what the handle overhangs at either end.
        "w-full max-w-64 touch-none px-0.5 pt-1 select-none",
        dragging ? "cursor-grabbing" : "cursor-grab",
      )}
    >
      <div ref={track} className="relative h-4">
        <div className="absolute inset-x-0 top-1/2 h-0.5 -translate-y-1/2 bg-input" />
        <div
          className={cn(
            "absolute top-1/2 left-0 h-0.5 -translate-y-1/2 bg-primary",
            !dragging && "transition-[width]",
          )}
          style={{ width: at(index) }}
        />
        {levels.map((level, i) => (
          <span
            key={level}
            className="absolute top-1/2 h-2 w-px -translate-x-1/2 -translate-y-1/2 bg-input"
            style={{ left: at(i) }}
          />
        ))}
        <span
          className={cn(
            "absolute top-1/2 w-1 -translate-x-1/2 -translate-y-1/2 bg-primary outline-2 outline-background",
            dragging ? "h-5" : "h-4 transition-[left,height]",
          )}
          style={{ left: at(index) }}
        />
      </div>

      {/* The value is announced by `aria-valuetext`, so to a screen reader this row would be
          the same four words twice. */}
      <div aria-hidden className="relative mt-1 h-4">
        {levels.map((level, i) => (
          <span
            key={level}
            className={cn(
              // `font-condensed uppercase` is what micro is paired with everywhere it acts
              // as a label — the rail, the badges, the table headers, the field labels — and
              // it is also what keeps «MÁXIMO» narrow enough not to reach «ALTO».
              "absolute top-0 text-micro font-condensed whitespace-nowrap uppercase",
              i === index ? "text-foreground" : "text-muted-foreground",
            )}
            style={{
              left: i === 0 ? 0 : at(i),
              transform:
                i === 0
                  ? undefined
                  : i === levels.length - 1
                    ? "translateX(-100%)"
                    : "translateX(-50%)",
            }}
          >
            {t(EFFORT_LABELS[level])}
          </span>
        ))}
      </div>
    </div>
  );
}
