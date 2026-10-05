import "../i18n";

import type { ReactNode } from "react";

import { Alert } from "@/components/ui/misc";
import {
  Block,
  Detail,
  Facts,
  Paragraph,
  Rows,
  SectionHead,
  Steps,
} from "@/features/guide/blocks";
import { useT } from "@/lib/i18n";

import { ARM_META } from "../arms";

/**
 * The guide's section on the evaluation, and the evaluation's part of how a building step
 * closes, in English.
 *
 * Here and not in `features/guide/en/`, because it is the evaluation's: the guide's
 * registry (`features/guide/sections.tsx`) loads it only for an account the evaluation is
 * open to. Prose per language like the rest of the guide, and `scripts/check-i18n.mjs`
 * checks that both languages answer for the section.
 */

const ARM_ORDER = ["naive", "rag", "system"] as const;

function Evaluate() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.use")} title={t("guide.sec.evaluate")}>
        <p>
          The same commission solved by two different architectures and presented{" "}
          <strong>blind</strong>, so that you choose without knowing which is which. One of the
          two is always this system; the other is drawn for each session from the two
          alternatives — a commercial model, or a similarity search over your documents. It is
          the part of the system that exists to measure it, not to produce material.
        </p>
        <p>
          You ask for the comparison and you judge it: you pick the concept you want the
          exercise on, the two versions are prepared, and you read them when they are ready.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "What you are asked for",
            value: "Reading two proposals, one question per card, and one choice.",
          },
          {
            label: "What it produces",
            value: "A saved session with the two proposals and your judgement.",
          },
          {
            label: "What you need",
            value: "The four steps closed: the two versions are written from your subject.",
          },
        ]}
      />

      <Block title="The two tabs">
        <Rows
          items={[
            {
              key: "encargo",
              head: t("eval.tab.compose"),
              body: 'Where the screen opens. You pick the concept and the type of exercise you want: the same "Generate exercises" form, without two controls — how many exercises, and whether the model deliberates — because a comparison is always one per version. The model that writes the two local proposals is not chosen here: the administrator sets it in "Administration → Evaluations", and the commercial one uses its own.',
            },
            {
              key: "sesiones",
              head: t("eval.tab.history"),
              body: "Your history. You can reread any closed session, reveal included.",
            },
          ]}
        />
        <Paragraph>
          While a comparison is open the tabs disappear, and so does the technical detail: it
          would say which architecture each proposal comes from before you have read it. The
          button in the header takes you back to the list. Leaving the screen and coming back
          opens it on the form: a finished comparison is reread from "{t("eval.tab.history")}".
        </Paragraph>
      </Block>

      <Block title="How a comparison goes">
        <Steps
          items={[
            <>
              The two proposals appear, unlabelled and in an order that is yours alone. Above
              them, in one line, the commission: the type of exercise, the concepts, the level if
              one was pinned and, when one was drawn, the scenario both are set in. If your
              «Additional instructions» already said what the exercise is about, none is drawn:
              your words reach both proposals as they are. Either way it is the same for both,
              so it gives nothing away. Which of the two alternatives this session drew is not
              said either.
            </>,
            <>
              The two cards are boxes of the same height, short or long the proposal, and each
              one scrolls inside. The coral "{t("reveal.read")}" button in its header opens it in
              full, at reading size and with the question at the foot; ← and → move between
              them.
            </>,
            <>
              <strong>You answer one question per card</strong>: whether you would set it in
              class — or, if you are a student, whether it would be useful to practise with. One
              click, first impression, no dwelling on it.
            </>,
            <>
              <strong>You choose one</strong>. The choice bar stays pinned to the foot of the
              window; it does not activate until you have answered both, and you can
              always say that none of them convinces you.
            </>,
            <>
              Only then is it revealed which architecture wrote each one: a column per
              proposal, with what you answered about it, the model and the time, and a
              "{t("reveal.read")}" that opens it in full along with where it came from.
            </>,
            <>
              It also uncovers <strong>each proposal's concepts</strong>, read with the same
              tagger the bank is read with, and a line saying whether the exercise strayed
              into something that comes later in the syllabus. The rule is the same for
              both and it is the one the system carries in its prompt, except that only one
              of the two knows about it. With a curriculum, any mention of what the class
              has not covered counts; without one, only the proposal practising a concept
              that comes after what was asked for.
            </>,
            <>
              If you feel like it, you rate the system's one on four scales, with its exercise
              beside them. It is <strong>optional</strong>: the comparison was already recorded
              when you chose.
            </>,
            <>
              Below it, "{t("eval.orderAnother")}" closes the session and leaves you on the
              form, ready to ask for the next one. If somebody has left comparisons in your
              queue, that same button opens the one that comes next.
            </>,
          ]}
        />
      </Block>

      <Alert tone="settled" title="Everything measured comes before the reveal">
        <p>
          A score given after knowing what each thing is, is a score about a name and not about
          an exercise. That is why the per-card question and the choice come first, and the
          reveal is last: it is the reward for finishing, not a gate in front of more work.
        </p>
      </Alert>

      <Block title="If it is not your area, say so">
        <Paragraph>
          At the bottom right there is a discreet link:{" "}
          <strong>"I have no basis for judging this"</strong>. Evaluators come from different
          subjects and different years, so running into an exercise that is not yours is normal
          and is not a failing of yours.
        </Paragraph>
        <Paragraph>
          Skipping it is the right answer and it is recorded as such:{" "}
          <strong>it does not count as a preference</strong> and does not dirty any average.
          Answering out of politeness would, and there would be no way to tell afterwards.
        </Paragraph>
      </Block>

      <Alert tone="settled" title="You will not see the running score">
        <p>
          Showing you the result of what you are about to judge is an invitation to even it out.
          Your sessions are yours and you can reread them; the count belongs to whoever analyses
          the evaluation.
        </p>
      </Alert>

      <Detail title="The three architectures, of which each session pits two">
        {ARM_ORDER.map((arm) => (
          <div key={arm} className="flex gap-3">
            <span
              aria-hidden
              className="mt-1.5 size-3 shrink-0"
              style={{ background: ARM_META[arm].colour }}
            />
            <p className="flex-1">
              <span className="font-medium text-foreground">{t(ARM_META[arm].labelKey)}</span> —{" "}
              {t(ARM_META[arm].descriptionKey)}
            </p>
          </div>
        ))}
        <p>
          Each session pits this system against <strong>one</strong> of the other two, chosen by
          a coin the same seed flips that decides the order. That way the question answered is
          the one that matters — does the system write better exercises than this alternative?
          — and, over many sessions, each alternative meets the system as often as the other.
        </p>
        <p>
          Each architecture has its own fixed colour, always the same, in every session and every
          chart, so that two sessions months apart can be read together.
        </p>
        <p>
          The colour appears <strong>only after the reveal</strong>. While the comparison is
          blind, a coloured card would be a card carrying information.
        </p>
        <p>
          Exactly what each one receives is written out, row by row, under the "
          {t("eval.tab.compose")}" form: it is the "{t("fair.title")}" table, and it says who
          sees the concepts, who the descriptions, who pieces of your documents, who the
          bank's exercises as examples, who the prerequisites. {t("fair.footnote")}
        </p>
      </Detail>

      <Detail title="Why the order of the cards is different for each person">
        <p>
          If two evaluators judge the same two exercises, each of them sees them in an order of
          their own. Sharing the order would mean sharing the tendency to pick the first or the
          last one too, and then what looked like agreement about the exercises would partly be
          agreement about where they were placed.
        </p>
        <p>
          That order is drawn with a seed kept with the session, so months later it can be
          reconstructed exactly what you saw and in which position.
        </p>
      </Detail>

      <Detail title="What you do not choose">
        <p>
          <strong>How many exercises are generated</strong>: always one per proposal, two per
          session. It is what makes the session the unit of analysis.
        </p>
        <p>
          <strong>Which of the two alternatives the system is compared against</strong>: each
          session draws it, and it is not said until the reveal. Choosing it would leave out the
          alternative one least feels like reading, and the evaluation needs to measure both.
        </p>
        <p>
          <strong>Whether the model reasons before answering</strong>: each session draws it, not
          you. Choosing it would correlate it with your mood and with the time you have; drawn,
          it is a condition that can be measured separately afterwards. It applies equally to the
          two local proposals, so it never separates one from the other.
        </p>
      </Detail>
    </div>
  );
}

/**
 * The questionnaire at the foot of a building step, as the guide's "How this step is
 * closed" tells it: the common guide draws this only for an account the questionnaire is
 * asked of (`useAsksStageReview`), since nobody else has the questionnaire on screen.
 */
export function StageReviewGuide() {
  const { t } = useT();
  return (
    <>
      <Paragraph>
        At the foot of what is built there is "
        {t("stageReview.openTitle")}". It unfolds a short questionnaire beneath it: five
        statements, and for each you say how far you agree, from 1 ("strongly disagree") to 5
        ("strongly agree"). They are the same five ideas on all three steps. You can leave it
        half done and come back, because half an answer is a datum too, and once you have
        saved you can close it without losing anything. It is there even when the previous
        step has been reopened: what is judged is what is built. The verdict is optional, as
        correcting is.
      </Paragraph>
      <Detail title="What is kept of the verdict">
        <p>
          Your answers, with the <em>particular version</em> you judged. If you build the
          step again and judge it again, nothing is overwritten: they are two data, because
          "it came out badly" and "I redid it and it came out well" are two different things.
          Answering again about the same one does correct your earlier answer.
        </p>
        <p>
          Whether you <strong>corrected before judging</strong> is kept too. It is not
          surveillance: it is a variable of the evaluation, because the mark of somebody who has
          curated the result by hand is not the mark of somebody judging it as it came out,
          and without telling them apart the two are mixed into the same average.
        </p>
        <p>
          There are five statements on every step, all on the same agreement scale, and they
          follow the same order on all three: that everything there is yours, that nothing is
          missing, that the step does what it is for — the parts of each type, the order of
          the syllabus, the concept on each exercise — that you could use it as it is, and
          that all in all it came out well. They are worded so that agreeing is always the
          good news, so the number is the mark: 5 is best. The last two are identical on all
          three, and those are the ones that let one step be compared with another. At the
          end there is an optional box for whatever does not fit the scale.
        </p>
        <p>
          It is the only thing asked in return for using this, and it is what is being
          measured: without it there is no way to know whether the system prepares a subject
          well or only looks as if it does.
        </p>
      </Detail>
    </>
  );
}

export const BODIES: Record<string, () => ReactNode> = {
  evaluate: Evaluate,
};
