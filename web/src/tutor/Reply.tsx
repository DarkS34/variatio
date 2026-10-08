import { useMemo } from "react";

import { Markdown } from "@/components/Markdown";

import { ConceptMap } from "./ConceptMap";
import type { ConceptMapData } from "./conceptMap";
import { QuestionMark } from "./QuestionMark";
import { splitReply } from "./reply";

/**
 * What the tutor wrote, in its two registers, with the concept map between them.
 *
 * The explanation is body text, to be read. The question the reply closes with is what the
 * student has to answer, so it comes LAST — after the map, when the reply carries one, and
 * so right above the box to answer in — set a step larger and in the heading's weight, with
 * the tutor's mark beside it (`QuestionMark`): the coral dot on the question to answer now,
 * settled grey on the ones already answered. Where the explanation ends and the question
 * begins is read off the prose (`splitReply`), never asked of the model.
 *
 * Held to a measure: a line the width of the panel is one nobody finds the start of again.
 */
export function Reply({
  text,
  map,
  latest = false,
}: {
  text: string;
  map?: ConceptMapData | null;
  /** Whether this is the reply the student is answering now, the one whose question is open. */
  latest?: boolean;
}) {
  const { body, questions } = useMemo(() => splitReply(text), [text]);
  return (
    <div className="max-w-[46rem] space-y-4">
      {body ? <Markdown>{body}</Markdown> : null}
      <ConceptMap map={map} />
      {questions ? (
        <div className="flex items-start gap-3">
          <QuestionMark tone={latest ? "attention" : "settled"} size={5} className="mt-0.5" />
          <Markdown className="min-w-0 text-heading leading-snug">{questions}</Markdown>
        </div>
      ) : null}
    </div>
  );
}
