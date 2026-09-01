import { Check, Play, Scale, type LucideIcon } from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Alert, PhaseBar, Skeleton } from "@/components/ui/misc";
import { StatusMark } from "@/components/ui/status";
import { STATUS, type StatusKey } from "@/lib/status";
import { ARM_META } from "@/study/arms";
import { STEPS } from "@/lib/steps";
import { useT, type Translate } from "@/lib/i18n";
import { useBuildPhases } from "@/state/queries";
import { Block, Detail, Facts, Paragraph, Rows, SectionHead, Steps } from "../blocks";

const STATE_ORDER: StatusKey[] = ["approved", "draft", "stale", "building", "missing", "blocked"];

const STATE_HINTS: Record<StatusKey, string> = {
  approved: "Closed and counted as good. It is what unlocks the next stage.",
  draft: "Built but not reviewed. It can be edited; it does not count yet.",
  stale:
    "Something it depends on changed after it was approved. It has to be rebuilt or approved again.",
  building:
    "The screen says which of three things is happening: it is being built for the first time and there is nothing to replace; it is being worked over what is already there, which stays saved and merely stops being shown; or the job is still queued and has not started, and then there is no bar.",
  missing: "It does not exist yet. The screen shows the header and a single button: build.",
  blocked:
    'Not "it is not done", but "it is not your turn yet": something it depends on is unapproved.',
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

function Pill({ icon: Icon, label, tone }: { icon: LucideIcon; label: string; tone?: "study" }) {
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
          topic in the abstract: it starts from the three steps you describe your subject with, and
          produces variants that respect what the student has already seen and what they have
          not.
        </p>
      </SectionHead>

      <Block title="The route, at a glance">
        {/* Es la barra de arriba, dibujada aquí: cuatro pasos numerados y las dos cosas que
            se hacen con lo que producen. El raíl que había antes se fue con el panel — lo
            que codificaba, la dependencia entre etapas, lo dicen ahora los números. */}
        <div className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-card p-4 sm:p-6">
          {STEPS.map((step, index) => (
            <div key={step.path} className="flex items-center gap-2">
              <span className="nums flex size-6 shrink-0 items-center justify-center bg-primary font-condensed text-small font-semibold text-primary-foreground">
                {index + 1}
              </span>
              <span className="text-body font-medium">{t(step.labelKey)}</span>
            </div>
          ))}
          <span aria-hidden className="mx-1 h-6 w-px bg-border" />
          <Pill icon={Play} label={t("nav.create")} />
          <Pill icon={Scale} label={t("nav.compare")} tone="study" />
        </div>
        <Paragraph>
          It is exactly the bar above. The four steps are done in that order and each carries a word underneath saying where you are: <em>done</em>, <em>your turn</em> or <em>later</em>. The two pills on the right are not steps: they are what you do with what the steps produce, and they open once all four are behind you.
        </Paragraph>
      </Block>

      <Rows
        items={[
          {
            key: "perfil",
            head: "Exemplars profile",
            body: "What an exercise is here: its fields, their types, and the guidance the model follows.",
          },
          {
            key: "grafo",
            head: "Knowledge graph",
            body: "The vocabulary: concepts, domains and the relations between them.",
          },
          {
            key: "banco",
            head: "Exemplars bank",
            body: "Real exercises from your subject, already tagged with concepts from the graph.",
          },
        ]}
      />

      <Alert tone="info" title="You start at the profile, not at the graph">
        <p>
          A graph can be built with nothing else, but its which concepts work as a label review needs the profile{" "}
          <em>approved</em>. Starting at the graph is starting at a stage you cannot finish.
        </p>
      </Alert>

      <Block title="The first half hour">
        <Steps
          items={[
            <>
              Get yourself into a <strong>workspace</strong>. If you have none yet, the panel
              offers to create yours; if you have several, you switch in the selector at the top
              left. Everything else lives inside one.
            </>,
            <>
              From <strong>"{t("dash.rawData")}"</strong>, in the navigation, upload the
              material: the documents with example exercises, and the subject's notes.
            </>,
            <>
              On that same screen, launch the <strong>transcription</strong> of each origin. It
              is not required — skip it and every build transcribes its own along the way — but
              it is the mechanical work that opens all three: done once, it stops being paid for
              at the start of each one. It is also where you can read a page that came out badly
              and correct it by hand.
            </>,
            <>
              Build the <strong>profile</strong>, review it field by field and approve it.
            </>,
            <>
              Launch the <strong>graph</strong>. It is the most expensive job in the chain: you
              can close the tab, the server carries on.
            </>,
            <>
              Review the graph's <strong>which concepts work as a label</strong> and its{" "}
              <strong>descriptions</strong>, and approve it.
            </>,
            <>
              Extract the <strong>bank</strong>, go over the exercises left with no concept, and
              approve it.
            </>,
            <>
              With the three approved, "{t("nav.generate")}" and "{t("nav.evaluate")}" open up.
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

      <Detail title="Why does every stage have to be approved?">
        <p>
          What gets approved is the <em>file's hash</em>. While a stage is approved, its screen
          offers no control that rewrites the artifact: under the "{t("stage.reopen")}" button it
          says so in as many words — "{t("stage.locked")}" — and that button is the only way
          back. Approving is what unlocks the next stage and, with all three, generation.
        </p>
        <p>
          What does <em>not</em> rewrite the artifact — the concept descriptions and the
          curriculum — stays available with the stage approved.
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
          A <strong>workspace</strong> is a complete instance: its raw material, its three
          artifacts, its cache and its curriculum. Two subjects are two workspaces. Two very
          different exercise formats for the same subject are too.
        </p>
      </SectionHead>

      <Facts
        items={[
          { label: "Where you switch", value: "The selector at the top left, next to the mark." },
          { label: "Who can create one", value: "Any account, and it becomes its owner." },
          {
            label: "If you have none",
            value: "The panel offers to create it. There is no default one.",
          },
          {
            label: "What travels with you",
            value: "Nothing. Each workspace has its own, cache included.",
          },
          {
            label: "What is decided on creation",
            value: "The prompt language. It cannot be changed later.",
          },
        ]}
      />

      <Block title="Coming in with none is normal">
        <Paragraph>
          There is no initial workspace for whoever has no other: a freshly created account, or
          one that has not been given access to anything yet, comes in and finds the{" "}
          <strong>Panel</strong> asking it to create its own. The subject's name is enough. Both
          ways out are equally valid: create it yourself and be its owner, or wait for whoever
          administers to give you access to one that already exists.
        </Paragraph>
        <Paragraph>
          Meanwhile the application is not blocked: this guide, "My profile" and — if you
          administer the installation — "Administration" work with no workspace at all. What
          waits is everything that reads an instance: the three stages, "Generate" and
          "Evaluate".
        </Paragraph>
      </Block>

      <Block title="The prompt language is chosen when the workspace is created">
        <Paragraph>
          Creating a workspace is where you choose which language the model is spoken to in
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

      <Block title="One tab, one workspace">
        <Paragraph>
          The active workspace is kept on your account and survives signing out; the one you are{" "}
          <em>looking at</em> is kept by the tab. You can have two subjects open in two tabs of
          the same browser without them treading on each other. Switching workspace empties the
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
          {t("tabs.workspaces")}", below each workspace, with the three loose facts that sit
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
          When asking for an exercise you can say which concepts the class has already seen.
          That is what bounds the scaffolding: an exercise may lean on a covered concept; it may
          not depend on one that has not been taught yet. It is chosen <em>in the commission</em>,
          under "Settings", and holds for that batch — it is not stored on the subject.
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
          The documents everything else comes out of. They have a screen of their own —{" "}
          <strong>"{t("nav.rawData")}"</strong> in the navigation, at{" "}
          <code className="font-mono text-small">/raw</code> — and a pill of their own, ahead
          of the three stages and separated from them by a rule: the raw material feeds the
          chain without being a step of it. It writes no artifact, nobody approves it, and that
          is why it is not on the rail.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "What it produces",
            value: "No artifact: each document's pages turned into markdown, saved one by one.",
          },
          {
            label: "What it costs",
            value: "One call to the model per page, in both origins alike.",
          },
          {
            label: "What it unlocks",
            value: "Nothing, and that is deliberate: it brings forward work the builds would do anyway.",
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
          Each card carries under its title the stage it feeds, with the short names from the bar
          at the top: "{t("nav.graph")}" for the notes, "{t("nav.profile")}" and "
          {t("nav.bank")}" for the exemplars. An empty origin does not draw an empty list: the
          whole card becomes the area to drop files into, which is the only thing worth doing
          there.
        </Paragraph>
      </Block>

      <Alert tone="info" title="Transcribing brings work forward; it is never a requirement">
        <p>
          Turning the documents into markdown is the first thing <em>every</em> build does, and
          it is mechanical work: doing it here once takes it out of the start of all three. Build
          without having transcribed and the build does it on its own, with nothing stopping you
          — <strong>nothing is ever refused for want of a transcription</strong>.
        </p>
        <p>
          Which is why, while documents are still untranscribed, the "{t("nav.rawData")}" pill
          carries a dot and the three stages on the bar at the top are <em>dimmed</em>, saying
          why on hover. Dimmed is not disabled: they stay clickable and they still build. It
          says where to start, it does not lock anything.
        </p>
      </Alert>

      <Block title="Two buttons, and they do not have the same reach">
        <Rows
          items={[
            {
              key: "todo",
              head: <>"{t("transcribe.startAll")}"</>,
              body: "In the notice at the top of the screen. It launches in one go whichever origins have something to do, and it is the normal route.",
            },
          ]}
        />
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
              body: "It was transcribed, but something it depended on has changed. The row says what: the document itself, the transcription route, the model, the render resolution, the OCR, or the prompt.",
            },
            {
              key: "failed",
              head: <Badge variant="danger">{t("transcribe.failedCount", { n: "N" })}</Badge>,
              body: "It sits beside the state rather than in its place: a document can be transcribed and up to date and still hold pages the model could not read. That badge is the only sign that text is missing there, and it is fixed by opening the document.",
            },
          ]}
        />
        <Paragraph>
          The reason sits on the document's own row rather than hidden inside a tally: "2
          expired" reports the state and keeps quiet about the very half you act on. A state
          with no reason is not a state, and what is underneath is a list of pages the next build
          was about to redo in silence.
        </Paragraph>
      </Block>

      <Alert tone="settled" title="Stopping it loses nothing">
        <p>
          Pages are written document by document, so a cancelled transcription keeps everything
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
            While an origin is being transcribed you can review and correct the documents that
            have already come out. The only one that will not open is the one being rewritten at
            that instant: its row says so with an activity indicator and with "
            {t("transcribe.transcribing")}" in place of its state.
          </p>
        </Detail>
      </Block>

      <Detail title="Both origins take the same route, and it costs what it costs">
        <p>
          Corpus and exemplars are transcribed by the same algorithm: each page is drawn and the
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
          The consequence shows in the phase bar explained in "{t("guide.sec.runs")}": the
          reading the notes is now the widest section of the graph build. Taking it out of there,
          and being able to watch it while it happens, is exactly what this screen exists for.
        </p>
      </Detail>
    </div>
  );
}

/**
 * How each of the three steps ends. The same block in all three sections because it is the
 * same task: the only difference is the questions, which the server writes.
 */
function Verdict() {
  return (
    <Block title="How this step is closed">
      <Paragraph>
        To the right of what you have built there is a short questionnaire on how it came
        out. The questions change with the step, but two are always the same — how much you
        would have to correct before you could use it, and 1 to 5 overall — and those are the
        ones that let one step be compared with another.
      </Paragraph>
      <Steps
        items={[
          <>
            Look at what is on the left. You do not have to read all of it: what is being
            asked is whether it sounds like your subject.
          </>,
          <>
            Answer and save. You can leave it half done and come back: half an answer is a
            datum too.
          </>,
          <>
            Saving brings up the next step. Correcting the thing on the left by hand stays
            available throughout, before and after.
          </>,
        ]}
      />
      <Detail title="What exactly is kept">
        <p>
          Your answers, with the <em>particular version</em> you judged. If you build the
          step again and judge it again, nothing is overwritten: they are two data, because
          "it came out badly" and "I redid it and it came out well" are two different things.
          Answering again about the same one does correct your earlier answer.
        </p>
        <p>
          It is the only thing we ask in return for using this, and it is what is being
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
      <SectionHead eyebrow={`${t("guide.group.prepare")} · stage 1`} title={t("guide.sec.profile")}>
        <p>
          It defines what an exercise is: its fields, their types, and the guidance the model follows
          when extracting and when generating them. It is the piece that instantiates the use
          case — changing profile is changing the kind of material, not the subject.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "What it produces",
            value: <code className="font-mono text-small">exemplars_profile.json</code>,
          },
          {
            label: "What it costs",
            value: "One long pass over a sample of your exercises, not over all of them.",
          },
          {
            label: "What it unlocks",
            value: "The bank's extraction and the graph's which concepts work as a label review.",
          },
        ]}
      />

      <Block title="How it is done">
        <Steps
          items={[
            <>
              Upload one or more documents with real exercises from the subject into the raw
              exemplars slot. With no material, the build button is off and says why.
            </>,
            <>
              Press "Build". What comes out is a <strong>draft</strong>, not a final result.
            </>,
            <>
              Go over each <strong>exercise type</strong>: its description, its{" "}
              <strong>difficulty level</strong> and, inside it, each field — its name, its type,
              whether it is required and what it holds.
            </>,
            <>
              Go over each exercise type's <strong>"{t("modality.rules")}"</strong>: they are the only
              thing the profile tells the generator about the <em>shape</em> of an exercise.
            </>,
            <>Approve. The stage closes and the screen stops offering anything that rewrites it.</>,
          ]}
        />
        <Paragraph>
          The profile is edited through the form alone: there is no raw-JSON tab, and no save
          button either. What writes the changes is <strong>"Approve"</strong>: it saves first
          and closes the stage after, in one press. While something is unsaved the bar says so,
          and at the very top is the notice saying whether the profile <em>loads</em> — while it
          does not, approving is disabled, which is what keeps the instance from being left with
          a broken schema.
        </Paragraph>
      </Block>

      <Block title="Modalities, and why they show up everywhere else">
        <Paragraph>{t("modality.whatAre.body")}</Paragraph>
        <Paragraph>
          Which is why the exercise type comes back later as a column and a filter in the bank, and as
          the first question on the generation form. A profile with a single exercise type draws
          neither: a dropdown with one option chooses nothing.
        </Paragraph>
      </Block>

      <Block title="The difficulty level, which every type carries">
        <Paragraph>
          Every exercise type carries a <strong>difficulty level</strong>, and it is not one more
          field: it is not added, not removed and not renamed. It is edited at the top, in "
          {t("modality.identity")}", right below the type's description.
        </Paragraph>
        <Paragraph>
          The <strong>three levels are the same in every type</strong>. That is what makes
          "advanced" mean the same thing in a multiple-choice question and in a programming
          exercise, what lets the bank's column be read at a glance and what lets the list be
          ordered by it. What changes from one type to the next is <em>what puts</em> an exercise
          on each level, and that is the only part you write.
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
              key: "topic",
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

      <Block title="What a field has">
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
              body: "The one carrying the statement. It is the one turned into a vector to match against concepts, and only a text field can be it.",
            },
          ]}
        />
      </Block>

      <Alert tone="danger" title="Touching it after extracting the bank invalidates the bank">
        <p>
          The bank's exercises were extracted against the previous schema. If you change the fields,
          the bank goes to "Stale" and has to be extracted again.
        </p>
      </Alert>

      <Detail title="The draft is not stable, and it is worth knowing">
        <p>
          The profile is inferred from a sample of your exercises, and it has produced{" "}
          <em>different</em> field sets across two passes over the same material. Treat it as a
          starting point: the version you approve is yours, not its.
        </p>
        <p>If you rebuild it, compare before replacing the one you already had.</p>
      </Detail>
      <Verdict />
    </div>
  );
}

function Graph() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={`${t("guide.group.prepare")} · stage 2`} title={t("guide.sec.graph")}>
        <p>
          The system's vocabulary. Everything tagged and generated afterwards comes from here:
          neither the model nor you can use a concept that is not in the graph.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "What it produces",
            value: <code className="font-mono text-small">knowledge_graph.json</code>,
          },
          {
            label: "What it costs",
            value:
              "It is the most expensive job in the chain: one call per page of your notes, and several that reason over the whole inventory.",
          },
          {
            label: "What it unlocks",
            value: "The bank's tagging, the curriculum and generation.",
          },
        ]}
      />

      <Block title="A list, with a map under it">
        <Paragraph>
          What you see first is the syllabus: the units in teaching order, folded. Open them, or
          search and the ones with results open on their own. Every row carries the topic and
          whether it <strong>works as a label</strong>; clicking it opens its card over the page,
          which is where the name, the unit, the description and the relations are corrected.
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

      <Block title="After building, three things to look at">
        <Steps
          items={[
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                Taggability
                <Badge variant="attention">needs the profile approved</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                Which concepts work as a <em>label</em>. The ones that would fit any exercise at all
                — "coding", "design" — are marked as NOT working as a label: they still exist and still
                work through their relations, they simply stop being able to be what an exercise
                is about. When in doubt, exclude: a vague label pollutes the whole bank.
              </p>
            </>,
            <>
              <p className="font-medium">Descriptions</p>
              <p className="text-small text-muted-foreground">
                The prose describing each concept, written against the paragraphs of your notes
                it came from. <strong>It is the text matched against, not the name.</strong> They
                are written on their own when indexing; the tab is for reading them and
                correcting the ones that do not say what you would say.
              </p>
            </>,
            <>
              <p className="font-medium">Curation by hand</p>
              <p className="text-small text-muted-foreground">
                Renaming what came out crooked, deleting what is not a concept of the subject,
                and fixing relations. Renaming carries the anchoring to your notes with it; deleting
                lets it go.
              </p>
            </>,
          ]}
        />
      </Block>

      <div className="space-y-2">
        <Detail title="Why matching is not done on the concept's name">
          <p>
            A name is a two-word label and says nothing about what is practised by using it. What
            is turned into a vector is the <em>description</em>, fused with the centre of the
            bank exercises already carrying that concept.
          </p>
          <p>
            That is why a badly written description is paid for on every tagging and every
            generation, and why they are worth reading.
          </p>
        </Detail>

        <Detail title="Prerequisites: what is assumed known and what is forbidden">
          <p>
            Around the concepts you ask for, the system derives two lists from the graph and puts
            them into the prompt:
          </p>
          <Rows
            items={[
              {
                key: "sabido",
                head: <span className="text-settled">Assumed known</span>,
                body: "Prerequisites that are also in the curriculum. The exercise may lean on them, but must not turn them into the difficulty. They travel with their description, not as a bare name.",
              },
              {
                key: "prohibido",
                head: <span className="text-destructive">Forbidden</span>,
                body: "What comes after the target and has not been taught yet. It must not appear.",
              },
            ]}
          />
          <p>
            Both lists walk the whole graph, not one hop: they are transitive closures bounded by
            the curriculum. On the generation screen they are drawn before launching, so you can
            see exactly what the model is going to work with.
          </p>
        </Detail>
      </div>
      <Verdict />
    </div>
  );
}

function Bank() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={`${t("guide.group.prepare")} · stage 3`} title={t("guide.sec.bank")}>
        <p>
          The exercises extracted from your documents and tagged with concepts from the graph. They
          are the examples that accompany every generation: this is where "here is how exercises
          are written in this subject" comes from, for the model to imitate.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "What it produces",
            value: <code className="font-mono text-small">exemplars_bank.json</code>,
          },
          {
            label: "What it costs",
            value: "It grows with the number of documents: all of them are walked, one after another.",
          },
          {
            label: "It is saved",
            value: "After each document. Cancelling loses nothing already extracted.",
          },
        ]}
      />

      <Alert tone="info" title="Extracting and tagging are one single job">
        <p>
          Each document is tagged as it comes out of the extractor, so by the time extraction
          finishes the bank is already tagged: there is no intermediate step to launch. What is
          left is correcting what came out wrong, and there are three separate controls for that.
        </p>
      </Alert>

      <Block title="The strip of meters says two different things">
        <Rows
          items={[
            {
              key: "etiquetados",
              head: t("bank.taggedItems"),
              body: "How many exercises of the bank carry at least one concept. It is the correcting still ahead of you, and it has beside it the two controls that act on that very number. It is only drawn while some are missing: with the whole bank tagged there is nothing to look at there.",
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
          <em>exercises with no concept</em>, the other <em>concepts with no exercise</em>. The whole
          bank can be tagged while half the syllabus has not a single example to imitate.
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
              Then the ones carrying <strong>a single concept</strong>, or one that does not
              fit: the concepts column reads at a glance, and that is where the matching goes
              wrong without saying so.
            </>,
            <>
              Correct the <strong>primary concept</strong> by hand where needed: it is the one
              that decides what that exercise is compared against afterwards.
            </>,
          ]}
        />
      </Block>

      <Block title="The three ways to re-tag, which do not do the same thing">
        <Rows
          items={[
            {
              key: "pendientes",
              head: <>"{t("bank.retagUntagged", { n: "N" })}"</>,
              body: "With no selection: it runs over exactly the exercises left with no concept, never over the whole bank. It sits in the strip of meters, next to the number it acts on.",
            },
            {
              key: "todo",
              head: <>"{t("bank.retagAll")}"</>,
              body: "The whole bank, from scratch. It overwrites the current tags, the ones you corrected by hand included, which is why it asks for confirmation before it runs.",
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
          statement's text or by id, the <strong>exercise type</strong> — the ones your profile
          declares, each with how many exercises it has across the whole bank — the{" "}
          <strong>source document</strong>, the <strong>level</strong> — the three rungs, each
          with its own count — and, at the end of the row, the{" "}
          <strong>"{t("bank.untagged")}"</strong> toggle. If your profile declares a single
          exercise type, that dropdown does not appear: a menu with one option filters nothing.
        </Paragraph>
        <Paragraph>
          There is no order control: the table runs in the order the exercises were extracted
          in, which is the order of their ids. The level is <em>filtered</em> and not sorted,
          because with three rungs sorting only groups, and the question people actually ask is
          «show me the advanced ones».
        </Paragraph>
        <Paragraph>
          Filtering by exercise type moved nothing about tagging by concept, which is the heart of the
          bank: the meters, "{t("bank.seeUntagged", { n: "N" })}", the three re-tag buttons, the
          concepts column and the editor's primary-concept picker are all exactly where they
          were.
        </Paragraph>
      </Block>

      <Detail title="Retrying makes sense: the index improves between passes">
        <p>
          Every well-tagged exercise pushes its concept's centre towards where it really is, so one
          pass's index is consumed by the next. An exercise that finds no concept today may find one
          tomorrow without your having touched anything.
        </p>
        <p>
          That is why rejected ones are tried again on every pass, instead of being marked as
          impossible.
        </p>
      </Detail>
      <Verdict />
    </div>
  );
}

function Generate() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow={t("guide.group.use")} title={t("guide.sec.generate")}>
        <p>
          One commission, one batch of variants. The form is an accordion: it is answered top to
          bottom and each question collapses to a single line once answered, so changing the
          concepts again costs one click and no scrolling.
        </p>
        <p>
          There are <strong>up to five</strong> questions, not always five: two of them appear
          only if your instance needs them, and the numbering counts the ones that get drawn.
        </p>
      </SectionHead>

      <Block title="The questions, in the order they are asked">
        <Steps
          items={[
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {t("form.type.title")}
                <Badge variant="outline">only with several exercise types</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                {t("form.type.hint")} If your profile declares a single one, this question is not
                asked.
              </p>
            </>,
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {t("form.taught.title")}
                <Badge variant="outline">{t("common.optional")}</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                What the class has already covered, for <em>this</em> commission, and it
                arrives <strong>off</strong>: no restriction. Turning it on lets you pick the
                covered concepts by hand, and they hold for this run alone — nothing is
                stored on the subject. {t("form.taught.hint")}
              </p>
            </>,
            <>
              <p className="font-medium">{t("form.practise.title")}</p>
              <p className="text-small text-muted-foreground">
                {t("form.practise.hint")} Only concepts that <strong>work as a label</strong> are
                offered: this is where you choose what the exercise is about, and a generic
                concept is no use for that.
              </p>
            </>,
            <>
              <p className="font-medium">{t("form.difficulty.title")}</p>
              <p className="text-small text-muted-foreground">
                The three levels of the type you chose, each with the criterion you wrote in
                Step 2 underneath, plus «{t("decision.any")}» to leave it unpinned. It is the
                same ladder in every type, so asking for «advanced» means the same thing here
                as it does in the bank's column.
              </p>
            </>,
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {t("form.decisions.titleMany")}
                <Badge variant="outline">only if the profile leaves something to you</Badge>
              </p>
              <p className="text-small text-muted-foreground">{t("form.decisions.hint")}</p>
            </>,
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                {t("form.instructions.title")}
                <Badge variant="outline">{t("common.optional")}</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                Free text for what none of the controls above decides, capped at 600 characters
                which the box itself counts down. It goes through two filters before entering the
                prompt.
              </p>
            </>,
          ]}
        />
      </Block>

      <Block title="Before launching, what the graph is about to tell the model">
        <Paragraph>
          Under the chosen concepts, "{t("form.graphSays")}" appears with the two lists the
          prompt will carry: "{t("form.given")}" and "{t("form.forbidden")}". They come out of
          the graph and of this question's curriculum, and they are visible <em>before</em>{" "}
          anything is spent.
        </Paragraph>
        <Paragraph>
          The same box warns about <strong>topics with no example</strong>: if a chosen concept has no
          exemplar in the bank — or none of the exercise type asked for — the batch is generated with
          no example to imitate and quality usually drops. A switch hides the concepts with no
          exemplars from the list; turning it off is what lets you ask for them knowingly.
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
              body: "It decides whether what you are asking for belongs to this field or to something you already decided above: the concepts, the exercise type, the exercise's fields, or the subject itself. If it does, it tells you which control decides it.",
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
          by whoever administers the installation too. The model is stored with every variant,
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
          text as it is written, the bank exemplars the model was given, and the technical
          details of the call. It opens by itself while the job runs and closes when it ends,
          unless you touch it.
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
                  Every variant is saved into "{t("menu.savedVariants")}"{" "}
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
                  What the system can check without judging the exercise: whether it names
                  something not yet taught, whether it looks too much like an example or another
                  one in the batch, and whether the tagger recognises it as the concept you asked
                  for. The first two make the generator <em>try again</em> before handing you the
                  exercise; what arrives flagged is what still did not come out clean, and at that
                  point <strong>it is a signal for whoever reads, not a rejection</strong>.
                </>
              ),
            },
            {
              key: "reintentada",
              head: <Badge variant="outline">{t("result.retried", { n: "N" })}</Badge>,
              body: "How many times the call had to be repeated because of those two signals. It does not say the variant is bad: it says what it cost.",
            },
          ]}
        />
        <Paragraph>
          A variant with nothing to flag says so just as plainly: "{t("result.noFlags")}".
        </Paragraph>
      </Block>

      <Block title="And afterwards">
        <Rows
          items={[
            {
              key: "cambiar",
              head: <>"{t("generate.changeCommission")}"</>,
              body: 'Reopens the form with everything filled in and leaves the results in view until you launch another batch. Reopening also brings up "Start over", for when what you want is a different commission rather than a variation on the same one.',
            },
            {
              key: "otras",
              head: <>"{t("generate.anotherN", { n: "N" })}"</>,
              body: 'Repeats the same commission, new batch. With a single exercise the label reads "Generate another".',
            },
            {
              key: "exportar",
              head: <>"{t("generate.export")}"</>,
              body: "A menu with three ways out for the whole batch: copy the JSON, download it, or download it as Markdown.",
            },
            {
              key: "como-esta",
              head: <>"{t("generations.moreLikeThis")}"</>,
              body: 'It is in "My variants" and recovers the commission of one particular variant, even from another day.',
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
          You ask for the comparison and you judge it: you pick the topic you want the
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
            value: "The four steps behind you: the three versions are written from your subject.",
          },
        ]}
      />

      <Block title="The two tabs">
        <Rows
          items={[
            {
              key: "encargo",
              head: t("eval.tab.compose"),
              body: 'Where the screen opens. You pick the topic and the type of exercise you want: the same "Create exercises" form, without two controls — how many exercises, and whether the model reasons — because a comparison is always one per version.',
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
            <>The three proposals appear, unlabelled and in an order that is yours alone.</>,
            <>
              <strong>You answer one question per card</strong>: whether you would set it in
              class — or, if you are a student, whether it would be useful to practise with. One
              click, first impression, no dwelling on it.
            </>,
            <>
              <strong>You choose one</strong>. The button does not activate until you have
              answered all three, and you can always say that none of them convinces you.
            </>,
            <>
              Only then is it revealed which architecture wrote each one, with what you answered
              about each card beside it.
            </>,
            <>
              If you feel like it, you rate the system's one on four scales. It is{" "}
              <strong>optional</strong>: the comparison was already recorded when you chose.
            </>,
            <>
              Below it, "{t("eval.nextInQueue", { pending: "N" })}" jumps straight to the next
              one not yet judged, without going through the list.
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
          back. What is being done is watched from the{" "}
          <strong>{t("nav.dashboard")}</strong> and from the run drawer.
        </p>
      </SectionHead>

      <Block title="The six states">
        <Paragraph>
          No state is told apart by colour alone: each has its own shape, and that shape is the
          same on the bar at the top, on the panel's cards and in each stage's header.
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
          workspace's own folder. It is material to read next to a traceback, not something to
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
          claims work is being done that nobody is doing. The same holds on the panel's card, in
          the stage's header and on the button that launched it.
        </Paragraph>
        <Paragraph>
          The number in brackets counts jobs, not minutes, and it only counts the ones on the{" "}
          <em>same engine</em>: if yours is remote and what is running is local, you are behind
          nothing at all. A queued commission is a commission made, so the form stays collapsed
          and what you are offered is to cancel it, not to launch it again.
        </Paragraph>
      </Block>

      <Alert tone="attention" title="Cancelling and rebuilding">
        <p>
          Cancelling does not cut off mid-call: it stops at the next safe point, so it can take a
          while. And a rebuild <em>hides</em> the artifact it is about to replace without
          deleting it — the builder writes at the end — which is why cancelling brings it
          straight back, untouched and with no restore step.
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
            body: "Which workspaces you are in and with what role, and where to enter another from. Access is granted by whoever administers: it is not asked for here. The one thing you can do to them is delete one of your own — one you own — and doing so tells you what goes and what stays. The name is not changed from here: it is given at creation and only an administrator changes it.",
          },
          {
            key: "variantes",
            head: t("tabs.variants"),
            body: 'Everything you have generated, with the commission that produced it: it can be searched, narrowed to yours or widened to the whole workspace, relaunched as "more like this one", and deleted.',
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
                body: "The one the MODEL IS SPOKEN TO in. It lives on the workspace, is chosen when the workspace is created and never after: the relation labels end up written inside the graph and the loader indexes by them.",
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

      <Block title="A variant can go back into the bank">
        <Paragraph>
          In "{t("tabs.variants")}", every variant offers "{t("generations.promote")}":{" "}
          {t("generations.promoteHint")}
        </Paragraph>
        <Paragraph>
          It is how something that came out well stops being a loose result and becomes an
          example the model imitates next time. What to keep in mind is the second half of that
          sentence: the bank goes stale and has to be approved again, so it is worth promoting
          several at once rather than one at a time.
        </Paragraph>
      </Block>

      <Block title="Two things that come as a surprise">
        <Alert tone="info" title="The username cannot be changed">
          <p>
            It is what identifies everything you have done: every variant, every evaluation
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
          The invitation may already carry a workspace and a role inside it, or carry none: in
          that case you come in all the same and the panel offers to create yours. An account
          with no workspace is a normal account, not a half-made one.
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
          Five tabs, and this section covers all of them. "{t("admin.tab.study")}" gathers
          what people answered: the comparisons they judged and the verdicts they left at the
          end of each step.
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
          The invitation may already carry a workspace and a role inside it, or carry none.
          Access is granted and revoked afterwards, account by account and workspace by
          workspace, from this same table; there are three roles:
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
              body: "Whoever administers gets into every workspace without being a member of any. It cannot be taken away from oneself: that is what stops the installation being left with nobody to administer it.",
            },
            {
              key: "reset",
              head: <>"{t("acc.resetLink")}"</>,
              body: "The same link the \"I have forgotten my password\" mail would send, generated here so it can be handed over by hand. It lasts a few minutes and works once.",
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
              body: "Actually deletes the account, and it cannot be undone. What it produced does NOT go with it: the generated variants and the evaluation sessions stay, without an author. A course built on that material does not collapse because whoever generated it was removed, and the study does not lose the comparisons it counted.",
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
          Every instance of the installation with its members, its variants and the state of its
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
              body: "Deleting a workspace from here takes its directory tree off the disk too, the raw documents included. The dialog enumerates what disappears, and the instance's identifier has to be typed to confirm. It is not offered on the last workspace left.",
            },
          ]}
        />
        <Paragraph>
          <strong>Emptying one particular stage</strong> is done from its own badge in the chain
          column: press the stage's badge and confirm. It does not touch the history, so if you
          get it wrong it is restored from the artifact's own screen.
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
                  workspace: what is running, what is waiting, and whose each one is.
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
          because its model does not reason, the variant because each commission decides that,
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
          variants and evaluations read exactly the same when it opens again.
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
    question: `A stage says "${t(STATUS.stale.labelKey)}"`,
    answer: (
      <p>
        Something it depends on changed after you approved it. Open the stage: either rebuild
        with what is new, or check that it still holds and approve it again. Meanwhile, the
        stages that depend on it stay blocked.
      </p>
    ),
  },
  {
    key: "bloqueado",
    question: `A stage says "${t(STATUS.blocked.labelKey)}"`,
    answer: (
      <p>
        It is not "it is not done", it is "it is not your turn yet": something it depends on is
        unapproved. The screen itself says which, with a link.
      </p>
    ),
  },
  {
    key: "aprobada",
    question: "An approved stage will not let me change anything",
    answer: (
      <>
        <p>
          That is what approving means. What gets approved is the file exactly as it stands, so
          while the stage is closed the screen offers no control that rewrites it: the fields are
          visible, but read-only.
        </p>
        <p>
          The way back is the "{t("stage.reopen")}" button in the header, with the notice
          underneath saying it in as many words: "{t("stage.locked")}". Reopening removes the
          approval and nothing else — it deletes nothing, it rebuilds nothing — and approving
          again costs one click.
        </p>
        <p>
          Two things keep working with the stage approved, because they do not touch the
          artifact: the concept descriptions and the curriculum.
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
          permission on the instance is read-only; the previous stage is not approved; the raw
          slot has no documents in it; the engine does not answer; or this same build is already
          queued. If it is the one about material, the link on the notice itself takes you to
          upload it.
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
    question: "There are bank exercises with no concept at all",
    answer: (
      <p>
        That is normal on the first pass. Use "{t("bank.retagUntagged", { n: "N" })}": it runs
        only over those, never over the whole bank. And repeating makes sense, because the index
        improves with every well-tagged exercise. If one keeps resisting, set its concept by hand.
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
        Building the graph is the most expensive job in the chain. The phase bar says which one
        it is on and the section that moves is the one running; the run drawer shows the
        particular step. You can close the tab and come back later.
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
          single place every reason not to offer itself — read-only permission, the previous
          stage unapproved, the raw slot empty, the engine not answering, that same build already
          queued — and says them in its own tooltip. Another job running is not on the list: that
          resolves itself by waiting your turn, and the button does the counting.
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
