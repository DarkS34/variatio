import {
  Activity,
  Play,
  Scale,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";

import { Badge } from "@/components/ui/badge";
import { Alert, PhaseBar } from "@/components/ui/misc";
import { Rail, type RailStop } from "@/components/ui/rail";
import { StatusMark } from "@/components/ui/status";
import { STATUS, type StatusKey } from "@/lib/status";
import { ARM_META } from "@/study/arms";
import { useT } from "@/lib/i18n";
import { Block, Detail, Facts, Paragraph, Rows, SectionHead, Steps } from "../blocks";

const CHAIN: RailStop[] = [
  { key: "perfil", label: "Profile", status: "approved" },
  { key: "grafo", label: "Graph", status: "approved" },
  { key: "banco", label: "Bank", status: "approved" },
];

const STATE_ORDER: StatusKey[] = ["approved", "draft", "stale", "building", "missing", "blocked"];

const STATE_HINTS: Record<StatusKey, string> = {
  approved: "Closed and counted as good. It is what unlocks the next stage.",
  draft: "Built but not reviewed. It can be edited; it does not count yet.",
  stale:
    "Something it depends on changed after it was approved. It has to be rebuilt or approved again.",
  building: "A job is writing it right now. What was there is hidden until it finishes.",
  missing: "It does not exist yet. The screen shows the header and a single button: build.",
  blocked:
    "Not «it is not done», but «it is not your turn yet»: something it depends on is unapproved.",
};

const BUILD_PLAN = [
  { key: "convert", label: "Converting the corpus", weight: 11 },
  { key: "extract", label: "Extraction", weight: 8 },
  { key: "clean", label: "Cleaning and merging", weight: 25 },
  { key: "domains", label: "Domains", weight: 9 },
  { key: "link", label: "Linking", weight: 26 },
  { key: "curate", label: "Curation", weight: 1 },
];

const ARM_ORDER = ["naive", "rag", "system"] as const;

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

function Empezar() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Getting started" title="What it is and how you move through it">
        <p>
          <strong>Variatio</strong> generates <strong>learning items</strong> —exercises,
          problems, assessment tasks— anchored to a course's syllabus. It does not write about a
          topic in the abstract: it starts from three artifacts that describe your subject and
          produces variants that respect what the student has already seen and what they have
          not.
        </p>
      </SectionHead>

      <Block title="The route, at a glance">
        <div className="flex flex-wrap items-end gap-4 rounded-lg border border-border bg-card p-4 sm:gap-6 sm:p-6">
          <div className="flex flex-col items-center gap-2">
            <Pill icon={Activity} label="Panel" />
            <span className="text-small text-muted-foreground">watch</span>
          </div>

          <span aria-hidden className="w-px self-stretch bg-border" />

          <div className="flex w-full min-w-0 flex-1 flex-col items-center gap-2 sm:w-auto sm:min-w-[20rem]">
            <Rail stops={CHAIN} className="max-w-[26rem]" />
            <span className="text-small text-muted-foreground">
              prepare the instance, in this order
            </span>
          </div>

          <span aria-hidden className="w-px self-stretch bg-border" />

          <div className="flex flex-col items-center gap-2">
            <div className="flex gap-1.5">
              <Pill icon={Play} label="Generate" />
              <Pill icon={Scale} label="Evaluate" tone="study" />
            </div>
            <span className="text-small text-muted-foreground">use what was prepared</span>
          </div>
        </div>
        <Paragraph>
          It is exactly the bar at the top. The line between the three middle stages is not
          decoration: it means dependency, and it is drawn dotted while what sits behind it is
          unresolved.
        </Paragraph>
      </Block>

      <Rows
        items={[
          {
            key: "perfil",
            head: "Exemplars profile",
            body: "What an item is here: its fields, their types, and the guidance the model follows.",
          },
          {
            key: "grafo",
            head: "Knowledge graph",
            body: "The vocabulary: concepts, domains and the relations between them.",
          },
          {
            key: "banco",
            head: "Exemplars bank",
            body: "Real items from your subject, already tagged with concepts from the graph.",
          },
        ]}
      />

      <Alert tone="info" title="You start at the profile, not at the graph">
        <p>
          A graph can be built with nothing else, but its taggability review needs the profile{" "}
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
              From the <strong>Panel</strong>, upload the raw material: the documents with
              example exercises, and the theory corpus.
            </>,
            <>
              Build the <strong>profile</strong>, review it field by field and approve it. It
              takes minutes.
            </>,
            <>
              Launch the <strong>graph</strong>. It is the most expensive job in the chain
              —hours—: you can close the tab, the server carries on.
            </>,
            <>
              Review the graph's <strong>taggability</strong> and its{" "}
              <strong>descriptions</strong>, and approve it.
            </>,
            <>
              Extract the <strong>bank</strong>, go over the items left with no concept, and
              approve it.
            </>,
            <>With the three approved, «Generate» and «Evaluate» open up.</>,
          ]}
        />
      </Block>

      <Detail title="Why does every stage have to be approved?">
        <p>
          What gets approved is the <em>file's hash</em>. While a stage is approved, its screen
          offers no control that rewrites the artifact: to edit it again you have to press
          «Reopen». Approving is what unlocks the next stage and, with all three, generation.
        </p>
        <p>
          What does <em>not</em> rewrite the artifact —the concept descriptions and the
          curriculum— stays available with the stage approved.
        </p>
      </Detail>
    </div>
  );
}

function Workspace() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Getting started" title="The workspace and the subject">
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
          Meanwhile the application is not blocked: this guide, «My profile» and —if you
          administer the installation— «Administration» work with no workspace at all. What waits
          is everything that reads an instance: the three stages, «Generate» and «Evaluate».
        </Paragraph>
      </Block>

      <Block title="One tab, one workspace">
        <Paragraph>
          The active workspace is kept on your account and survives signing out; the one you are{" "}
          <em>looking at</em> is kept by the tab. You can have two subjects open in two tabs of
          the same browser without them treading on each other. Switching workspace empties the
          screen of what you were watching: the jobs, the log and the progress belong to the
          instance you are leaving.
        </Paragraph>
      </Block>

      <Block title="The subject's context">
        <Paragraph>
          It is the prose saying what this instance is about —subject, level, language of
          instruction, conventions— and it goes into <em>every</em> call to the model. It is read
          and edited on the <strong>Panel</strong>, on its own card: it is not a stage of the
          chain, which is why it is not on the bar.
        </Paragraph>
        <Alert tone="attention" title="«Unread draft»">
          <p>
            Every build writes a fresh draft of the context without touching yours. If the card
            says so, there is a new synthesis waiting to be read: open it, keep what improves on
            what you have, and discard the rest. Your curated text is never overwritten on its
            own.
          </p>
        </Alert>
      </Block>

      <Block title="The curriculum">
        <Paragraph>
          The concepts the course <em>has already covered</em>. It is edited on the graph's
          «Curriculum» tab and it is what bounds the scaffolding of every generation: an item may
          lean on a covered concept; it may not depend on one that has not been taught yet.
        </Paragraph>
        <Alert tone="info" title="Empty does not mean «nothing covered»: it means «no restriction»">
          <p>
            Reading it literally would forbid the whole syllabus, which is exactly the state a
            new instance starts in. Emptying it deliberately is saved as a decision, with its
            date.
          </p>
        </Alert>
      </Block>

      <Detail title="«Close prerequisites on save»">
        <p>
          When saving the curriculum you can ask for the prerequisites of what you marked to be
          added too. It is applied <em>on save</em> and written into the file: it is not a rule
          applied at read time, so the curriculum always means exactly what it says.
        </p>
        <p>
          If the graph changes and a saved concept disappears, the screen tells you by name
          instead of dropping it in silence.
        </p>
      </Detail>
    </div>
  );
}

function Perfil() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Preparing the instance · stage 1" title="Exemplars profile">
        <p>
          It defines what an item is: its fields, their types, and the guidance the model follows
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
          { label: "How long it takes", value: "Minutes. One long pass over the sample." },
          {
            label: "What it unlocks",
            value: "The bank's extraction and the graph's taggability review.",
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
              Press «Build». What comes out is a <strong>draft</strong>, not a final result.
            </>,
            <>
              Go over each field: its name, its type, the extraction guidance, the generation
              guidance and who decides its value.
            </>,
            <>
              Go over the <strong>general generation rules</strong>: they are the ones that
              govern how a whole item is written.
            </>,
            <>Approve. The stage closes and the screen stops offering anything that rewrites it.</>,
          ]}
        />
      </Block>

      <Block title="What a field has">
        <Rows
          items={[
            {
              key: "tipo",
              head: "Type",
              body: "Text, number, list, or a closed enumeration of values.",
            },
            {
              key: "extraccion",
              head: "Extraction guidance",
              body: "How to recognise that field inside a raw document.",
            },
            {
              key: "generacion",
              head: "Generation guidance",
              body: "How to write it when generating. It is written by hand: what the builder proposes are general rules, not one per field.",
            },
            {
              key: "decidido",
              head: "Decided by",
              body: "The model, or you. The ones you decide appear as controls on the generation form.",
            },
            {
              key: "primario",
              head: "Primary field",
              body: "The one carrying the statement. It is the one turned into a vector to match against concepts.",
            },
          ]}
        />
      </Block>

      <Alert tone="danger" title="Touching it after extracting the bank invalidates the bank">
        <p>
          The bank's items were extracted against the previous schema. If you change the fields,
          the bank goes to «Stale» and has to be extracted again.
        </p>
      </Alert>

      <Detail title="The draft is not stable, and it is worth knowing">
        <p>
          The builder infers the profile from a sample of the corpus, and it has produced{" "}
          <em>different</em> field sets across two passes over the same material. Treat it as a
          starting point: the version you approve is yours, not its.
        </p>
        <p>If you rebuild it, compare before replacing the one you already had.</p>
      </Detail>
    </div>
  );
}

function Grafo() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Preparing the instance · stage 2" title="Knowledge graph">
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
            label: "How long it takes",
            value: "Hours. It is the most expensive job in the whole chain.",
          },
          {
            label: "What it unlocks",
            value: "The bank's tagging, the curriculum and generation.",
          },
        ]}
      />

      <Block title="The two views">
        <Rows
          items={[
            {
              key: "temario",
              head: "Syllabus",
              body: "The domains and their concepts, with the graph canvas beside them. Drag to move, scroll to zoom, and clicking a node selects it in the table too.",
            },
            {
              key: "curriculo",
              head: "Curriculum",
              body: "What has been covered already. This is where it is marked, and where it is saved with or without closing prerequisites.",
            },
          ]}
        />
        <Paragraph>
          The canvas has two layouts: <strong>forces</strong>, which groups by neighbourhood, and{" "}
          <strong>curriculum</strong>, which orders by prerequisite levels. Switching from one to
          the other rebuilds nothing: the nodes ease across to their new positions.
        </Paragraph>
      </Block>

      <Block title="After building, three reviews">
        <Steps
          items={[
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                Taggability
                <Badge variant="attention">needs the profile approved</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                Which concepts work as a <em>label</em>. The ones that would fit any item at all
                —«coding», «design»— are marked as non-taggable: they still exist and still work
                through their relations, they simply stop being able to be what an exercise is
                about. When in doubt, exclude: a vague label pollutes the whole corpus.
              </p>
            </>,
            <>
              <p className="font-medium">Descriptions</p>
              <p className="text-small text-muted-foreground">
                The prose describing each concept, written against the paragraphs of the corpus
                it came from. <strong>It is the text matched against, not the name.</strong> They
                are written on their own when indexing; the tab is for reading them and
                correcting the ones that do not say what you would say.
              </p>
            </>,
            <>
              <p className="font-medium">Curation by hand</p>
              <p className="text-small text-muted-foreground">
                Renaming what came out crooked, deleting what is not a concept of the subject,
                and fixing relations. Renaming carries the corpus anchoring with it; deleting
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
            bank items already carrying that concept.
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
          <ul className="space-y-1">
            <li>
              <span className="font-medium text-settled">Assumed known</span> — prerequisites that
              are also in the curriculum. The exercise may lean on them, but must not turn them
              into the difficulty. They travel with their description, not as a bare name.
            </li>
            <li>
              <span className="font-medium text-destructive">Forbidden</span> — what comes after
              the target and has not been taught yet. It must not appear.
            </li>
          </ul>
          <p>
            Both lists walk the whole graph, not one hop: they are transitive closures bounded by
            the curriculum. On the generation screen they are drawn before launching, so you can
            see exactly what the model is going to work with.
          </p>
        </Detail>
      </div>
    </div>
  );
}

function Banco() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Preparing the instance · stage 3" title="Exemplars bank">
        <p>
          The items extracted from your documents and tagged with concepts from the graph. They
          are the examples that accompany every generation: this is where «here is how exercises
          are written in this subject» comes from, for the model to imitate.
        </p>
      </SectionHead>

      <Facts
        items={[
          {
            label: "What it produces",
            value: <code className="font-mono text-small">exemplars_bank.json</code>,
          },
          {
            label: "How long it takes",
            value: "Tens of minutes, depending on how many documents there are.",
          },
          {
            label: "It is saved",
            value: "After each document. Cancelling loses nothing already extracted.",
          },
        ]}
      />

      <Alert tone="info" title="Extracting and tagging are one single job">
        <p>
          Each document is tagged as it comes out of the extractor, so there is no «tag
          everything» button: that step no longer exists on its own. What there is, is the
          correction of what came out wrong.
        </p>
      </Alert>

      <Block title="It is reviewed by suspicion, not top to bottom">
        <Steps
          items={[
            <>
              First, the ones <strong>left with no concept</strong>. The tagging card counts them
              and «See the N with no concept» filters them.
            </>,
            <>
              Then the decisions <strong>won by a narrow margin</strong>: that is where the
              matching goes wrong without saying so.
            </>,
            <>
              Correct the <strong>primary concept</strong> by hand where needed: it is the one
              that decides what that item is compared against afterwards.
            </>,
          ]}
        />
      </Block>

      <Block title="The two re-tag buttons, which do not do the same thing">
        <Rows
          items={[
            {
              key: "pendientes",
              head: "«Re-tag the N»",
              body: "With no selection: it runs over exactly the items left with no concept, never over the whole bank.",
            },
            {
              key: "seleccion",
              head: "«Re-tag selection»",
              body: "With items ticked by hand: only those are re-tagged, even if they already had a concept.",
            },
          ]}
        />
      </Block>

      <Detail title="Retrying makes sense: the index improves between passes">
        <p>
          Every well-tagged item pushes its concept's centre towards where it really is, so one
          pass's index is consumed by the next. An item that finds no concept today may find one
          tomorrow without your having touched anything.
        </p>
        <p>
          That is why rejected ones are tried again on every pass, instead of being marked as
          impossible.
        </p>
      </Detail>
    </div>
  );
}

function Generar() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Using it" title="Generate variants">
        <p>
          One commission, one batch of variants. The form is five questions: they are answered
          top to bottom and each one collapses to a single line once answered, so changing the
          concepts again costs one click and no scrolling.
        </p>
      </SectionHead>

      <Block title="The five questions">
        <Steps
          items={[
            <>
              <p className="font-medium">What kind of item?</p>
              <p className="text-small text-muted-foreground">
                The modality, from the ones your profile declares. It determines which fields
                have to be filled in afterwards.
              </p>
            </>,
            <>
              <p className="font-medium">What has been covered already?</p>
              <p className="text-small text-muted-foreground">
                The curriculum for <em>this</em> commission. It arrives filled in with the
                workspace's own; emptying it here means «no restriction», for this run only.
              </p>
            </>,
            <>
              <p className="font-medium">What has to be practised?</p>
              <p className="text-small text-muted-foreground">
                The target concepts. Only the <strong>taggable</strong> ones are offered: this is
                where you choose what the exercise is about, and a generic concept is no use for
                that.
              </p>
            </>,
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                Fixed fields
                <Badge variant="outline">optional</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                The fields your profile marks as decided by the user: difficulty, answer format,
                whatever you have declared.
              </p>
            </>,
            <>
              <p className="flex flex-wrap items-center gap-2 font-medium">
                Additional instructions
                <Badge variant="outline">optional</Badge>
              </p>
              <p className="text-small text-muted-foreground">
                Free text for what none of the controls above decides. It goes through two
                filters before entering the prompt.
              </p>
            </>,
          ]}
        />
      </Block>

      <Block title="What happens to what you write in the free text">
        <Rows
          items={[
            {
              key: "guardrail",
              head: "1 · Guardrail",
              body: "A fixed check blocks orders to override instructions («forget everything above…»), and then a judge model decides whether there is anything harmful or an attempt to get around the exercise's own restrictions.",
            },
            {
              key: "admisibilidad",
              head: "2 · Admissibility",
              body: "It decides whether what you are asking for belongs to this field or to something you already decided above: the concepts, the modality, the item's fields, or the subject itself. If it does, it tells you which control decides it.",
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

      <Block title="Reasoning and effort">
        <Paragraph>
          The switch decides whether the model deliberates before answering; the bar beside it,
          how much. A high effort on the local model multiplies the time several times over
          without necessarily improving the statement, and the screen itself warns you when the
          model about to serve the commission is one of those that runs away at the top end.
        </Paragraph>
      </Block>

      <Block title="What you see when it finishes">
        <div className="space-y-3">
          <div className="flex flex-wrap items-start gap-3">
            <Badge variant="settled">saved</Badge>
            <p className="max-w-[64ch] flex-1 text-body text-muted-foreground">
              Every variant is saved into «My variants» <em>the moment it validates</em>, with
              its whole commission. A batch cancelled at the third keeps three.
            </p>
          </div>
          <div className="flex flex-wrap items-start gap-3">
            <Badge variant="attention">2 signals</Badge>
            <p className="max-w-[64ch] flex-1 text-body text-muted-foreground">
              What the system can check without judging the exercise: whether it names something
              not yet taught, whether it looks too much like an example or another one in the
              batch, and whether the tagger recognises it as the concept you asked for.{" "}
              <strong>They are signals for whoever reads, not a rejection.</strong>
            </p>
          </div>
        </div>
      </Block>

      <Block title="And afterwards">
        <Rows
          items={[
            {
              key: "cambiar",
              head: "«Change the commission»",
              body: "Reopens the form with everything filled in and leaves the results in view until you launch another batch.",
            },
            {
              key: "otras",
              head: "«Generate another N»",
              body: "Repeats the same commission, new batch.",
            },
            {
              key: "como-esta",
              head: "«Generate more like this one»",
              body: "It is in «My variants» and recovers the commission of one particular variant, even from another day.",
            },
          ]}
        />
      </Block>
    </div>
  );
}

function Evaluar() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Using it" title="Evaluate">
        <p>
          The same commission solved by three different architectures and presented{" "}
          <strong>blind</strong>, so that you choose without knowing which is which. It is the
          part of the system that exists to measure it, not to produce material.
        </p>
        <p>
          Normally you will not have to prepare anything: the screen opens on{" "}
          <strong>whatever somebody has assigned you</strong> and all you have to do is read and
          decide.
        </p>
      </SectionHead>

      <Facts
        items={[
          { label: "How long it takes", value: "A couple of minutes per comparison." },
          {
            label: "What it produces",
            value: "A saved session with the three proposals and your judgement.",
          },
          { label: "What you need", value: "Nothing: the comparisons come ready." },
        ]}
      />

      <Block title="The three tabs">
        <Rows
          items={[
            {
              key: "asignadas",
              head: "Assigned",
              body: "What somebody has prepared for you. It is where the screen opens and where almost all your work will be. At the top, the next one not yet judged; below, the ones left and the ones you already closed.",
            },
            {
              key: "encargo",
              head: "Your own commission",
              body: "In case you want to ask for a particular exercise yourself. It is the same «Generate» form, without two controls: how many items, and whether the model reasons. If your account is a student's, this tab does not appear.",
            },
            {
              key: "sesiones",
              head: "My sessions",
              body: "Your history. You can reread any closed session, reveal included.",
            },
          ]}
        />
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
          <strong>«I have no basis for judging this»</strong>. Evaluators come from different
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
          <strong>How many items are generated</strong>: always one per architecture. It is what
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

function Ejecucion() {
  const { t } = useT();
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Day to day" title="Following a run">
        <p>
          One GPU, one job at a time. You can close the tab: the job runs on the server and you
          find it where it was when you come back. What is being done is watched from the{" "}
          <strong>Panel</strong> and from the run drawer.
        </p>
      </SectionHead>

      <Block title="The six states">
        <Paragraph>
          No state is told apart by colour alone: each has its own shape, and that shape is the
          same on the bar at the top, on the panel's cards and in each stage's header.
        </Paragraph>
        <div className="divide-y divide-border rounded-lg border border-border bg-card">
          {STATE_ORDER.map((key) => (
            <div key={key} className="flex items-center gap-4 p-3">
              <StatusMark
                status={key === "blocked" ? "missing" : key}
                blocked={key === "blocked"}
                size="md"
              />
              <span className="w-32 shrink-0 text-body font-medium">{t(STATUS[key].labelKey)}</span>
              <span className="text-small text-muted-foreground">{STATE_HINTS[key]}</span>
            </div>
          ))}
        </div>
      </Block>

      <Block title="The bar is the plan">
        <div className="space-y-3 rounded-lg border border-border bg-card p-4">
          <PhaseBar phases={BUILD_PLAN} percent={42} activeKey="clean" />
          <Paragraph>
            Each section is a phase, and its width is that phase's <em>measured weight</em>: that
            is why cleaning and linking take up half the bar and the final curation is a hairline.
            The one that moves is the one running. There is no time estimate anywhere, and that
            is deliberate: changing model changes the cost of each call by multiples, and a false
            figure is worse than none.
          </Paragraph>
        </div>
      </Block>

      <Block title="Where to look">
        <Rows
          items={[
            {
              key: "ejecucion",
              head: "«See run»",
              body: "The pill at the bottom right, always present. It opens the drawer on the progress tab: the steps, the phase and what is being written.",
            },
            {
              key: "registro",
              head: "«Log»",
              body: "Top right, with the session's line count. It is the same drawer, on the other tab.",
            },
          ]}
        />
      </Block>

      <Alert tone="attention" title="Cancelling and rebuilding">
        <p>
          Cancelling does not cut off mid-call: it stops at the next safe point, so it can take a
          while. And a rebuild <em>hides</em> the artifact it is about to replace without
          deleting it —the builder writes at the end— which is why cancelling brings it straight
          back, untouched and with no restore step.
        </p>
      </Alert>

      <Detail title="The warning ribbon on the top bar">
        <p>
          When the inference engine does not answer, or when some model has yet to be downloaded,
          a ribbon appears under the navigation bar saying exactly what breaks and what keeps
          working: what is already built can always still be read, what fails is starting new
          jobs.
        </p>
      </Detail>
    </div>
  );
}

function Cuenta() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Day to day" title="Your account and the installation">
        <p>
          Everything that is yours and is not part of the chain lives in «My profile», behind the
          avatar at the top right — the same menu you got here from.
        </p>
      </SectionHead>

      <Rows
        items={[
          {
            key: "cuenta",
            head: "Account",
            body: "Your visible name, an optional email address and the password. The address is not used to sign in: only to receive the link to reset it.",
          },
          {
            key: "variantes",
            head: "Variants",
            body: "Everything you have generated, with the commission that produced it. «More like this one» is relaunched from here.",
          },
          {
            key: "accesos",
            head: "Access",
            body: "Which workspaces you are in and with what role. It is read-only: access is granted by whoever administers.",
          },
        ]}
      />

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
          in a shared place. On opening it you also choose your password —whichever you like, or
          the one your manager suggests— and say whether you teach or study.
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

      <Block title="Administration">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">administrators only</Badge>
        </div>
        <Paragraph>
          The installation seen from outside, in five tabs: <strong>Evaluations</strong> (the
          study), <strong>Accounts and access</strong> (invitations, roles, unlocks),{" "}
          <strong>Workspaces</strong> (disk usage, export, delete), <strong>Engine</strong>{" "}
          (resident models, downloads, the SSH tunnel to the GPU box) and{" "}
          <strong>Settings</strong> (every setting, each with what it cost to measure it and with
          what it will invalidate on saving).
        </Paragraph>
      </Block>

      <Block title="Closing the installation while it is being worked on">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant="secondary">administrators only</Badge>
        </div>
        <Paragraph>
          At the very top of Administration there is a <strong>maintenance</strong> switch.
          Closed, every other account sees a notice screen instead of the application — with
          whatever text is written there — and the API refuses their requests; whoever
          administers still gets in, which is what makes it possible to open it again.
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

const PROBLEMS: { key: string; question: string; answer: ReactNode }[] = [
  {
    key: "mantenimiento",
    question: "«Under maintenance»",
    answer: (
      <>
        <p>
          It is not a failure: whoever administers the installation has closed it deliberately to
          apply changes. The notice says since when, and yours is where it was — artifacts,
          variants and evaluations read exactly the same when it opens again.
        </p>
        <p>
          There is no expected time of return, and there is none because nobody knows it. «Check
          again» asks once more; the screen also does it by itself every few seconds.
        </p>
      </>
    ),
  },
  {
    key: "ollama",
    question: "«Ollama does not answer on …»",
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
    key: "modelo",
    question: "A model shows as «not installed»",
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
    question: "A stage says «Stale»",
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
    question: "A stage says «Blocked»",
    answer: (
      <p>
        It is not «it is not done», it is «it is not your turn yet»: something it depends on is
        unapproved. The screen itself says which, with a link.
      </p>
    ),
  },
  {
    key: "boton",
    question: "The build button is off",
    answer: (
      <p>
        Hover over it: it says why. There are only four reasons — raw material is missing, a job
        is already running, the engine does not answer, or the previous stage is not approved. If
        it is the first, the link on the notice itself takes you to the Panel to upload the
        material.
      </p>
    ),
  },
  {
    key: "sin-concepto",
    question: "There are bank items with no concept at all",
    answer: (
      <p>
        That is normal on the first pass. Use «Re-tag the N»: it runs only over those, never over
        the whole bank. And repeating makes sense, because the index improves with every
        well-tagged item. If one keeps resisting, set its concept by hand.
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
        Building the graph takes hours: it is the most expensive job in the chain. The phase bar
        says which one it is on and the section that moves is the one running; the run drawer
        shows the particular step. You can close the tab and come back later.
      </p>
    ),
  },
];

function Repartir() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Day to day" title="Handing out evaluations">
        <p>
          How the work evaluators find already done gets prepared. It lives in{" "}
          <strong>Administration → Evaluations</strong> and only whoever administers the
          installation sees it.
        </p>
        <p>
          The idea behind it: <strong>whoever hands out decides who is able to judge what</strong>
          . With evaluators from different subjects and different years there is no automatic
          rule that can hand out well, because the information needed —who teaches what— is in no
          table.
        </p>
      </SectionHead>

      <Block title="The three steps, in that order">
        <Steps
          items={[
            <>
              <strong>To whom?</strong> You choose the person first, not the comparison. That way
              «can they judge this?» is the first question and not one asked at the end.
            </>,
            <>
              <strong>In which of their workspaces?</strong> Only the ones that person can really
              open show up. Assigning them something from a subject they have no access to would
              put an entry in their queue that errors when pressed.
            </>,
            <>
              <strong>Which ones?</strong> You tick the comparisons that are theirs and assign
              them. The ones you do not hand out <strong>stay stored</strong> for somebody else.
            </>,
          ]}
        />
      </Block>

      <Block title="Preparing comparisons in advance">
        <Paragraph>
          On the third step, «Commission more comparisons» opens the same «Generate» form and
          prepares several in one go. They are done one after another in the queue, and appear in
          the list as they finish.
        </Paragraph>
        <Paragraph>
          Preparing them beforehand is what lets a teacher come in and have nothing to configure
          and no GPU to wait for. It is also what makes it possible to{" "}
          <strong>spread the commissions across domains and exercise types deliberately</strong>{" "}
          instead of letting each evaluator ask for their two favourite concepts.
        </Paragraph>
        <Alert tone="attention" title="To commission, you have to have that workspace open">
          <p>
            The form reads the graph and the concepts of the workspace you have active at the very
            top. If it does not match the one chosen in step 2, the button is disabled on purpose:
            composing a commission with one subject's concepts to run it in another would not end
            well. Handing out what already exists does work from anywhere.
          </p>
        </Alert>
      </Block>

      <Block title="Giving the same comparison to two people">
        <Paragraph>
          It is deliberate and it is the only way to know whether the instrument is reliable: if
          two people reading the same three exercises agree, the measure holds up; if not, that
          has to be said. The list shows who already has each comparison, so that the overlap can
          be built on purpose.
        </Paragraph>
        <Paragraph>
          Each person gets the <strong>same exercises in an order of their own</strong>, so that
          what they share is the judgement and not the position of the cards.
        </Paragraph>
        <Paragraph>
          There is also a tick-box to repeat a comparison for somebody who has already judged it.
          That measures something else —whether a person is consistent with themselves— and that
          is why it has to be asked for explicitly.
        </Paragraph>
      </Block>

      <Block title="Teacher or student">
        <Paragraph>
          Every account carries an evaluator profile that decides{" "}
          <strong>which question is asked</strong> about each card: a teacher, whether they would
          set the exercise in class; a student, whether it would be useful to practise with. A
          student does not teach, so asking them the first would only produce an answer given out
          of politeness.
        </Paragraph>
        <Paragraph>
          Each person says so when creating their account from the invitation: the link does not
          carry it, because whoever invites has no reason to know and a question in the middle of
          a comparison gets answered any old way. It is corrected afterwards from «Accounts and
          access», and that is also where an account created from the command line is given a
          profile. Accounts with no profile are flagged so they do not stay that way: meanwhile
          they get the teacher's questions.
        </Paragraph>
      </Block>

      <Detail title="What the panel looks at to know whether the study holds up">
        <p>
          <strong>Whether the preference is distinguishable from chance</strong>. With three
          proposals, choosing blind would give 33 %. The panel gives every percentage its
          interval and the probability of having seen it by coincidence.
        </p>
        <p>
          <strong>Whether position decided anything</strong>. It crosses the chosen letter
          against the order that was drawn. If the first card won too often, the problem would be
          the placement and not the exercises.
        </p>
        <p>
          <strong>Whether two evaluators agree</strong>, over the comparisons handed to more than
          one person.
        </p>
        <p>
          <strong>How long judging takes</strong>. A session closed in eight seconds does not
          leave room to read three statements, and it is worth being able to say so.
        </p>
        <p>
          <strong>How many were skipped for lack of basis</strong>. It is a fact about the panel's
          composition, not a failing of anybody's.
        </p>
      </Detail>
    </div>
  );
}

function Problemas() {
  return (
    <div className="space-y-6">
      <SectionHead eyebrow="Day to day" title="When something goes wrong">
        <p>
          Almost nothing that appears here breaks anything: what is already built can always
          still be read. What fails is starting new work.
        </p>
      </SectionHead>

      <div className="space-y-2">
        {PROBLEMS.map((problem) => (
          <Detail key={problem.key} title={problem.question}>
            {problem.answer}
          </Detail>
        ))}
      </div>

      <Alert tone="info" title="General rule: hover over whatever is switched off">
        <p>
          No disabled control stays silent in this application. The build button decides in one
          single place every reason not to offer itself —material missing, a job running, the
          engine not answering, the previous stage unapproved— and says them in its own tooltip.
        </p>
      </Alert>
    </div>
  );
}

export const BODIES: Record<string, () => ReactNode> = {
  empezar: Empezar,
  workspace: Workspace,
  perfil: Perfil,
  grafo: Grafo,
  banco: Banco,
  generar: Generar,
  evaluar: Evaluar,
  ejecucion: Ejecucion,
  cuenta: Cuenta,
  repartir: Repartir,
  problemas: Problemas,
};
