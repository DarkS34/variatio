import katex from "katex";
import "katex/dist/katex.min.css";
import { useMemo } from "react";

import { cn } from "@/lib/utils";

/**
 * A TeX formula, typeset.
 *
 * Named `TeX` and never `Math`: the second shadows the global inside every module that
 * imports it, so a `Math.min` two hundred lines down fails to compile — or worse, does not.
 *
 * KaTeX and not a hand-rolled subset: what this material contains is `\rightarrow`,
 * `\bullet`, `\cdot`, `\text{}` and aligned arrays of production rules, so a translator for
 * "some greek and some arrows" would be wrong on exactly the exercises worth reading. It
 * rides in the lazy chunks of the two screens that render an item, `Markdown` being reached
 * from nowhere else.
 *
 * `throwOnError: false` is load-bearing and not defensive: what is typeset here is model
 * output, an unbalanced brace is normal, and KaTeX's fallback shows the offending source in
 * the error colour. The alternative loses the nine good formulas on the card with it.
 *
 * `trust: false` (the default) keeps the HTML KaTeX's own: it refuses the commands that
 * inject markup or navigate, so a `\href{javascript:…}` renders as text.
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
