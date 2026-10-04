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
          conditions as "{t("nav.create")}". It is meant for students: a reader of the subject
          can use it even without being able to build or generate anything.
        </p>
        <p>
          The tutor <strong>gives no solutions</strong>: it asks you questions so that you reach
          them yourself, and shows you where to look in the notes. To practise, the door is "{t("nav.create")}".
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
              head: "Where the notes explain it",
              body: "The passages the syllabus anchored to that concept and the pieces of the notes closest to the message. The references under each reply come from here, never from what the model writes, and each one opens the notes at that section.",
            },
            {
              key: "before",
              head: "What you need to know first",
              body: "The concept's direct prerequisites. The tutor takes them as known: if you ask about a concept, it works on that concept and does not walk you through the earlier ones. Only if you say something earlier is missing does it tell you to review it, and its section appears under the reply.",
            },
            {
              key: "map",
              head: "The concept map",
              body: "A diagram of the concept with what it takes as known, what comes later and its other relations in the syllabus. The system draws it from the syllabus, never the model, so it cannot invent a relation. It does not come with every reply: it appears the first time the conversation reaches a concept, and when the tutor sends you back to review something earlier, with that concept marked.",
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
          draw a diagram of its own, it cannot copy a passage of the notes, it cannot introduce a later concept and it cannot suggest
          what the criteria rule out. If it fails, the model writes another one with the reason;
          if it fails again, you get a fallback question that points you to the notes. That is
          why the reply appears whole and not word by word.
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
          with, larger and in bold, because that is what you are to answer. The reply speaks
          of "the notes" without naming the unit or the section: the exact place is below it. Under each reply, "{t("tutor.references")}" lists the sections it
          comes from. Each one opens the notes at that section.
        </Paragraph>
        <Paragraph>
          The notes open in "{t("tutor.notes.view.original")}": the document as it is —the
          pages of the PDF, the slides, the Word document—, with all its pages one under
          another, opened at the page where the section starts. From there you scroll freely:
          if the section goes on to the next page, keep scrolling, and the line under the list
          says which page you are on. The arrows and the list jump to another section. In a
          Word document, or in one whose pages were rearranged by hand, the page opened is
          approximate: if the section is not there, keep scrolling.
          "{t("tutor.notes.view.text")}" shows the same section as text, which is what the
          tutor reads and what you can select and copy. The window is the same size in both
          views, and the view you choose holds while you stay in the conversation. A document
          that cannot be shown in its original form opens as text straight away.
        </Paragraph>
        <Paragraph>
          When what is being worked on is written in mathematical notation —a formula, a
          recurrence, a cost—, the tutor writes it as a formula and not in words. On a narrow
          screen, the concept map draws only what comes before and after, and writes the other
          relations under it.
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
