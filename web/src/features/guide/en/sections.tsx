import { Check, Play, Scale, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Alert, PhaseBar, Skeleton } from "@/components/ui/misc";
import { StatusMark } from "@/components/ui/status";
import { STATUS, type StatusKey } from "@/lib/status";
import { ARM_META } from "@/study/arms";
import {
  USES,
  STEPS,
  nextStepOf,
  stepNumber,
  stepNumberOf,
} from "@/lib/steps";
import { useT, type Translate } from "@/lib/i18n";
import { useBuildPhases } from "@/state/queries";
import { Block, Detail, Facts, Paragraph, Rows, SectionHead, Steps } from "../blocks";

const STATE_ORDER: StatusKey[] = ["approved", "draft", "stale", "building", "missing", "blocked"];

const STATE_HINTS: Record<StatusKey, string> = {
  approved:
    "Closed and taken as good. It is closed by moving on to the next step; correcting it afterwards opens it again with the first change you save.",
  draft: "Built and not closed yet. It can be looked at and corrected; what comes after it is still waiting.",
  stale:
    "Something it depends on changed after it was closed. It has to be looked over and closed again by carrying on.",
  building:
    "The screen says which of three things is happening: it is being built for the first time and there is nothing to replace; it is being worked over what is already there, which stays saved and merely stops being shown; or the job is still queued and has not started, and then there is no bar.",
  missing: "It does not exist yet. The screen shows the header and a single button, large and in the middle: start building.",
  blocked:
    'Not "it is not done", but "it is not your turn yet": something it depends on is not closed.',
};

const ARM_ORDER = ["naive", "rag", "system"] as const;

/**
 * The graph builder's real plan, read from the API the way the panel reads it.
 *
 * It used to be copied out by hand in this file and it fell behind: it drew conversion at
 * 10 % when conversion weighs a third, and it did not draw the context phase at all. The
 * guide reads the app's own sources instead of restating them, so there is no hand-written
 * fallback here either: with no plan, a skeleton.
 */
function BuildPlanBar() {
  const phases = useBuildPhases("knowledge_graph");
  if (!phases.length) return <Skeleton className="h-1.5 w-full" />;
  return <PhaseBar phases={phases} percent={58} activeKey="clean" />;
}

/**
 * One of the two doors of the testing phase, drawn as the bar draws it: an icon and no
 * number, because the two have no order between them.
 */
function Pill({
  icon: Icon,
  label,
  tone,
}: {
  icon: LucideIcon;
  label: string;
  tone?: "study";
}) {
  return (
    <span
      className={
        tone === "study"
          ? "flex items-center gap-1.5 rounded-md px-2.5 py-1.5 text-small font-medium text-study ring-1 ring-inset ring-[color-mix(in_oklch,var(--study)_30%,transparent)] bg-[color-mix(in_oklch,var(--study)_9%,transparent)]"
          : "flex items-center gap-1.5 rounded-md border border-border px-2.5 py-1.5 text-small font-medium"
      }
    >
      <Icon className="size-4" />
      {label}
    </span>
  );
}

function Start() {
  const tr = useT();
  const { t } = tr;
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.start")} title={t("guide.sec.start")}>
        <p>
          <strong>Variatio</strong> generates <strong>learning exercises</strong> — exercises,
          problems, assessment tasks — anchored to a course's syllabus. It does not write about a
          concept in the abstract: it starts from the four steps you describe your subject with, and
          produces exercises that respect what the student has already seen and what they have
          not.
        </p>
      </SectionHead>

      <Block title="The route, at a glance">
        {/* It is the bar above, drawn here: the steps come from `STEPS` and the two doors
            from `USES`, so this figure cannot promise an order the navigation does not
            have. */}
        <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-4 sm:p-6">
          <div className="space-y-1.5">
            <p className="font-condensed text-micro uppercase text-muted-foreground">
              {t("nav.phase.build")}
            </p>
            <div className="flex flex-wrap items-center gap-3">
              {STEPS.map((step, index) => (
                <div key={step.path} className="flex items-center gap-2">
                  <span className="nums flex h-6 min-w-6 shrink-0 items-center justify-center bg-primary px-1 font-condensed text-small font-semibold text-primary-foreground">
                    {stepNumber(index)}
                  </span>
                  <span className="text-body font-medium">{t(step.labelKey)}</span>
                </div>
              ))}
            </div>
          </div>
          <span aria-hidden className="mx-1 h-6 w-px bg-border" />
          <div className="space-y-1.5">
            <p className="font-condensed text-micro uppercase text-muted-foreground">
              {t("nav.phase.test")}
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {USES.map((door) => (
                <Pill
                  key={door.key}
                  icon={door.key === "generate" ? Play : Scale}
                  label={t(door.labelKey)}
                  tone={door.study ? "study" : undefined}
                />
              ))}
            </div>
          </div>
        </div>
        <Paragraph>
          It is exactly the bar above, and it is two named phases. The{" "}
          <strong>{t("nav.phase.build").toLowerCase()}</strong> is four steps numbered{" "}
          <strong>{stepNumber(0)}</strong> to <strong>{stepNumber(3)}</strong> because they are
          one single job, <em>preparing the subject</em>, and they are done in that order: each
          needs the one before it closed. Each carries a word underneath saying where you are:{" "}
          <em>{t("nav.state.done").toLowerCase()}</em>,{" "}
          <em>{t("nav.state.now").toLowerCase()}</em> or{" "}
          <em>{t("nav.state.later").toLowerCase()}</em>.
        </Paragraph>
        <Paragraph>
          The <strong>{t("nav.phase.test").toLowerCase()}</strong> is two things you can do with
          the subject once it is built, and that is why they carry no number: neither comes
          before the other and neither needs the other. Both light up at once, when the construction
          is closed; until then they are half off, they say "{t("nav.state.later").toLowerCase()}"
          and they answer no click.
          "{t("nav.create")}" is what the construction exists for. "{t("nav.compare")}" stands
          apart in its own colour: it produces no material for your subject, it is there to
          measure the system.
        </Paragraph>
      </Block>

      <Rows
        items={[
          {
            key: "perfil",
            head: `${stepNumberOf("exemplars_profile")} · ${t("artifact.profile")}`,
            body: "What shapes your exercises come in: which parts each type carries, what its difficulty level is, and how it is written.",
          },
          {
            key: "grafo",
            head: `${stepNumberOf("knowledge_graph")} · ${t("artifact.graph")}`,
            body: "The subject's syllabus: its concepts, grouped into units and joined by what has to be known before what.",
          },
          {
            key: "banco",
            head: `${stepNumberOf("exemplars_bank")} · ${t("artifact.bank")}`,
            body: "Your own exercises, collected one by one out of the documents, each with the syllabus concepts it practises.",
          },
        ]}
      />

      <Alert tone="info" title="Exercise types come before the syllabus">
        <p>
          A syllabus can be built with nothing else, but the review of which concepts work as a
          label needs the <em>exercise types already closed</em>: it is judged against the shapes
          of exercise you set. That is why Step {stepNumberOf("exemplars_profile")} comes before
          Step {stepNumberOf("knowledge_graph")}, and not the other way round.
        </p>
      </Alert>

      <Block title="How you get started">
        <Steps
          items={[
            <>
              Get yourself into a <strong>subject</strong>. If you have none yet, you are
              offered to create yours as soon as you come in; if you have several, you switch in
              the selector at the top left. Everything else lives inside one.
            </>,
            <>
              <strong>Step {stepNumber(0)}</strong> — in "{t("nav.step.raw")}" upload the
              subject's notes and the exercises you already have. A couple of topics is enough:
              every document is read whole, so the more you upload the longer it takes.
            </>,
            <>
              On that same screen, "{t("transcribe.startAll")}" gets the reading of the documents
              out of the way. It is not required — skip it and every build reads its own along
              the way — but it is the mechanical work that opens the three steps after it. It is
              also where you can read a page that came out badly and correct it by hand.
            </>,
            <>
              <strong>Step {stepNumber(1)}</strong> — build the{" "}
              <strong>{t("nav.step.profile").toLowerCase()}</strong>, look at them, correct
              whatever does not fit and carry on.
            </>,
            <>
              <strong>Step {stepNumber(2)}</strong> — launch <strong>the syllabus</strong>. It is
              the most expensive job on the route: you can close the tab, the server carries on.
              When it finishes it chains on its own the description of every concept and the review
              of which ones work as a label.
            </>,
            <>
              <strong>Step {stepNumber(3)}</strong> — collect your exercises and go over the{" "}
              <strong>{t("nav.step.bank").toLowerCase()}</strong>: whether the concept each one has
              been given is the one it really practises.
            </>,
            <>
              With the four closed, "{t("nav.create")}" and "{t("nav.compare")}" open up.
            </>,
          ]}
        />
      </Block>

      <Block title="Every screen brings you to its own page here">
        <Paragraph>
          Under the title of the important screens there is a "{t("guide.linkTo", {
            section: t("guide.sec.graph"),
          })}" link that opens exactly the section explaining them. No need to remember what it
          is called: you read it from where you were, and the back button brings you back.
        </Paragraph>
      </Block>

      <Detail title={`What does it mean to "close" a step?`}>
        <p>
          There is no button called "approve". A step is closed{" "}
          <strong>by moving on to the next one</strong>: the "
          {t("stage.continue", { n: stepNumber(2) })}" button at the foot of the screen first
          saves whatever you have unsaved and takes what is there as good. If that write is
          refused, nothing is closed and nothing moves on.
        </p>
        <p>
          Closing a step is what unlocks the next one, and closing the three that build
          something is what opens "{t("nav.create")}". What is taken as good is the file{" "}
          <em>as it stands</em>, so a closed step opens read-only like any other. Correcting
          it needs no separate button: "{t("stage.curate.start")}" unlocks it just the same,
          and the first change you save opens it again — it will have to be closed once more
          by carrying on.
        </p>
        <p>
          What is <em>not</em> part of that file — a concept's description — can still be
          corrected with the step closed, because it lives apart and expires nothing.
        </p>
      </Detail>
    </div>
  );
}

function Workspace() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.start")} title={t("guide.sec.workspace")}>
        <p>
          A <strong>subject</strong> is prepared whole and on its own: its documents, the four
          steps of the route and everything generated from it. Nothing crosses from one to
          another. If one subject is taught with two very different exercise formats, those are
          two as well.
        </p>
      </SectionHead>

      <Facts
        items={[
          { label: "Where you switch", value: "The selector at the top left, next to the mark." },
          { label: "Who can create one", value: "Any account, and it becomes its owner." },
          {
            label: "If you have none",
            value: "You are offered to create it as soon as you come in. There is no default one.",
          },
          {
            label: "What travels with you",
            value: "Nothing. Each subject has its own, cache included.",
          },
          {
            label: "What is decided on creation",
            value: "The prompt language. It cannot be changed later.",
          },
        ]}
      />

      <Block title="Coming in with none is normal">
        <Paragraph>
          There is no initial subject for whoever has no other: a freshly created account, or
          one that has not been given access to anything yet, comes in and finds the offer to
          create its own. Its name is enough. Both ways out are equally valid: create it
          yourself and be its owner, or wait for whoever administers to give you access to one
          that already exists.
        </Paragraph>
        <Paragraph>
          Meanwhile the application is not blocked: this guide, "{t("account.title")}" and — if
          you administer the installation — "{t("admin.title")}" work with no subject at all.
          What waits is everything that reads an instance: the four steps, "{t("nav.create")}"
          and "{t("nav.compare")}".
        </Paragraph>
      </Block>

      <Block title="The prompt language is chosen when the subject is created">
        <Paragraph>
          Creating a subject is where you choose which language the model is spoken to in
          throughout the building of that instance. <strong>It cannot be changed afterwards</strong>
          , and that is not an arbitrary restriction: the relation labels are written inside the
          graph itself and the loader indexes by them, so the language is baked into the
          artifacts from the first build onwards. The creation form says so on the spot.
        </Paragraph>
        <Paragraph>
          It does not have to match the language you read the application in. Preparing an
          instance whose prompts are English while working in Spanish is a case the split was
          made for, and it is why these are two separate settings.
        </Paragraph>
      </Block>

      <Block title="One tab, one subject">
        <Paragraph>
          The active subject is kept on your account and survives signing out; the one you are{" "}
          <em>looking at</em> is kept by the tab. You can have two subjects open in two tabs of
          the same browser without them treading on each other. Switching subject empties the
          screen of what you were watching: the jobs and the progress belong to the instance
          you are leaving.
        </Paragraph>
      </Block>

      <Block title="The subject's context">
        <Paragraph>
          It is the prose saying what this instance is about — subject, level, language of
          instruction, conventions — and it goes into <em>every</em> call to the model. It is not
          written by hand: the syllabus build and the exercise-types build synthesise it, each
          with what it knows about the subject. It is read under "{t("account.title")} →{" "}
          {t("tabs.workspaces")}", below each one, with the three loose facts that sit
          beside the paragraph — {t("context.fact.subject").toLowerCase()},{" "}
          {t("context.fact.level").toLowerCase()} and{" "}
          {t("context.fact.language").toLowerCase()} — which are read separately and say the same
          thing it does.
        </Paragraph>
        <Alert tone="info" title={`"${t("context.draft")}" against "${t("context.curated")}"`}>
          <p>
            The badge says where the text you are reading comes from: "{t("context.curated")}" if
            somebody once wrote it, "{t("context.draft")}" if it is the last build's synthesis.
            Every build writes a fresh draft without touching what is already there, so what was
            written by hand is never overwritten on its own.
          </p>
        </Alert>
      </Block>

      <Block title="What the class has already covered">
        <Paragraph>
          When asking for an exercise you can say how far the class has got. That is what bounds
          the scaffolding: an exercise may lean on a concept already taught; it may not depend on
          one the class has not seen yet. It is chosen <em>in the commission itself</em>, in the
          same question where you choose what to practise and directly above it, and holds for
          that batch — it is not stored on the subject.
        </Paragraph>
        <Alert tone="info" title="Marking nothing does not mean nothing covered">
          <p>
            It means no restriction. Reading it literally would forbid the whole syllabus, which
            is exactly the state a new instance starts in.
          </p>
        </Alert>
      </Block>

    </div>
  );
}

function Raw() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.prepare")} title={t("guide.sec.raw")}>
        <p>
          The documents everything else comes out of, and the first step of the route —{" "}
          <strong>"{t("nav.step.raw")}"</strong> on the bar at the top, at{" "}
          <code className="font-mono text-small">/raw</code>. It is the only place where you
          have to go looking for files on your own machine: the other three steps work on
          whatever you leave here.
        </p>
        <p>
          <strong>A couple of topics is enough.</strong> Every document is read whole, so the
          more you upload the longer it takes, and seeing whether this is any use for your
          subject does not need the whole course.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "What you do here",
            value: "Upload your documents, and optionally get their reading out of the way and correct by hand whatever comes out wrong.",
          },
          {
            label: "What reading them costs",
            value: "One call to the model per page, in both origins alike.",
          },
          {
            label: "When it is done",
            value: "As soon as both origins hold documents. Reading them is not a requirement.",
          },
        ]}
      />

      <Block title="The two origins">
        <Rows
          items={[
            {
              key: "corpus",
              head: t("raw.slot.corpus"),
              body: t("raw.slot.corpus.purpose"),
            },
            {
              key: "exemplars",
              head: t("raw.slot.exemplars"),
              body: t("raw.slot.exemplars.purpose"),
            },
          ]}
        />
        <Paragraph>
          Under each card's title goes that same sentence, saying what to drop there and what it
          is used for. An empty origin does not draw an empty list: the whole card becomes the
          area to drop files into, which is the only thing worth doing there.
        </Paragraph>
        <Paragraph>
          Once there are documents, each one is <strong>one row</strong>: its name, how its
          reading is going, and the two operations on it — open it to correct its pages, or take
          it out of the origin.
        </Paragraph>
      </Block>

      <Alert tone="info" title="Reading them now brings work forward; it is never a requirement">
        <p>
          Turning the documents into text is the first thing <em>every</em> build does, and it is
          mechanical work: doing it here once takes it out of the start of the three steps after
          it. Build without having read them and the build does it on its own, with nothing
          stopping you — <strong>nothing is ever refused for want of a reading</strong>.
        </p>
        <p>
          Which is why, while documents are still unread, the "{t("nav.step.raw")}" step on the
          bar at the top says so on hover, and says it by counting: how many are left, and that
          you can build all the same. It says where to start, it does not lock anything.
        </p>
      </Alert>

      <Block title="One button, and it launches everything">
        <Paragraph>
          "{t("transcribe.startAll")}" is in the block at the top of the screen — the same
          block, with the same big button, every step starts from — and it is the only one
          there is: it launches in one go whichever origins have something to do.
          Underneath it is <strong>two jobs</strong>, one per origin, so two show up in the queue
          and both have to be stopped if you change your mind.
        </Paragraph>
      </Block>

      <Block title="A document this installation has already read arrives read">
        <Paragraph>
          A document is identified by its content, not by its name or by the subject it sits in.
          Upload one this installation has already read — the same exercise sheet in two
          subjects, or the same file again under another name — and its pages are copied across
          as you upload it, so the row shows up already up to date, with no model call spent.
        </Paragraph>
        <Paragraph>
          It only happens when everything matches: the file's content and the settings it was
          read under. If any of that has moved since, the document comes up pending and is read
          like any other. The pages are <strong>copied</strong>, so correcting one here does not
          touch the other subject's.
        </Paragraph>
      </Block>

      <Block title="How each document is doing">
        <Rows
          items={[
            {
              key: "done",
              head: (
                <span className="flex items-center gap-1.5 text-small text-muted-foreground">
                  <Check aria-hidden className="size-4 text-settled" />
                  {t("transcribe.state.done")}
                </span>
              ),
              body: "Its pages are written and still hold. Builds reuse them as they are, without asking the model again.",
            },
            {
              key: "pending",
              head: <Badge variant="outline">{t("transcribe.state.pending")}</Badge>,
              body: "It has not been read yet. Not a problem: if you do not read it first, the build will.",
            },
            {
              key: "stale",
              head: <Badge variant="attention">{t("transcribe.state.stale")}</Badge>,
              body: "It was read, but something it depended on has changed. The row says what: the document itself, the reading route, the model, the render resolution, the OCR, or the prompt.",
            },
            {
              key: "failed",
              head: <Badge variant="danger">{t("transcribe.failedCount", { n: "N" })}</Badge>,
              body: "It sits beside the state rather than in its place: a document can be read and up to date and still hold pages the model could not make out. That badge is the only sign that text is missing there, and it is fixed by opening the document.",
            },
          ]}
        />
        <Paragraph>
          The reason sits on the document's own row rather than hidden inside a tally: "2 to be
          read again" reports the state and keeps quiet about the very half you act on. A state
          with no reason is not a state, and what is underneath is a list of pages the next build
          was about to redo in silence.
        </Paragraph>
        <Paragraph>
          Once an origin is up to date, its whole card takes the blue of its mark and the tick
          becomes a filled circle. And once both are, the same block that closes every step
          appears at the foot of the screen: "{t("stage.continue", { n: stepNumber(1) })}".
        </Paragraph>
      </Block>

      <Alert tone="settled" title="Stopping it loses nothing">
        <p>
          Pages are written document by document, so a cancelled reading keeps everything
          that had already come out, and relaunching it carries on from where it was. The button
          says so on the spot, because one that might be throwing work away is one nobody
          presses.
        </p>
      </Alert>

      <Block title="Correcting a page by hand">
        <Steps
          items={[
            <>
              Hover over the document's row and press the pencil. It opens with the index of
              pages on the left and the markdown of whichever you pick on the right.
            </>,
            <>
              Edit and save. You can also <strong>insert</strong> a blank page right after the
              one you are looking at, or <strong>delete</strong> it: both renumber the ones that
              follow, and the screen says so before doing it.
            </>,
            <>
              Leaving with unsaved changes asks before discarding them, and so does switching
              page.
            </>,
          ]}
        />
        <Paragraph>
          Only two kinds of page are flagged, because they are the only ones that need a person:
        </Paragraph>
        <Rows
          items={[
            {
              key: "failed",
              head: <Badge variant="danger">{t("doc.mark.failed")}</Badge>,
              body: t("doc.failedPage"),
            },
            {
              key: "empty",
              head: <Badge variant="attention">{t("doc.mark.empty")}</Badge>,
              body: t("doc.emptyPage"),
            },
          ]}
        />
        <Detail title="Why what you correct by hand wins">
          <p>
            Later builds read these pages from disk instead of asking the model again, so a
            correction of yours <strong>beats what the model said and survives every build that
            comes after</strong>. Editing does not mark the document as expired either: all that
            is discarded are the two seams around the page you touched, because they were decided
            against text that is no longer there.
          </p>
          <p>
            The last remaining page cannot be deleted. A document with zero pages reads as "
            {t("transcribe.state.pending")}", and the next build would silently redo everything
            that had been corrected.
          </p>
          <p>
            While an origin is being read you can review and correct the documents that
            have already come out. The only one that will not open is the one being rewritten at
            that instant: its row says so with an activity indicator and with "
            {t("transcribe.transcribing")}" in place of its state.
          </p>
        </Detail>
      </Block>

      <Detail title="Both origins take the same route, and it costs what it costs">
        <p>
          Notes and exercises are read by the same algorithm: each page is drawn and the
          model is asked to copy it character by character, completing nothing and correcting
          nothing. One call per page, no exceptions, because the page image is the honest source
          — a table split across two sheets, a code block with its indentation, or a formula
          survive that way and no other.
        </p>
        <p>
          Every join between two pages gets a second, far shorter call that decides only{" "}
          <em>how</em> they are glued: whether the sentence carries on, which separator goes in
          between, and how many repeated header lines to drop. It rewrites nothing — that is
          what keeps "copy character by character" true. Which is why the progress bar moves
          through pages first and through seams afterwards, within the same document.
        </p>
        <p>
          A Word or PowerPoint file has no page to draw: it declares its own structure and is
          read straight as text, in seconds. What that path does not see are the{" "}
          <em>images</em> — and in an exercise workbook that is where the formulas and a
          program's "expected output" tend to be — so each image is shown to the model on its
          own, under the same rules as a figure on a page: a formula comes back as a formula, a
          screenshot of code as code, and only what cannot be copied is noted as a figure. Each
          image is remembered by its content, so the logo repeated in every document is read
          once. An image in a format that cannot be opened (Office's WMF and EMF metafiles,
          when the installation has no LibreOffice) leaves a visible mark in its place and a
          badge on the document's row.
        </p>
        <p>
          The consequence shows in the phase bar explained in "{t("guide.sec.runs")}": the
          reading the notes is now the widest section of the graph build. Taking it out of there,
          and being able to watch it while it happens, is exactly what this screen exists for.
        </p>
      </Detail>
    </div>
  );
}

/**
 * How each of the three steps that build something ends. The same block in all three
 * sections because it is the same task: the only difference is the questions, which the
 * server writes.
 */
function Verdict({ artifact }: { artifact: string }) {
  const { t } = useT();
  const next = nextStepOf(artifact);
  return (
    <Block title="How this step is closed">
      <Paragraph>
        A step opens <strong>read-only</strong>: it is there to be looked at, not touched.
        Looking and correcting are two different things, and that is why they are two
        different moments. At the foot of the screen, not on the way in, three things follow
        one another: the verdict, the offer to correct, and the next step.
      </Paragraph>
      <Steps
        items={[
          <>
            <strong>Look at what is above.</strong> You do not have to read all of it: what is
            asked afterwards is whether it sounds like your subject.
          </>,
          <>
            <strong>"{t("stageReview.openTitle")}"</strong>, the button at the foot, unfolds a
            short questionnaire beneath it: five questions, the same five ideas on all three
            steps. You can leave it half done and come back, because half an answer is a datum
            too, and once you have saved you can close it without losing anything. It is there
            even when the previous step has been reopened: what is judged is what is built.
          </>,
          <>
            <strong>"{t("stage.curate.start")}"</strong> unlocks the editing of what is above.
            While you are correcting, a bar pinned to the bottom edge says how the changes
            stand and carries "{t("stage.curate.save")}" and "{t("stage.curate.stop")}".
          </>,
          <>
            <strong>
              "
              {next.number === null
                ? t("stage.continueGenerate")
                : t("stage.continue", { n: next.number })}
              "
            </strong>{" "}
            closes the step and takes you to whatever comes after it. Before closing it saves whatever you
            had pending, and if that write is refused it neither closes nor moves on: it says
            so and leaves you where you were.
          </>,
        ]}
      />
      <Paragraph>
        Correcting is optional and so is the verdict: you can carry on having done neither.
        What you cannot do is move on without closing, because the next step needs this one
        taken as good.
      </Paragraph>
      <Detail title="What exactly is kept">
        <p>
          Your answers, with the <em>particular version</em> you judged. If you build the
          step again and judge it again, nothing is overwritten: they are two data, because
          "it came out badly" and "I redid it and it came out well" are two different things.
          Answering again about the same one does correct your earlier answer.
        </p>
        <p>
          Whether you <strong>corrected before judging</strong> is kept too. It is not
          surveillance: it is a variable of the study, because the mark of somebody who has
          curated the result by hand is not the mark of somebody judging it as it came out,
          and without telling them apart the two are mixed into the same average.
        </p>
        <p>
          There are five questions on every step and they follow the same order on all three:
          whether something is there that should not be, whether something is missing, whether
          the step does what it is for — the parts of each type, the order of the syllabus,
          the concept on each exercise — how much you would have to correct before you could
          use it, and 1 to 5 overall. The last two are identical on all three, and those are
          the ones that let one step be compared with another. At the end there is an optional
          box for whatever does not fit the options.
        </p>
        <p>
          It is the only thing asked in return for using this, and it is what is being
          measured: without it there is no way to know whether the system prepares a subject
          well or only looks as if it does.
        </p>
      </Detail>
    </Block>
  );
}

function Profile() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.prepare")} title={t("guide.sec.profile")}>
        <p>
          What shapes the exercises you set come in: a question with options, a piece of code to
          write, a bug to fix. Of each shape it records which parts it carries, how it is
          written, and what makes it more or less difficult. It is the template new exercises
          are written from.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "Where it comes from",
            value: `From the documents you left in "${t("raw.slot.exemplars")}", reading a sample.`,
          },
          {
            label: "What it costs",
            value: "One long pass over a sample of your exercises, not over all of them.",
          },
          {
            label: "What it unlocks",
            value: "Collecting your exercises, and deciding which concepts of the syllabus work as a label.",
          },
        ]}
      />

      <Block title="How it is done">
        <Steps
          items={[
            <>
              In Step {stepNumber(0)}, upload one or more documents with real exercises from the
              subject into "{t("raw.slot.exemplars")}". With no material, the build button is off
              and says why.
            </>,
            <>
              Press "{t("build.start")}", the large button in the middle of the screen. What
              comes out is a <strong>first version</strong>, not a final result, and no rebuild
              is offered: a second pass over the same documents gives nothing different.
            </>,
            <>
              Read each <strong>exercise type</strong> — the strip at the top picks them one by
              one: what it is, when one of its exercises is basic, intermediate or advanced, and
              the <strong>"{t("modality.rules")}"</strong>, which are the only thing the model is
              told about the <em>shape</em> of an exercise.
            </>,
            <>
              If something does not fit, "{t("stage.curate.start")}" at the foot of the screen
              unlocks the editing. Only then do "{t("modality.add")}" and each type's parts show
              up — that is the most technical question on the whole route, and not the one asked
              on the way in.
            </>,
            <>
              Judge the step and carry on. Carrying on saves whatever you had unsaved and closes
              the step.
            </>,
          ]}
        />
        <Paragraph>
          There is no tab with the raw file. What writes the changes is "
          {t("stage.curate.save")}", in the bar pinned to the bottom, and "carry on" too. That
          same bar says whether something is unsaved and, when the file does not{" "}
          <em>load</em>, the validator's own sentence — while it does not load, nothing can be
          saved, which is what keeps the subject from being left with a broken template.
        </Paragraph>
      </Block>

      <Block title="Exercise types, and why they show up everywhere else">
        <Paragraph>{t("modality.whatAre.body")}</Paragraph>
        <Paragraph>
          Which is why the exercise type comes back later as a column and a filter over your
          exercises, and as the first question when you ask for a new one. With a single type
          declared neither is drawn: a dropdown with one option chooses nothing.
        </Paragraph>
      </Block>

      <Block title="The difficulty level, which every type carries">
        <Paragraph>
          Every exercise type carries a <strong>difficulty level</strong>, and it is not one more
          part: it is not added, not removed and not renamed. It lives at the top, in "
          {t("modality.identity")}", right below the type's description — while you are looking,
          the three rungs are shown with what the criterion says about each one underneath; while
          you are correcting, it becomes a text box.
        </Paragraph>
        <Paragraph>
          The <strong>three levels are the same in every type</strong>. That is what makes
          "advanced" mean the same thing in a multiple-choice question and in a programming
          exercise, and what lets a list with mixed types be filtered by it. What changes from
          one type to the next is <em>what puts</em> an exercise on each level, and that is the
          only part you write.
        </Paragraph>
        <Rows
          items={[
            {
              key: "signals",
              head: "Write it with signals you can see",
              body: "What the exercise asks for, how many steps have to be chained, how many things have to be combined, whether the answer is read off directly or has to be worked out. «It is hard for a beginner» cannot be checked by looking at an exercise, so it classifies nothing.",
            },
            {
              key: "scale",
              head: "The scale is measured against your exercises",
              body: "«Basic» is the simplest thing your course actually sets in that type, and «advanced» the most demanding it ever sets. A criterion copied from another course leaves all your material on «basic», and then the level says nothing.",
            },
            {
              key: "spread",
              head: "Check it by spreading them",
              body: "Take a few of your own exercises of that type and apply the criterion. If they all land on the same level, the criterion does not separate: sharpen it until it spreads them.",
            },
            {
              key: "concept",
              head: "It is not what it is about, nor how long it is",
              body: "A long statement is not a hard exercise, and one from the last unit is not hard for being at the end. What each exercise is about is already recorded elsewhere, against the syllabus.",
            },
            {
              key: "who-reads-it",
              head: "Somebody who is choosing reads it",
              body: "When you ask for a new exercise you see the three levels with their criterion beside them and pick one. That is why the criterion is written rung by rung, each with an example of your own and with where the border to the next one is: «basic (recognition)» tells whoever has to choose nothing at all.",
            },
          ]}
        />
      </Block>

      <Block title="What each part of a type has">
        <Paragraph>
          This is only seen <strong>while you are correcting</strong>: the{" "}
          {t("modality.fieldsOf", { name: "…" })} block appears under the two cards above the
          moment you press "{t("stage.curate.start")}", and not before. It is the most technical
          thing asked anywhere on the route, and the screen does not open on it.
        </Paragraph>
        <Rows
          items={[
            {
              key: "tipo",
              head: t("field.type.label"),
              body: "Text, number, list, or a closed enumeration of values. Pick an enumeration and the list of permitted values appears underneath.",
            },
            {
              key: "obligatorio",
              head: t("field.required.label"),
              body: t("field.required.hint"),
            },
            {
              key: "descripcion",
              head: t("field.description.label"),
              body: t("field.description.hint"),
            },
            {
              key: "primario",
              head: t("field.primary.badge"),
              body: "The one carrying the statement. It is the text the exercise is matched against the syllabus's concepts with, and only a part of type text can be it.",
            },
          ]}
        />
      </Block>

      <Alert tone="danger" title="Touching it after collecting your exercises invalidates them">
        <p>
          Your exercises were collected with these parts. Change a type's parts and Step{" "}
          {stepNumberOf("exemplars_bank")} goes to "{t(STATUS.stale.labelKey)}" and they have to
          be collected again.
        </p>
      </Alert>

      <Detail title="This first version is not stable, and it is worth knowing">
        <p>
          The types are inferred from a sample of your exercises, and two passes over the same
          material have gone as far as producing <em>different</em> sets of parts. Treat it as a
          starting point: the version you take as good is yours, not its.
        </p>
      </Detail>
      <Verdict artifact="exemplars_profile" />
    </div>
  );
}

function Graph() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.prepare")} title={t("guide.sec.graph")}>
        <p>
          Your subject's syllabus: its concepts, grouped into units and joined by what has to be
          known before what. Everything tagged and written afterwards comes from here: neither the model nor
          you can use a concept that is not in the syllabus.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "Where it comes from",
            value: `From the documents you left in "${t("raw.slot.corpus")}", read whole.`,
          },
          {
            label: "What it costs",
            value:
              "It is the most expensive job on the route: one call per page of your notes, and several that reason over the whole list.",
          },
          {
            label: "What it unlocks",
            value: "Putting the syllabus's concepts on your exercises, saying how far the class has got, and asking for new exercises.",
          },
        ]}
      />

      <Block title="A list, with a map under it">
        <Paragraph>
          What you see first is the syllabus: the units in teaching order, folded. Open them, or
          search and the ones with results open on their own. Every row carries the concept and
          whether it <strong>{t("kg.taggable").toLowerCase()}</strong> — "{t("common.yes")}" or "
          {t("common.no")}"; clicking it opens its card <em>beside the list</em>, with its unit,
          its description and its relations. While you are only looking, that is a read, which is
          exactly what is asked here: open a concept and see whether what it says about it is your
          subject.
        </Paragraph>
        <Paragraph>
          Press "{t("stage.curate.start")}" at the foot of the screen and that same card becomes
          editable — the name, the unit and the relations — and the list grows the buttons for
          adding a unit and adding a concept, and each row's "{t("kg.taggable").toLowerCase()}"
          turns from a "{t("common.yes")}" into a switch.
        </Paragraph>
        <Paragraph>
          The map is folded under the list, because the first thing you see of a syllabus has to
          be the syllabus and not its drawing. {t("kg.mapDescription")} The enlarge button opens
          it full screen <em>with the card beside it</em>, so you can change what you pick
          without going back.
        </Paragraph>
        <Paragraph>
          The canvas has two layouts: <strong>"{t("canvas.layout.force")}"</strong>, which puts
          each concept next to the ones it relates to, and{" "}
          <strong>"{t("canvas.layout.curriculum")}"</strong>, which orders by prerequisite level.
          Switching rebuilds nothing: the nodes ease to their new positions. A level is a{" "}
          <em>band</em> and not a row, because a real syllabus spreads prerequisites very
          unevenly; with fewer than three levels the canvas says so, because that is a fact
          about the syllabus and not a broken view.
        </Paragraph>
      </Block>

      <Block title="The build does not end with the syllabus">
        <Paragraph>
          As soon as the syllabus is written, two more things chain on their own, and the screen
          says so while they happen. They block nothing below them: you can be reading the
          syllabus while they finish.
        </Paragraph>
        <Steps
          items={[
            <>
              <p className="font-medium">Each concept's description</p>
              <p className="text-small text-muted-foreground">
                The prose describing each concept, written against the paragraphs of your notes it
                came from. <strong>It is the text matched against, not the name.</strong> They
                are corrected on the concept's own card, which is where they are being read — and
                they are the one thing that can still be corrected with the step closed, because
                they live apart and expire nothing.
              </p>
            </>,
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                Which concepts work as a label
                <Badge variant="attention">
                  needs Step {stepNumberOf("exemplars_profile")} closed
                </Badge>
              </p>
              <p className="text-small text-muted-foreground">
                The ones that would fit any exercise at all — "coding", "design" — are marked as
                NOT working as a label: they still exist and still work through their relations,
                they simply stop being able to be what an exercise is about. When in doubt,
                exclude: a vague label pollutes every one of your exercises. It is judged against
                the previous step's exercise types, which is why that step comes first.
              </p>
            </>,
          ]}
        />
        <Paragraph>
          The button that launches that review again is at the top right and{" "}
          <strong>only appears while you are correcting</strong>: it is something done TO the
          syllabus, not something to look at. With the step already closed it is visible, but it
          refuses and says why.
        </Paragraph>
      </Block>

      <Block title="Curating the syllabus by hand">
        <Paragraph>
          With "{t("stage.curate.start")}" pressed you can rename what came out crooked, delete
          what is not a concept of the subject, move concepts between units and fix relations.
          Renaming a concept carries with it the piece of your notes it came from; deleting it lets
          it go. Ticking or unticking "{t("kg.taggable").toLowerCase()}" does not move the row:
          it stays where it was, under the hand that pressed it.
        </Paragraph>
      </Block>

      <div className="space-y-2">
        <Detail title="Why matching is not done on the concept's name">
          <p>
            A name is a two-word label and says nothing about what is practised by using it. What
            is matched against is the <em>description</em>, fused with what your exercises
            already carrying that concept have in common.
          </p>
          <p>
            That is why a badly written description is paid for every time a concept is put on an
            exercise and every time a new one is written, and why they are worth reading.
          </p>
        </Detail>

        <Detail title="What is assumed known and what is forbidden">
          <p>
            Around the concepts you ask for, two lists are taken from the syllabus and handed to
            the model:
          </p>
          <Rows
            items={[
              {
                key: "sabido",
                head: <span className="text-settled">{t("form.given")}</span>,
                body: "What has to be known before the concept asked for and the class has already covered. The exercise may lean on it, but must not turn it into the difficulty. It travels with its description, not as a bare name.",
              },
              {
                key: "prohibido",
                head: <span className="text-destructive">{t("form.forbidden")}</span>,
                body: "What comes after the concept asked for and the class has not seen yet. It must not appear.",
              },
            ]}
          />
          <p>
            Both walk the whole syllabus and not one hop, and both are bounded by whatever you
            say the class has covered. When you ask for an exercise they are drawn before
            launching, so you can see exactly what the model is going to work with.
          </p>
        </Detail>
      </div>
      <Verdict artifact="knowledge_graph" />
    </div>
  );
}

function Bank() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.prepare")} title={t("guide.sec.bank")}>
        <p>
          Your exercises, collected one by one out of the documents, each with the syllabus
          concepts it practises. What is reviewed here is <strong>that matching</strong>: whether
          the concept each exercise has been given is the one it really practises.
        </p>
        <p>
          It matters because these are the examples that accompany every new exercise: this is
          where "here is how exercises are written in this subject" comes from, for the model to
          imitate, and they are picked by the concept each one carries.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "Where it comes from",
            value: `From the documents in "${t("raw.slot.exemplars")}", walked one after another.`,
          },
          {
            label: "What it costs",
            value: "It grows with the number of documents: all of them are walked, whole.",
          },
          {
            label: "If you cancel it",
            value: "The whole pass is lost, but what you already had stays as it was: it is only replaced at the end.",
          },
        ]}
      />

      <Alert tone="info" title="Collecting and tagging are one single job">
        <p>
          Each document is given its concepts as it comes out, so by the time it finishes
          everything is already tagged: there is no intermediate step to launch. What is left is
          correcting what came out wrong, and there are three separate controls for that.
        </p>
      </Alert>

      <Block title="The strip of meters says two different things">
        <Rows
          items={[
            {
              key: "etiquetados",
              head: t("bank.taggedItems"),
              body: "How many of your exercises carry at least one concept. It is the correcting still ahead of you. It is only drawn while some are missing: with everything tagged there is nothing to look at there.",
            },
            {
              key: "cobertura",
              head: t("bank.conceptsWithExample"),
              body: t("bank.coverageBody"),
            },
          ]}
        />
        <Paragraph>
          The two look in opposite directions and are worth keeping apart: one counts{" "}
          <em>exercises with no concept</em>, the other <em>concepts with no exercise</em>.
          Everything can be tagged while half the syllabus has not a single example to imitate.
        </Paragraph>
      </Block>

      <Block title="It is reviewed by suspicion, not top to bottom">
        <Steps
          items={[
            <>
              First, the ones <strong>left with no concept</strong>. The strip of meters at the
              top counts them and "{t("bank.seeUntagged", { n: "N" })}" filters them.
            </>,
            <>
              Then the ones carrying <strong>a single concept</strong>, or one that does not fit:
              every row measures the same and the concepts column reads at a glance, which is
              where the matching goes wrong without saying so. Click a row to read the whole
              exercise.
            </>,
            <>
              If there is correcting to do, "{t("stage.curate.start")}" at the foot of the
              screen: then each exercise can be edited and its <strong>primary concept</strong>{" "}
              changed by hand, which is the one that decides what it is compared against
              afterwards.
            </>,
          ]}
        />
      </Block>

      <Block title="The three ways to put concepts back, which do not do the same thing">
        <Paragraph>
          All three <strong>only appear while you are correcting</strong>: they are the only
          things on this screen that write. What they say is not lost by hiding them — how many
          exercises have no concept is still on the meter, and "
          {t("bank.seeUntagged", { n: "N" })}" is a filter and stays.
        </Paragraph>
        <Rows
          items={[
            {
              key: "pendientes",
              head: <>"{t("bank.retagUntagged", { n: "N" })}"</>,
              body: "It runs over exactly the exercises left with no concept, never over all of them. It sits in the strip of meters, next to the number it acts on.",
            },
            {
              key: "todo",
              head: <>"{t("bank.retagAll")}"</>,
              body: "All of them, from scratch. It overwrites the current concepts, the ones you corrected by hand included, which is why it asks for confirmation before it runs.",
            },
            {
              key: "seleccion",
              head: <>"{t("bank.retagSelected")}"</>,
              body: "Only the exercises ticked by hand, even if they already had a concept. It lives at the foot of the table, because it is contextual: it belongs to the rows and not to the totals.",
            },
          ]}
        />
      </Block>

      <Block title="Finding one particular exercise">
        <Paragraph>
          Above the table there are five filters that combine: a <strong>search</strong> over the
          statement's text or by id, the <strong>exercise type</strong> — the ones from Step{" "}
          {stepNumberOf("exemplars_profile")}, each with how many of your exercises it has — the{" "}
          <strong>source document</strong>, the <strong>level</strong> — the three rungs, each
          with its own count — and, at the end of the row, the{" "}
          <strong>"{t("bank.untagged")}"</strong> toggle, which is the only one of the five that
          talks about the work left rather than about what an exercise is like. With a single
          type declared that dropdown does not appear: a menu with one option filters nothing.
        </Paragraph>
        <Paragraph>
          Those menus' counts are over <em>all</em> your exercises and do not move with the other
          filters: they say what is in there, not what you have just asked. There is no order
          control: the list runs in the order the exercises were collected in. The level is{" "}
          <em>filtered</em> and not sorted, because with three rungs sorting only groups, and the
          question people actually ask is «show me the advanced ones».
        </Paragraph>
        <Paragraph>
          Each page holds <strong>seven exercises</strong>, and every closed row measures the
          same: the statement is cut to two lines and at most three concepts are drawn, with a "+N"
          that names the rest on hover. A table whose rows grow with the length of each statement
          cannot be read down a column, which is how you look for what is wrong.
        </Paragraph>
      </Block>

      <Detail title="Retrying makes sense: the matching improves between passes">
        <p>
          Every well-tagged exercise pulls its concept towards where it really is, so what one pass
          learns the next one uses. An exercise that finds no concept today may find one tomorrow
          without your having touched anything.
        </p>
        <p>
          That is why the ones left out are tried again on every pass, instead of being marked as
          impossible.
        </p>
      </Detail>
      <Verdict artifact="exemplars_bank" />
    </div>
  );
}

function Generate() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.use")} title={t("guide.sec.generate")}>
        <p>
          The first door of the <strong>{t("nav.phase.test").toLowerCase()}</strong>, and what
          the construction exists for: one commission, one batch of new exercises. The form is an accordion — it is answered
          top to bottom and each question collapses to a single line once answered, so changing
          the concepts again costs one click and no scrolling.
        </p>
        <p>
          What is <strong>numbered is the commission</strong>: four questions at most, and two of
          them appear only if your subject needs them. The free text carries no number and sits
          folded in "{t("form.instructions.title")}", underneath.
        </p>
      </SectionHead>

      <Block title="The numbered questions, in the order they are asked">
        <Steps
          items={[
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {t("form.type.title")}
                <Badge variant="outline">only with several exercise types</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                {t("form.type.hint")} With a single type declared, this question is not asked.
              </p>
            </>,
            <>
              <p className="font-medium">{t("form.practise.title")}</p>
              <p className="text-small text-muted-foreground">
                {t("form.practise.hint")} Only concepts that{" "}
                <strong>{t("kg.taggable").toLowerCase()}</strong> are offered: this is where you
                choose what the exercise is about, and a generic concept is no use for that.
              </p>
            </>,
            <>
              <p className="font-medium">{t("form.difficulty.title")}</p>
              <p className="text-small text-muted-foreground">
                The three levels of the type you chose, each with the criterion you wrote in Step{" "}
                {stepNumberOf("exemplars_profile")} underneath, plus "{t("decision.any")}" to
                leave it unpinned. It is the same ladder in every type, so asking for "advanced"
                means the same thing here as it does in the list of your exercises.
              </p>
            </>,
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {t("form.decisions.titleMany")}
                <Badge variant="outline">only if some type leaves something to you</Badge>
              </p>
              <p className="text-small text-muted-foreground">{t("form.decisions.hint")}</p>
            </>,
          ]}
        />
      </Block>

      <Block title={`What is optional, folded into "${t("form.instructions.title")}"`}>
        <Paragraph>
          Under the numbered questions there is a disclosure saying at a glance whether anything
          is written inside it. It is not required, and that is why it takes up no number: the
          screen's order is first what has to be answered, then what may be added.
        </Paragraph>
        <Rows
          items={[
            {
              key: "instructions",
              head: t("form.instructions.title"),
              body: (
                <>
                  {t("form.instructions.hint")} There is a 600-character cap which the box itself
                  counts down, and what you write goes through two filters before reaching the
                  model.
                </>
              ),
            },
          ]}
        />
      </Block>

      <Block title="Before launching, what the syllabus is about to tell the model">
        <Paragraph>
          Under the chosen concepts, "{t("form.graphSays")}" appears with the two lists that will
          be handed over: "{t("form.given")}" and "{t("form.forbidden")}". They come out of the
          syllabus and of whatever you said the class has covered, and they are visible{" "}
          <em>before</em> anything is spent.
        </Paragraph>
        <Paragraph>
          The same box warns about <strong>concepts with no example</strong>: if a chosen concept has
          no exercise of yours — or none of the type asked for — the batch is written with no
          example to imitate and quality usually drops. The list only offers concepts your exercises
          can illustrate, and the selector itself says how many it is leaving out. It can show up
          anyway when you restore an old commission, if the material has changed since.
        </Paragraph>
      </Block>

      <Block title="What happens to what you write in the free text">
        <Rows
          items={[
            {
              key: "guardrail",
              head: "1 · Guardrail",
              body: 'A fixed check blocks orders to override instructions ("forget everything above…"), and then a judge model decides whether there is anything harmful or an attempt to get around the exercise\'s own restrictions.',
            },
            {
              key: "admisibilidad",
              head: "2 · Admissibility",
              body: "It decides whether what you are asking for belongs to this box or to something you already decided above: the concepts, the exercise type, the exercise's parts, or the subject itself. If it does, it tells you which control decides it.",
            },
          ]}
        />
        <Alert tone="settled" title="If the judge cannot answer, your request goes through">
          <p>
            Engine down, unreadable reply, or a verdict that does not hold up: all three let the
            commission carry on and say so in the log. A screen that blocks when its judge is
            down blocks everything.
          </p>
        </Alert>
      </Block>

      <Block title="Which model writes it">
        <Paragraph>
          You choose it, out of what the installation offers. Whoever administers it sets that
          list in «Configuration → Generator models»; you get a card per model with what each
          one costs — one answers in seconds, the other takes minutes and deliberates — and
          the first of the list comes selected. With a single one on offer nothing is asked.
        </Paragraph>
        <Paragraph>
          It is chosen <em>before</em> the effort and not after, because how many levels there
          are and which one is worth avoiding is the model's business. Some models answer the
          same whatever level you set: those draw no bar, and which ones they are is declared
          by whoever administers the installation too. The model is stored with every exercise,
          so in «{t("menu.savedVariants")}» you can compare two statements knowing what wrote
          each.
        </Paragraph>
      </Block>

      <Block title="Reasoning and effort">
        <Paragraph>
          The switch decides whether the model deliberates before answering; the bar beside it,
          how much. A high effort on the local model multiplies the time several times over
          without necessarily improving the statement, and the screen itself warns you when the
          model about to serve the commission is one of those that runs away at the top end.
        </Paragraph>
      </Block>

      <Block title="While it runs">
        <Paragraph>
          On launching, the form folds into one line holding the commission's summary, and a
          strip appears above the results: the job's name, its status, how long it has been
          going, and — while it is waiting its turn — "{t("queue.queuedAhead", { n: "N" })}"{" "}
          <em>instead of</em> the bar. The cancel button lives there, and only there.
        </Paragraph>
        <Paragraph>
          Everything else folds behind "{t("run.detail")}" on that same strip: the steps, the
          text as it is written, the exercises of yours the model was shown, and the technical
          details of the call. It is the only place those three are visible. It opens by itself
          while the job runs and closes when it ends, unless you touch it.
        </Paragraph>
      </Block>

      <Block title="What you see when it finishes">
        <Rows
          items={[
            {
              key: "guardada",
              head: <Badge variant="settled">{t("result.saved")}</Badge>,
              body: (
                <>
                  Every exercise is saved into "{t("menu.savedVariants")}"{" "}
                  <em>the moment it validates</em>, with its whole commission. A batch cancelled
                  at the third keeps three.
                </>
              ),
            },
            {
              key: "senales",
              head: <Badge variant="attention">2 signals</Badge>,
              body: (
                <>
                  What can be checked without judging the exercise: whether it names something
                  the class has not seen yet, whether it looks too much like an example or
                  another one in the same batch, and whether re-reading it recognises the concept
                  you asked for. The first two make it <em>try again</em> before handing it to
                  you; what arrives flagged is what still did not come out clean, and at that
                  point <strong>it is a signal for whoever reads, not a rejection</strong>.
                </>
              ),
            },
            {
              key: "reintentada",
              head: <Badge variant="outline">{t("result.retried", { n: "N" })}</Badge>,
              body: "How many times the call had to be repeated because of those two signals. It does not say the exercise is bad: it says what it cost.",
            },
          ]}
        />
        <Paragraph>
          An exercise with nothing to flag carries no such box: it is only drawn when there is
          something to look at.
        </Paragraph>
      </Block>

      <Block title="And afterwards">
        <Rows
          items={[
            {
              key: "variar",
              head: <>"{t("generate.vary")}"</>,
              body: "Reopens the form with everything filled in and leaves the results in view until you launch another batch. Change whatever you like — or change nothing, if what you want is another batch of the same commission — and launch again.",
            },
            {
              key: "cero",
              head: <>"{t("generate.startOver")}"</>,
              body: "Reopens the form empty, for a commission that has nothing to do with the last one.",
            },
            {
              key: "exportar",
              head: <>"{t("generate.export")}"</>,
              body: "A menu with three ways out for the whole batch: copy the JSON, download it, or download it as Markdown.",
            },
            {
              key: "como-esta",
              head: <>"{t("generations.moreLikeThis")}"</>,
              body: (
                <>
                  It is in "{t("nav.myVariants")}" and recovers the commission of one
                  particular exercise, even from another day.
                </>
              ),
            },
          ]}
        />
      </Block>
    </div>
  );
}

function Evaluate() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.use")} title={t("guide.sec.evaluate")}>
        <p>
          The same commission solved by three different architectures and presented{" "}
          <strong>blind</strong>, so that you choose without knowing which is which. It is the
          part of the system that exists to measure it, not to produce material.
        </p>
        <p>
          You ask for the comparison and you judge it: you pick the concept you want the
          exercise on, the three versions are prepared, and you read them when they are ready.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "What you are asked for",
            value: "Reading three proposals, one question per card, and one choice.",
          },
          {
            label: "What it produces",
            value: "A saved session with the three proposals and your judgement.",
          },
          {
            label: "What you need",
            value: "The four steps closed: the three versions are written from your subject.",
          },
        ]}
      />

      <Block title="The two tabs">
        <Rows
          items={[
            {
              key: "encargo",
              head: t("eval.tab.compose"),
              body: 'Where the screen opens. You pick the concept and the type of exercise you want: the same "Generate exercises" form, without two controls — how many exercises, and whether the model deliberates — because a comparison is always one per version.',
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
          button in the header takes you back to the list.
        </Paragraph>
      </Block>

      <Block title="How a comparison goes">
        <Steps
          items={[
            <>
              The three proposals appear, unlabelled and in an order that is yours alone. Above
              them, in one line, the commission: the type of exercise, the concepts and the level
              if one was pinned. It is the same for all three, so it gives nothing away.
            </>,
            <>
              The three cards are the same height and do not scroll inside: the page moves,
              they do not. A long exercise is read with the expand button in its header, at
              reading size and with the question at the foot; ← and → move between them.
            </>,
            <>
              <strong>You answer one question per card</strong>: whether you would set it in
              class — or, if you are a student, whether it would be useful to practise with. One
              click, first impression, no dwelling on it. The three steps above say which one
              you are on.
            </>,
            <>
              <strong>You choose one</strong>. The choice bar stays pinned to the foot of the
              window; it does not activate until you have answered all three, and you can
              always say that none of them convinces you.
            </>,
            <>
              Only then is it revealed which architecture wrote each one: a row per proposal,
              with what you answered about it, the model and the time, and a
              "{t("reveal.detail")}" that unfolds the technical detail.
            </>,
            <>
              If you feel like it, you rate the system's one on four scales, with its exercise
              beside them. It is <strong>optional</strong>: the comparison was already recorded
              when you chose.
            </>,
            <>
              Below it, "{t("eval.backToList")}" closes the session and takes you back to your
              history, which is where the next one is asked for.
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
          the study.
        </p>
      </Alert>

      <Detail title="The three architectures being compared">
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
          sees the concepts, who the descriptions, who the bank's examples, who the
          prerequisites. {t("fair.footnote")}
        </p>
      </Detail>

      <Detail title="Why the order of the cards is different for each person">
        <p>
          If two evaluators judge the same three exercises, each of them sees them in an order of
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
          <strong>How many exercises are generated</strong>: always one per architecture. It is what
          makes the session the unit of analysis.
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

function Runs() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.daily")} title={t("guide.sec.runs")}>
        <p>
          Jobs queue <strong>per engine</strong>, and each engine has its own room. The local one
          holds a single job: the GPU is one, and two jobs on it would do nothing but swap
          weights. The remote one holds <strong>several at once</strong>, because what is shared
          there is not a machine but a quota, and the quota is administered call by call by the
          throttle — so two people can generate against Cerebras at the same time without waiting
          for each other. A local job and a remote one never wait for each other either. You can
          close the tab: the job runs on the server and you find it where it was when you come
          back. Every job is watched <strong>on the screen that launched it</strong>: there is no
          separate place to keep an eye on all of them.
        </p>
      </SectionHead>

      <Block title="The six states">
        <Paragraph>
          No state is told apart by colour alone: each has its own shape, and it is read on the
          bar at the top, under each step's name. The step's header carries no tag at all: what
          a state asks of you is said by the notices on the screen.
        </Paragraph>
        <Rows
          items={STATE_ORDER.map((key) => ({
            key,
            head: (
              <span className="flex items-center gap-3">
                <StatusMark
                  status={key === "blocked" ? "missing" : key}
                  blocked={key === "blocked"}
                  size="md"
                />
                {t(STATUS[key].labelKey)}
              </span>
            ),
            body: STATE_HINTS[key],
          }))}
        />
      </Block>

      <Block title="The bar is the plan">
        <div className="space-y-3 rounded-lg border border-border bg-card p-4">
          <BuildPlanBar />
          <Paragraph>
            This is the graph builder's real plan, read from the API and not copied out here.
            Each section is a phase and its width is that phase's <em>measured weight</em>: which
            is why reading the notes takes up a third of the bar on its own, linking and
            cleaning almost half of it between them, and the final curation is a hairline. The
            one that moves is the one running. There is no time estimate anywhere, and that is
            deliberate: changing model changes the cost of each call by multiples, and a false
            figure is worse than none.
          </Paragraph>
        </div>
      </Block>

      <Block title="Where to look">
        <Rows
          items={[
            {
              key: "etapa",
              head: <>On the step's own screen</>,
              body: "While a step is being built, its screen carries the phase bar: which phase is running, how much each one weighs and how far it has got. That is where a build is watched, and where it is cancelled.",
            },
            {
              key: "ejecucion",
              head: <>When asking for exercises</>,
              body: "A strip appears above the results with the job in flight: how long it has been going, where it has got to and how to stop it. It opens out to show the steps, what the model is writing and the examples it was shown.",
            },
          ]}
        />
        <Paragraph>
          The <strong>technical log is not shown in the application</strong>: every line the
          pipeline writes is kept on the server, under <code>logs/</code> and inside it the
          subject's own folder. It is material to read next to a traceback, not something to
          watch while you work, and it is what to ask for when something fails.
        </Paragraph>
        <Paragraph>
          With the engine split in two halves there can be <strong>two jobs running at once</strong>,
          one on each. Every screen finds its own by the kind of job it launched, not by "the last
          one that moved", which with two lanes no longer identifies anybody.
        </Paragraph>
      </Block>

      <Block title="&quot;Queued&quot; is not &quot;running&quot;">
        <Paragraph>
          A job waiting its turn says so with "{t("queue.queuedAhead", { n: "N" })}" and{" "}
          <strong>draws no progress bar</strong>: a bar over something that has not started
          claims work is being done that nobody is doing. The same holds in the step's header
          and on the button that launched it.
        </Paragraph>
        <Paragraph>
          The number in brackets counts jobs, not minutes, and it only counts the ones on the{" "}
          <em>same engine</em>: if yours is remote and what is running is local, you are behind
          nothing at all. A queued commission is a commission made, so the form stays collapsed
          and what you are offered is to cancel it, not to launch it again.
        </Paragraph>
      </Block>

      <Alert tone="attention" title="Cancelling">
        <p>
          Cancelling cuts off at once: there is no waiting for the model to finish whatever it
          was writing, it is cut off mid-sentence and the machine is handed back. Whatever had
          already come out for good is kept.
        </p>
      </Alert>

      <Detail title="The warning ribbon on the top bar">
        <p>
          When the inference engine does not answer, or when some model has yet to be downloaded,
          a ribbon appears under the navigation bar saying exactly what breaks and what keeps
          working: what is already built can always still be read, what fails is starting new
          jobs.
        </p>
        <p>
          That ribbon is <em>everything</em> the day to day says about the machine, and that is
          deliberate: the engine's state, which models are loaded, how much VRAM they share and
          the installation's whole queue are properties of the installation rather than of your
          instance, so they live in "{t("admin.tab.engine")}", inside "{t("admin.title")}". What
          appears here is only what is stopping you working.
        </p>
      </Detail>
    </div>
  );
}

function Account() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.daily")} title={t("guide.sec.account")}>
        <p>
          Everything that is yours and is not part of the chain lives in "{t("account.title")}",
          behind the account icon at the top right — the same menu you got here from, and where
          "{t("admin.title")}" lives too. "{t("nav.myVariants")}" has a button of its own right
          beside it, because it is opened daily.
        </p>
      </SectionHead>

      <Rows
        items={[
          {
            key: "cuenta",
            head: t("tabs.account"),
            body: "Your visible name, the password, and the language you read the application in. If the installation has mail configured there is also an optional address, which is not used to sign in: only to receive the password-reset link. Without mail configured the field is not there, because nothing could be delivered to it — the link is asked for from whoever administers.",
          },
          {
            key: "workspaces",
            head: t("tabs.workspaces"),
            body: "Which subjects you are in and with what role, and where to enter another from. Access is granted by whoever administers: it is not asked for here. The one thing you can do to them is delete one of your own — one you own — and doing so tells you what goes and what stays. The name is not changed from here: it is given at creation and only an administrator changes it.",
          },
          {
            key: "variantes",
            head: t("tabs.variants"),
            body: 'Everything YOU have generated, with the commission that produced it: it can be searched, relaunched as "more like this one", and deleted. It is private: even in a subject you share with other people, each of you sees only their own.',
          },
        ]}
      />

      <Block title="The interface language">
        <Paragraph>
          Three buttons on the "{t("tabs.account")}" tab: which language the screens, this guide and the
          error messages are shown to you in. It is yours and nobody else's — not even whoever
          administers touches it — and you can change it as often as you like with no
          consequences: it translates nothing that is already written.
        </Paragraph>
        <Detail title="Three languages that are not the same one">
          <Rows
            items={[
              {
                key: "interfaz",
                head: "The interface's",
                body: "What YOU read. It lives on your account, changes whenever you want, and affects nothing else.",
              },
              {
                key: "prompts",
                head: "The prompts'",
                body: "The one the MODEL IS SPOKEN TO in. It lives on the subject, is chosen when the subject is created and never after: the relation labels end up written inside the graph and the loader indexes by them.",
              },
              {
                key: "material",
                head: "The generated material's",
                body: "The one the exercises are WRITTEN in. Nobody chooses it: it comes from the subject's context, which in turn comes from your notes.",
              },
            ]}
          />
          <p>
            They cross without trouble. You can read in English an instance whose prompts are
            Spanish and which produces exercises in Spanish, and all three decisions stay
            independent of one another.
          </p>
        </Detail>
      </Block>

      <Block title="Two things that come as a surprise">
        <Alert tone="info" title="The username cannot be changed">
          <p>
            It is what identifies everything you have done: every exercise, every evaluation
            session and every line of the log point at it. The visible name can be changed
            whenever you like.
          </p>
        </Alert>
        <Alert tone="info" title="Changing your password closes every other session">
          <p>
            All of them except this tab. It is what one wants almost every time a password is
            changed, and it is why there is no separate list of open sessions to manage.
          </p>
        </Alert>
      </Block>

      <Block title="How you get in here">
        <Paragraph>
          There is no open sign-up. An account exists because somebody passed you a{" "}
          <strong>single-use invitation link</strong> and you chose your username on opening it.
          That link <em>is</em> the invitation: it is not tied to any address, so do not leave it
          in a shared place. On opening it you also choose your password — whichever you like, or
          the one your manager suggests — and say whether you teach or study.
        </Paragraph>
        <Paragraph>
          The invitation may already carry a subject and a role inside it, or carry none: in
          that case you come in all the same and are offered to create yours. An account with no
          subject is a normal account, not a half-made one.
        </Paragraph>
      </Block>

      <Block title="Light theme, dark, or whatever the system says">
        <Paragraph>
          Three buttons in the same avatar menu. It is a property of the screen and not of the
          account: it is kept per browser, because the same person reads this on a laptop in the
          sun and on a desktop in the dark.
        </Paragraph>
      </Block>

      <Block title={t("admin.title")}>
        <Badge variant="secondary">administrators only</Badge>
        <Paragraph>
          The installation seen from outside, in five tabs: "{t("admin.tab.study")}" (the study),
          "{t("admin.tab.accounts")}" (invitations, roles, unlocks), "
          {t("admin.tab.workspaces")}" (disk usage, export, delete), "{t("admin.tab.engine")}"
          and "{t("admin.tab.config")}" (every setting, each with what it cost to measure it and
          with what it will invalidate on saving). It has a section of its own next door: "
          {t("guide.sec.admin")}".
        </Paragraph>
      </Block>

      <Block title="Closing the installation while it is being worked on">
        <Badge variant="secondary">administrators only</Badge>
        <Paragraph>
          At the very top of "{t("admin.title")}", above the tabs rather than inside any of them,
          there is a <strong>"{t("maint.title")}"</strong> switch. Closed, every other account
          sees a notice screen instead of the application — with whatever text is written there —
          and the API refuses their requests; whoever administers still gets in, which is what
          makes it possible to open it again.
        </Paragraph>
        <Paragraph>
          It is for applying changes without leaving anybody halfway through: updating the
          server, migrating the database, switching engine. While it is closed, the header
          remembers it in red on all your screens, because the real risk is not failing to
          notice: it is forgetting to reopen it.
        </Paragraph>
      </Block>
    </div>
  );
}

function Admin() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.daily")} title={t("guide.sec.admin")}>
        <p>
          The installation seen from outside: who exists, where each of them gets in, what the
          instances weigh and what the machine is doing. It lives behind the avatar, under{" "}
          <strong>"{t("admin.title")}"</strong>, and only whoever administers the installation
          sees it.
        </p>
        <p>
          Five tabs, and this section covers all of them. "{t("admin.tab.study")}" gathers what
          people have answered, in two blocks: the blind comparisons of the testing phase, with
          their tallies and their contrasts, and the forms that close each step of the
          construction phase, summarised step by step. Above both sits one filter — an account,
          a kind of account (teachers or students) and a subject — that narrows both blocks at
          once, and each block downloads as CSV exactly what it shows.
        </p>
      </SectionHead>

      <Block title={t("admin.tab.accounts")}>
        <Paragraph>
          This is where it is decided who exists and where they get in.{" "}
          <strong>There is no open sign-up</strong>, and that is a decision rather than a gap: an
          account exists because somebody opened a single-use invitation link, or because it was
          created from the command line. The link <em>is</em> the invitation and it is tied to no
          address, so it is handed over by hand and not left in a shared place. Whoever opens it
          chooses their username, their password, and whether they teach or study.
        </Paragraph>
        <Paragraph>
          The invitation may already carry a subject and a role inside it, or carry none.
          Access is granted and revoked afterwards, account by account and subject by subject,
          from this same table; there are three roles:
        </Paragraph>
        <Rows
          items={[
            { key: "viewer", head: t("role.viewer"), body: t("role.viewer.hint") },
            { key: "editor", head: t("role.editor"), body: t("role.editor.hint") },
            { key: "owner", head: t("role.owner"), body: t("role.owner.hint") },
          ]}
        />
        <Paragraph>And beside the access, every row offers four more things:</Paragraph>
        <Rows
          items={[
            {
              key: "admin",
              head: <>"{t("acc.makeAdmin")}"</>,
              body: "Whoever administers gets into every subject without being a member of any. It cannot be taken away from oneself: that is what stops the installation being left with nobody to administer it.",
            },
            {
              key: "reset",
              head: <>"{t("acc.resetLink")}"</>,
              body: "A link for setting a new password, generated here so it can be handed over by hand: the sign-in screen offers no way to ask for one. It lasts a few minutes and works once.",
            },
            {
              key: "unlock",
              head: <>"{t("acc.badge.locked")}"</>,
              body: "After several failed attempts the rate limiter closes that account's login for a while. From here it is opened without waiting, and from here every open session of theirs can be closed too.",
            },
            {
              key: "perfil",
              head: <>"{t("acc.profileLabel")}"</>,
              body: "Teacher or student. It decides the wording of the question asked when comparing proposals, and how the study groups the answers; it grants and removes no permission, which is why it is corrected here with no further ceremony.",
            },
            {
              key: "sesiones",
              head: <>"{t("acc.seeSessions")}"</>,
              body: 'Only if that account has evaluated anything: it jumps to "Evaluations" with the filter already set to them.',
            },
          ]}
        />
      </Block>

      <Block title="Closing an account: two different things">
        <Rows
          items={[
            {
              key: "desactivar",
              head: <>"{t("acc.deactivate")}"</>,
              body: "Shuts the door without deleting anything. They can no longer get in and everything of theirs stays where it was, with their name on it. It is what you do when somebody stops taking part.",
            },
            {
              key: "eliminar",
              head: <>"{t("common.delete")}"</>,
              body: "Actually deletes the account, and it cannot be undone. What it produced does NOT go with it: the generated exercises and the evaluation sessions stay, without an author. A course built on that material does not collapse because whoever generated it was removed, and the study does not lose the comparisons it counted.",
            },
          ]}
        />
        <Paragraph>
          Neither is offered on your own row, and neither is "{t("acc.makeAdmin")}": that is what
          keeps the installation from being left with nobody to administer it.
        </Paragraph>
      </Block>

      <Block title={t("admin.tab.workspaces")}>
        <Paragraph>
          Every instance of the installation with its members, its exercises and the state of its
          chain. What each one weighs is broken down by role — {t("ws.disk.raw")},{" "}
          {t("ws.disk.instance")}, {t("ws.disk.cache")} and {t("ws.disk.history")} — which is the
          only way to see that the expensive part is almost never the artifacts.
        </Paragraph>
        <Rows
          items={[
            {
              key: "cache",
              head: "Empty the cache",
              body: "It deletes only the vectors and the converted markdown, which the next job recomputes. The concept descriptions and their anchoring to your notes stay: the model wrote them by reading those, and they cost a long pass.",
            },
            {
              key: "export",
              head: "Export",
              body: "Downloads the instance exactly as the files have it — artifacts, context, approvals and curriculum — in a single JSON.",
            },
            {
              key: "borrar",
              head: "Delete",
              body: "Deleting a subject from here takes its directory tree off the disk too, the raw documents included. The dialog enumerates what disappears, and the instance's identifier has to be typed to confirm. It is not offered on the last subject left.",
            },
          ]}
        />
        <Paragraph>
          <strong>Emptying one particular step</strong> is done from its own badge in the route
          column: press the step's badge and confirm. It does not touch the history, so if you
          get it wrong it is restored from that same step's own screen.
        </Paragraph>
      </Block>

      <Block title={t("admin.tab.engine")}>
        <Paragraph>
          It is one engine with as many halves as the engine has. With a single one it is a panel
          about one machine and carries no headings at all: "{t("eng.half.local")}" with no "
          {t("eng.half.remote")}" beside it divides nothing. With the engine split, three ruled
          sections appear.
        </Paragraph>
        <Rows
          items={[
            {
              key: "local",
              head: t("eng.half.local"),
              body: (
                <>
                  {t("eng.half.localNote")}. The SSH tunnel to the GPU machine, raised and
                  stopped from here and keeping ssh's last lines of error; the resident models
                  and how they share the VRAM; and the ones on disk, with their downloads.
                </>
              ),
            },
            {
              key: "remote",
              head: t("eng.half.remote"),
              body: (
                <>
                  {t("eng.half.remoteNote")}: meters per minute and per day, and under them the
                  breakdown of what was spent per phase, which downloads as CSV.
                </>
              ),
            },
            {
              key: "process",
              head: t("eng.half.process"),
              body: (
                <>
                  {t("eng.half.processNote")}. The installation's whole queue, across every
                  subject: what is running, what is waiting, and whose each one is.
                </>
              ),
            },
          ]}
        />
        <Detail title="Three things the panel refuses to do">
          <p>
            <strong>Delete a model the configuration names.</strong> It tells you which settings
            ask for it: change those first.
          </p>
          <p>
            <strong>Put a download in the queue.</strong> Pulling a model is network and disk,
            never the GPU, so it runs beside the queue rather than behind a two-hour build.
          </p>
          <p>
            <strong>Release the GPU or invalidate a context while a job is running.</strong> That
            would be pulling the weights out from under something that is working.
          </p>
        </Detail>
      </Block>

      <Block title={t("admin.tab.config")}>
        <Paragraph>
          Every setting of the installation, each one with the measurement that justifies it
          beside it, laid out in sections with their own index and their own <strong>search
          box</strong> — which is what makes a setting findable when you only remember half a
          word of it.
        </Paragraph>
        <Paragraph>
          Each row says where its value comes from — "{t("cfg.source.default")}", "
          {t("cfg.source.file")}" or "{t("cfg.source.env")}" — and what the environment fixes
          always wins: there the control is shown disabled and says what fixes it, rather than
          letting you edit something that is about to be overwritten. Only a row that is "
          {t("cfg.source.file")}" and actually differs from the factory value offers to go back
          to it.
        </Paragraph>
        <Paragraph>
          What makes this screen useful is that it{" "}
          <strong>says what it is going to invalidate before you save</strong>, not twenty
          minutes afterwards. Touching a model's context window forces the warm contexts to be
          rebuilt; touching the embedding model re-embeds the whole concept index; touching the
          engine restarts the connection. The warnings appear under "{t("cfg.beforeSaving")}",
          beside the list of pending changes.
        </Paragraph>
        <Paragraph>
          Reasoning is not a global switch but a <strong>per-phase</strong> one, and it is drawn
          as what it is: four columns read top to bottom — the three builds and generation — each
          stop a call to the model. Under the stop's name, which model serves it; the circle says
          whether it deliberates before answering and, while it does, the selector beside it sets
          how much. Three stops carry no switch and say so with a dashed circle: the guardrail
          because its model does not reason, the exercise because each commission decides that,
          and the repair because it runs under a grammar and a grammar leaves no room to reason.
        </Paragraph>
      </Block>
    </div>
  );
}

const problems = (
  t: Translate["t"],
): { key: string; question: string; answer: ReactNode }[] => [
  {
    key: "mantenimiento",
    question: `"${t("maintenance.title")}"`,
    answer: (
      <>
        <p>
          It is not a failure: whoever administers the installation has closed it deliberately to
          apply changes. The notice says since when, and yours is where it was — artifacts,
          exercises and evaluations read exactly the same when it opens again.
        </p>
        <p>
          There is no expected time of return, and there is none because nobody knows it. "
          {t("maintenance.checkAgain")}" asks once more; the screen also does it by itself every
          few seconds.
        </p>
      </>
    ),
  },
  {
    key: "ollama",
    question: '"Ollama does not answer on …"',
    answer: (
      <>
        <p>
          The inference engine is not reachable. What is already built can still be read in full;
          what fails is starting any new job.
        </p>
        <p>
          If the GPU is on another machine, look at Administration → Engine: the SSH tunnel is
          raised and stopped from there, and it keeps the last few lines of error, which is where
          a key problem shows up.
        </p>
      </>
    ),
  },
  {
    key: "cerebras",
    question: `"${t("cere.refusing")}"`,
    answer: (
      <>
        <p>
          Not a failure either. The remote engine works under two quotas — one per minute and one
          per day — and the notice says which one ran out and how long until it frees up. The
          minute waits itself out with nothing for you to do; the day does not, because leaving a
          job hanging for hours with no explanation is worse than refusing it.
        </p>
        <p>
          There are three ways forward: wait, switch the engine to "ollama", or raise the ceiling
          if the account really does allow more. All three are done in Administration → Engine,
          where the settings sit in the right-hand column beside the meters that explain them.
        </p>
        <p>
          There is a third case that is not about a spent quota but about size: a call needing
          more tokens than the whole window holds is refused at once, because no amount of
          waiting makes it fit.
        </p>
        <p>
          What it <strong>does not</strong> do is fall back to the local engine on its own. That
          would silently change which engine produced an artifact, and that has to be something
          one can state.
        </p>
      </>
    ),
  },
  {
    key: "modelo",
    question: `A model shows as "${t("model.notInstalled")}"`,
    answer: (
      <p>
        Only the jobs that use that model fail; the rest of the chain works. It is downloaded
        from Administration → Engine, and the download runs beside the queue rather than inside
        it: it does not have to wait for a two-hour build to finish.
      </p>
    ),
  },
  {
    key: "obsoleto",
    question: `A step says "${t(STATUS.stale.labelKey)}"`,
    answer: (
      <p>
        Something it depends on changed after you closed it. Open it, check that it still holds
        — or correct it — and close it again by carrying on to the next one. Meanwhile, the
        steps that depend on it stay blocked.
      </p>
    ),
  },
  {
    key: "bloqueado",
    question: `A step says "${t(STATUS.blocked.labelKey)}"`,
    answer: (
      <p>
        It is not "it is not done", it is "it is not your turn yet": something it depends on is
        not closed. The screen itself says which, with a link.
      </p>
    ),
  },
  {
    key: "solo-lectura",
    question: "It will not let me change anything",
    answer: (
      <>
        <p>
          These are two different situations and they are left by different doors. If the step is{" "}
          <strong>open</strong>, what is happening is that you are <em>looking</em> at it: every
          step opens read-only, and the editing is unlocked with "{t("stage.curate.start")}", at
          the foot of the screen. Nothing is wrong — you simply have not asked to correct yet.
        </p>
        <p>
          If the step is <strong>closed</strong>, the door is the same: "
          {t("stage.curate.start")}" at the foot of the screen. What was taken as good is the
          file exactly as it stands, so the first change you save opens it again — deleting and
          rebuilding nothing — and closing it again is carrying on to the next step once more.
        </p>
        <p>
          A concept's description can be corrected with the step closed: it lives in a file of its
          own and expires nothing.
        </p>
      </>
    ),
  },
  {
    key: "boton",
    question: "The build button is off",
    answer: (
      <>
        <p>
          Hover over it: it says why. There are five reasons, checked in this order — your
          permission on this subject is read-only; the previous step is not closed; the Step{" "}
          {stepNumber(0)} origin has no documents in it; the engine does not answer; or this same
          build is already queued. If it is the one about material, the link on the notice itself
          takes you to upload it.
        </p>
        <p>
          Another job running is not a reason: the build queues behind it, and the button says
          how many it goes behind.
        </p>
      </>
    ),
  },
  {
    key: "sin-concepto",
    question: "There are exercises of mine with no concept at all",
    answer: (
      <p>
        That is normal on the first pass. Press "{t("stage.curate.start")}" and use "
        {t("bank.retagUntagged", { n: "N" })}": it runs only over those, never over all of them.
        And repeating makes sense, because the matching improves with every well-tagged exercise.
        If one keeps resisting, set its concept by hand.
      </p>
    ),
  },
  {
    key: "bloqueadas",
    question: "My additional instructions come back blocked",
    answer: (
      <p>
        The notice says which of the two filters it was. If it is admissibility, it names the
        control above that already decides that: change it there instead of asking for it in
        writing. If it is the guardrail, it says under which criterion.
      </p>
    ),
  },
  {
    key: "horas",
    question: "It has been hours and I do not know if it is progressing",
    answer: (
      <p>
        Building the graph is the most expensive job on the route. On its own screen, the
        phase bar says which one it is on: the section that moves is the one running, and
        underneath goes the name of what is being done right now. You can close the tab and come
        back later.
      </p>
    ),
  },
];

function Troubleshooting() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.daily")} title={t("guide.sec.troubleshooting")}>
        <p>
          Almost nothing that appears here breaks anything: what is already built can always
          still be read. What fails is starting new work.
        </p>
      </SectionHead>

      <div className="space-y-2">
        {problems(t).map((problem) => (
          <Detail key={problem.key} title={problem.question}>
            {problem.answer}
          </Detail>
        ))}
      </div>

      <Alert tone="info" title="General rule: hover over whatever is switched off">
        <p>
          No disabled control stays silent in this application. The build button decides in one
          single place every reason not to offer itself — read-only permission, the previous step
          not closed, the Step {stepNumber(0)} origin empty, the engine not answering, that same
          build already queued — and says them in its own tooltip. Another job running is not on
          the list: that resolves itself by waiting your turn, and the button does the counting.
        </p>
      </Alert>
    </div>
  );
}

export const BODIES: Record<string, () => ReactNode> = {
  start: Start,
  workspace: Workspace,
  raw: Raw,
  profile: Profile,
  graph: Graph,
  bank: Bank,
  generate: Generate,
  evaluate: Evaluate,
  runs: Runs,
  account: Account,
  admin: Admin,
  troubleshooting: Troubleshooting,
};
