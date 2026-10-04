import "./i18n";

import { ChevronRight, ClipboardCheck } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import { useStageReview } from "./queries";
import { StageReview } from "./StageReview";
import { questionCount } from "./types";

/** How long the questionnaire takes to unfold, and therefore when the page may scroll to it. */
const REVIEW_UNFOLD_MS = 300;

/**
 * The stage questionnaire as a stage screen carries it: the button at the foot of the
 * artifact and the form that unfolds under it.
 *
 * ONE component, because `StageGate` is core and loads it through `React.lazy` only for an
 * account the questionnaire is asked of (`useAsksStageReview`: the evaluation open to it and a
 * role that may correct the subject): for anybody else nothing of the questionnaire is drawn,
 * fetched or even downloaded.
 *
 * The button is at the FOOT and never on entering: "questions about what you have just
 * reviewed" over something nobody has looked at yet is a promise the screen cannot keep.
 *
 * This is where `--evaluation` is spent — the same token the bar's "Evaluar el sistema"
 * door carries. Filled while unanswered and quiet once answered, which is the only
 * difference that matters. `StageGate` does not mount it with the stage unbuilt, since there
 * would be nothing to judge, but DOES with the stage blocked: a built step whose predecessor
 * was reopened still has something to judge, and the questionnaire is what is being
 * measured.
 *
 * It unfolds directly under its button, as an accordion and at the button's own width. The
 * reading order of a stage is view → verdict → correction, top to bottom, so a panel
 * opening at the other end of the screen breaks it.
 *
 * The form is always mounted and merely clipped: unmounting it would throw away whatever
 * the person has typed into the box every time they close it. Button and panel are ONE
 * block, or the container's `space-y` opens a gap under the button while the panel is shut.
 */
export function StageReviewSlot({
  artifact,
  curated,
}: {
  artifact: string;
  /**
   * Whether this visit has written to the artifact: the evaluation's own contrast, whether
   * this person corrected before judging. A WRITE counts, not merely having opened the
   * controls, and it states what THIS visit did: correcting, leaving without answering and
   * coming back records a "no". The server only ever lets the mark climb. Told from above,
   * because the writes are the stage screen's.
   */
  curated: boolean;
}) {
  const { t, plural } = useT();
  // The questionnaire starts shut, and shuts again on another stage.
  const [open, setOpen] = useState(false);
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => setOpen(false), [artifact]);

  // The WRAPPER — button and panel — is what is scrolled to, under the sticky header
  // (`scroll-mt-20`): the panel alone is 0 px tall at the instant it is asked to open, so
  // scrolling to it scrolls nowhere.
  useEffect(() => {
    if (!open) return;
    // `scrollIntoView` does not honour the media query on its own, unlike a CSS transition.
    const still = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const scroll = () =>
      panel.current?.scrollIntoView({ behavior: still ? "auto" : "smooth", block: "start" });
    // AFTER the unfold and not at the click: the page is only as tall as its content, so a
    // scroll asked for before the panel has grown stops where the short page ends.
    if (still) {
      scroll();
      return;
    }
    const timer = window.setTimeout(scroll, REVIEW_UNFOLD_MS);
    return () => window.clearTimeout(timer);
  }, [open]);

  const review = useStageReview(artifact);
  const answered = review.data?.mine?.answered ?? false;
  // How many the form asks, from the form itself: a number written into the string promises
  // one thing and opens another as soon as an instrument changes.
  const count = review.data ? questionCount(review.data.instrument) : 0;

  return (
    <div ref={panel} className="scroll-mt-20">
      {review.data?.built ? (
        <button
          type="button"
          onClick={() => setOpen((was) => !was)}
          aria-expanded={open}
          className={cn(
            "group flex w-full items-center gap-3 border px-4 py-3.5 text-left transition-colors",
            answered
              ? "border-[color-mix(in_oklch,var(--evaluation)_35%,transparent)] bg-[color-mix(in_oklab,var(--evaluation)_7%,var(--card))] text-foreground hover:bg-[color-mix(in_oklab,var(--evaluation)_12%,var(--card))]"
              : "border-evaluation bg-evaluation text-evaluation-foreground hover:bg-[color-mix(in_oklab,var(--evaluation)_88%,var(--evaluation-foreground))]",
          )}
        >
          <ClipboardCheck aria-hidden className="size-5 shrink-0" />
          <span className="min-w-0 flex-1">
            <span className="block text-heading font-semibold">{t("stageReview.openTitle")}</span>
            <span
              className={cn("block text-small", answered ? "text-muted-foreground" : "opacity-85")}
            >
              {answered
                ? t("stageReview.openAnswered")
                : plural("stageReview.openPending", count)}
            </span>
          </span>
          <ChevronRight
            aria-hidden
            className={cn(
              "size-5 shrink-0 transition-transform duration-300",
              open && "rotate-90",
            )}
          />
        </button>
      ) : null}
      <div
        // `inert` and not only `aria-hidden`: clipped to zero height the panel is still in
        // the tab order, so tabbing off the button walked into a form nobody can see. React
        // 19 forwards it as the real attribute, which takes the subtree out of focus AND out
        // of the accessibility tree, and unlike `visibility: hidden` it does not fight the
        // closing transition.
        inert={!open}
        className={cn(
          "overflow-hidden transition-[max-height,opacity] duration-300 ease-out motion-reduce:transition-none",
          open ? "max-h-[400rem] opacity-100" : "max-h-0 opacity-0",
        )}
      >
        <div
          className={cn(
            "pt-4 transition-transform duration-300 ease-out motion-reduce:transition-none",
            open ? "translate-y-0" : "-translate-y-3",
          )}
        >
          <StageReview
            artifact={artifact}
            curated={curated}
            visible={open}
            onClose={() => setOpen(false)}
          />
        </div>
      </div>
    </div>
  );
}
