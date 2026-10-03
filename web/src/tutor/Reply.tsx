import { useMemo } from "react";

import { Markdown } from "@/components/Markdown";

import { splitReply } from "./reply";

/**
 * What the tutor wrote, in its two registers.
 *
 * The explanation is body text, to be read. The question the reply closes with is what the
 * student has to answer, so it is set a step larger and in the heading's weight, apart from
 * the explanation above it: the eye lands on what is asked. Where the one ends and the other
 * begins is read off the prose (`splitReply`), never asked of the model.
 *
 * Held to a measure: a line the width of the panel is one nobody finds the start of again.
 */
export function Reply({ text }: { text: string }) {
  const { body, questions } = useMemo(() => splitReply(text), [text]);
  return (
    <div className="max-w-[46rem] space-y-3">
      {body ? <Markdown>{body}</Markdown> : null}
      {questions ? <Markdown className="text-heading leading-snug">{questions}</Markdown> : null}
    </div>
  );
}
