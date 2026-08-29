import katex from "katex";
import "katex/dist/katex.min.css";
import { useMemo } from "react";

import { cn } from "@/lib/utils";

/**
 * A TeX formula, typeset.
 *
 * Named `TeX` and not `Math`: the second shadows the global inside every module that
 * imports it, and `Math.min` two hundred lines down then fails to compile — or, worse,
 * would not have.
 *
 * The generator writes TeX because the corpus does — an automata item comes back with
 * `$\Sigma = \{0, 1\}$` in its statement and a grammar arrives as a `\begin{array}` — and
 * until this existed the card showed the source, which is the one thing a formula must not
 * be. KaTeX and not a hand-rolled subset: what this material actually contains is
 * `\rightarrow`, `\bullet`, `\cdot`, `\text{}` and aligned arrays of production rules, and
 * a translator for «some greek and some arrows» would be visibly wrong on exactly the
 * exercises worth reading. It rides in the lazy chunks of the two screens that render an
 * item, because `Markdown` is reached from nowhere else.
 *
 * `throwOnError: false` is load-bearing rather than defensive. What is typeset here is
 * model output: a formula with an unbalanced brace is a normal Tuesday, and KaTeX's own
 * fallback shows the offending source in the error colour, which says «this came out
 * wrong» in the place where it came out wrong. The alternative — one bad formula taking
 * the whole card down — loses the other nine that were fine.
 *
 * The HTML is KaTeX's own, built from the TeX by KaTeX. `trust: false` (the default) is
 * what keeps it that way: it refuses the commands that inject markup or navigate, so a
 * `\href{javascript:…}` in a poisoned corpus renders as text like everything else.
 */
export function TeX({ tex, display = false }: { tex: string; display?: boolean }) {
  const html = useMemo(() => {
    try {
      return katex.renderToString(tex, {
        displayMode: display,
        throwOnError: false,
        errorColor: "var(--destructive)",
        strict: false,
        trust: false,
      });
    } catch {
      return null;
    }
  }, [tex, display]);

  // Everything KaTeX can fail at is already an error node; this is the case where it threw
  // anyway, and the source read as code is more use than an empty gap.
  if (html === null) {
    return (
      <code className="rounded bg-muted px-1 py-0.5 font-mono text-[0.9em] text-foreground">
        {tex}
      </code>
    );
  }

  // A derivation is wider than a card and must scroll inside itself: the page body never
  // scrolls sideways. Inline maths takes no such box — it is part of the sentence.
  return display ? (
    <div
      className="thin-scroll overflow-x-auto py-1"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  ) : (
    <span className={cn("inline-block max-w-full")} dangerouslySetInnerHTML={{ __html: html }} />
  );
}
