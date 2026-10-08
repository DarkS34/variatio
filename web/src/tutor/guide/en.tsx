import "../i18n";

import type { ReactNode } from "react";

import { Block, Paragraph, Rows, SectionHead } from "@/features/guide/blocks";
import { useT } from "@/lib/i18n";

/**
 * The guide's section on the Socratic tutor, in English.
 *
 * Here and not in `features/guide/en/`, because it is the tutor's: the guide's registry
 * (`features/guide/sections.tsx`) loads it only for an account the tutor is open to. Prose
 * per language like the rest of the guide, and `scripts/check-i18n.mjs` checks that both
 * languages answer for the section.
 */

function Tutor() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.use")} title={t("guide.sec.tutor")}>
        <p>
          One of the doors that open after the construction: a conversation with a Socratic tutor, which
          guides with questions instead of giving answers. It is on your bar because whoever
          administers the installation has opened it to your account, and it opens on the same
          conditions as "{t("nav.create")}". It is meant for students: a student of the subject
          uses it without being able to build or correct anything.
        </p>
        <p>
          The tutor <strong>gives no solutions</strong>: it asks you questions so that you reach
          them yourself, and tells you what the subject explains in its own words. To practise,
          the door is "{t("nav.create")}".
        </p>
      </SectionHead>

      <Block title="What sets it apart from any chat">
        <Paragraph>
          Every reply is written with a card the system prepares from the subject's artifacts.
          The student never sees it, but it decides what the tutor knows at that moment:
        </Paragraph>
        <Rows
          items={[
            {
              key: "focus",
              head: "The concept being discussed",
              body: "It comes from the syllabus. The first message that clearly names one sets it, and it only moves when another message is clearly about something else. An «I don't get it» does not move it, and neither does talking about something the syllabus places earlier. You can also choose it yourself on the «About» line of the box you write in: the tutor then deduces nothing and works on that concept.",
            },
            {
              key: "notes",
              head: "What the notes explain",
              body: "The passages the syllabus anchored to that concept and the pieces of the notes closest to the message. The tutor starts from them and tells you in its own words: it does not copy them, does not send you to read them and does not tell you which unit or section they are in. If you want to see the document, look for it on your own.",
            },
            {
              key: "before",
              head: "What you need to know first",
              body: "The concept's direct prerequisites. The tutor takes them as known: if you ask about a concept, it works on that concept and does not walk you through the earlier ones. Only if you say something earlier is missing does it tell you which concept to review.",
            },
            {
              key: "map",
              head: "The concept map",
              body: "A graph of the concept in the order it is learnt: on the left what it takes as known, in the middle the concept, on the right what comes later. Its other relations are dotted branches with the relation's name on them. The system draws it from the syllabus, never the model, so it cannot invent a relation. It does not come with every reply: it appears the first time the conversation reaches a concept, and when the tutor sends you back to review something earlier, with that concept marked in coral.",
            },
            {
              key: "after",
              head: "What comes later",
              body: "The concepts the syllabus places next. The tutor does not introduce them, and the system checks that it does not.",
            },
            {
              key: "bank",
              head: "The exercise you bring",
              body: "If you paste a statement from the bank, the tutor recognises it and knows which concepts it practises. If you get stuck, it can offer a simpler one on the same concept.",
            },
            {
              key: "criteria",
              head: "The subject's criteria",
              body: "The conventions and mistakes the notes point out, drafted by the system and corrected by a teacher.",
            },
          ]}
        />
      </Block>

      <Block title="What the system checks in every reply">
        <Paragraph>
          Before you read it, a reply goes through some checks: it has to ask at least one
          question and not too many, it cannot carry more than a few lines of code, it cannot
          draw a diagram of its own, it cannot copy a passage of the notes, it cannot send you to
          the notes or to a unit, it cannot introduce a later concept and it cannot suggest what
          the criteria rule out. If it fails, the model writes another one with the reason; if
          it fails again, you get a fallback question about the concept. That is why the reply
          appears whole and not word by word.
        </Paragraph>
        <Paragraph>
          Administrative questions (grades, dates, submissions) and questions outside the subject
          get a fixed answer that never reaches the model. A message the guardrail refuses does
          not reach the model either.
        </Paragraph>
      </Block>

      <Block title="Choosing what the message is about">
        <Paragraph>
          The box you write in has an "{t("tutor.topic.label")}" line at its top. It says which
          concept the tutor takes the conversation to be about. "{t("tutor.topic.choose")}"
          opens the syllabus: the numbered units on one side and the unit's concepts on the
          other, with a search box that finds a concept by its name or by its unit's. One click
          chooses the concept and closes the panel; the concept holds for the message you are
          writing.
        </Paragraph>
        <Paragraph>
          With a concept chosen and the box empty, the box offers the commonest question,
          "{t("tutor.composer.suggestion", { name: "…" })}". The Tab key writes it, and so does
          the "{t("tutor.composer.tab")}" button that appears beside it. You can then change it
          or send it with Enter.
        </Paragraph>
        <Paragraph>
          Choosing is optional: with nothing chosen, the tutor works the concept out from your
          message. The keyboard needs no mouse: type to search, the up and down arrows change
          unit, left and right move through the concepts, Enter chooses and Esc closes. With
          something typed in the search, up and down move through the results. In a
          new conversation, the list of units in the middle opens the same panel on that unit.
        </Paragraph>
      </Block>

      <Block title="Writing and reading">
        <Paragraph>
          Enter sends the message; Shift + Enter opens a new line. The conversation has a fixed
          height and scrolls inside its box. Once it is about something, the system gives it a
          short title, which is the one the list shows; until then it carries its first line.
        </Paragraph>
        <Paragraph>
          Every reply has two parts: the explanation, in plain text, and the question it ends
          with, last of all, larger and in bold, because that is what you are to answer. Beside
          it stands the tutor's mark, a question mark made of squares: its dot in coral on the
          question you have open, and grey on the ones you already answered. While the tutor
          writes, that same mark is drawn square by square.
        </Paragraph>
        <Paragraph>
          When what is being worked on is written in mathematical notation —a formula, a
          recurrence, a cost—, the tutor writes it as a formula and not in words. On a narrow
          screen, the concept map stands up: what comes before above, the concept in the
          middle, what comes later below and the other relations last.
        </Paragraph>
      </Block>

      <Block title="The queue">
        <Paragraph>
          Every reply is a job of the queue, like a generation. With the local engine alone, a
          build in progress leaves the conversation "queued" until it ends. You can stop a reply
          that is waiting; the message stays marked as unanswered and you can ask for the reply
          again. Each account has one reply on its way at a time. While the tutor works, a
          question mark is written square by square; while queued, the mark is hollow and
          still.
        </Paragraph>
      </Block>

      <Block title="The daily limit">
        <Paragraph>
          Whoever administers the installation can limit how many messages each account sends
          the tutor in a day. The limit adds up all your subjects. Every message that enters the
          queue counts, a reply you ask for again with "{t("tutor.retry")}" included.
        </Paragraph>
        <Paragraph>
          When the limit is reached, the message is not sent. Above the box to write in, a
          notice says when you can write again, in hours and minutes: "
          {t("tutor.limit.reached", { wait: "…" })}". The day is UTC's, so the limit reopens
          at the same moment for everybody. What you had written stays in the box.
        </Paragraph>
      </Block>

      <Block title="Who sees what">
        <Paragraph>
          A conversation belongs to whoever holds it: nobody else in the subject reads it. The
          one exception is whoever administers the installation, who can read them all from "
          {t("admin.tab.workspaces")}", without being able to change them.
        </Paragraph>
        <Paragraph>
          The criteria belong to the teachers: the "{t("tutor.tab.criteria")}" tab only appears
          with edit permission. The system generates them with "{t("tutor.criteria.build")}",
          and they are reviewed and corrected like any step of the construction. The review shows
          the sentences alone, each unit folded; each criterion's concepts and sources appear
          when correcting. The tutor's method is not written here: it holds in every subject.
        </Paragraph>
        <Paragraph>
          While correcting, a list shows the sections and the chosen one opens beside it. The
          three that concern the whole subject come first: "{t("tutor.criteria.general")}", "
          {t("tutor.criteria.terms")}" and "{t("tutor.criteria.admin.short")}". Then there is
          one section per unit. Each row of the list says how many criteria the section holds
          and how many changes in it are not saved. The bar at the foot saves the changes of
          every section at once.
        </Paragraph>
      </Block>

      <Block title={`From an exercise: "${t("tutor.fromExercise")}"`}>
        <Paragraph>
          In "{t("nav.mySubjects")}" and in the "{t("generate.tab.mine")}" tab of
          "{t("nav.create")}", every generated exercise offers to open a conversation about
          it; among a batch's results, each one as soon as it is saved. The button is in the
          tutor's blue, the same as its door in the bar. The
          statement arrives already written in the box and the tutor starts from the concepts
          that exercise practises.
        </Paragraph>
      </Block>
    </div>
  );
}

export const BODIES: Record<string, () => ReactNode> = {
  tutor: Tutor,
};
