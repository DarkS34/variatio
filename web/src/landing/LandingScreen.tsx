import "./i18n";

import { ArrowDown, ArrowRight, Check, FileText, LogIn, Maximize2, Play } from "lucide-react";
import {
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent,
  type ReactNode,
  type RefObject,
} from "react";

import { StepCounter } from "@/components/AppShell";
import { STAGE_KICKER } from "@/components/StageGate";
import { TabStrip, tabIds } from "@/components/TabStrip";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConceptChip } from "@/components/ui/concept-chip";
import { Lockup } from "@/components/ui/logo";
import { DEMO_PATH, LOGIN_PATH } from "@/features/auth/AuthGate";
import { useT, type Key } from "@/lib/i18n";
import { Link, useRouter } from "@/lib/router";
import { STEPS } from "@/lib/steps";
import { cn } from "@/lib/utils";

import { START_AT_GENERATE } from "./DemoPage";
import { LanguageSwitch } from "./LanguageSwitch";
import { useSectionNav } from "./sectionNav";

/**
 * THE LANDING: what the system does, how, the application itself to try, and the way in.
 * What a visitor without a session sees at `/` (`AuthGate.Front`).
 *
 * Four parts and the footer, redrawn on 2026-10-13 at the user's request («no me gusta»):
 * the hero, whose picture shows the whole system on an invented example — the notes, the
 * concept in the syllabus, the new exercise —; the three moves of a teacher, flat on the
 * ground; the demo, kept as it was; and a band of ink with the way in. Only the picture
 * and the demo stand out of the ground, so depth marks what matters, and the band is the
 * one contrast of the page. One `--attention`: «Probar la demo». No eyebrow over a section
 * but the hero's, which says who the page is for.
 */
export function LandingScreen() {
  const { active, go } = useSectionNav(SECTIONS.map((section) => section.id));
  // The last linked section and what follows it fill the window at least, so a link to it
  // brings its head under the header like any other's: shorter, the page ended before it
  // could. The room it lacks goes to the footer, at the page's end: given to the section
  // itself, it opened a hole between the demo and the band on a tall window.
  const demo = useRef<HTMLElement>(null);
  const join = useRef<HTMLElement>(null);
  const above = useHeights([demo, join]);

  return (
    <div className="flex min-h-full flex-col">
      <Header active={active} go={go} />
      <main className="flex flex-col">
        <Hero />
        <Section id="how" title="landing.how.title" lead="landing.how.lead">
          <Moves />
        </Section>
        <Section id="demo" title="landing.demo.title" lead="landing.demo.lead" innerRef={demo}>
          <DemoInvite />
        </Section>
        <Join innerRef={join} />
      </main>
      <Footer style={{ minHeight: `calc(100dvh + 1rem - ${above}px)` }} />
    </div>
  );
}

/** The sections the header links to, in the page's order. */
const SECTIONS: { id: string; label: Key }[] = [
  { id: "how", label: "landing.nav.how" },
  { id: "demo", label: "landing.nav.demo" },
];

const CONTAINER = "mx-auto w-full max-w-6xl px-4 sm:px-6";
const EYEBROW = cn(STAGE_KICKER, "font-condensed uppercase");

/** The summed height of some elements, read again whenever one of them changes size. */
function useHeights(refs: RefObject<HTMLElement | null>[]): number {
  const [height, setHeight] = useState(0);
  useLayoutEffect(() => {
    const elements = refs.map((ref) => ref.current).filter((element) => element !== null);
    if (!elements.length || typeof ResizeObserver === "undefined") return;
    const measure = () => setHeight(elements.reduce((sum, element) => sum + element.offsetHeight, 0));
    const observer = new ResizeObserver(measure);
    elements.forEach((element) => observer.observe(element));
    return () => observer.disconnect();
    // The refs are the page's own and never change.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return height;
}

/* HEADER ------------------------------------------------------------------------------- */

type Go = (event: MouseEvent, id: string | null) => void;

function Header({ active, go }: { active: string | null; go: Go }) {
  const { t } = useT();
  return (
    <header className="sticky top-0 z-30 bg-background/90 shadow-[0_12px_24px_-18px_var(--shadow-dark)] backdrop-blur">
      <div className={cn(CONTAINER, "flex h-16 items-center justify-between gap-6")}>
        <a
          href="#top"
          onClick={(event) => go(event, null)}
          aria-label={t("landing.home")}
          className="shrink-0"
        >
          <Lockup />
        </a>

        <nav aria-label={t("landing.nav.label")} className="hidden items-center gap-1 md:flex">
          {SECTIONS.map((section) => (
            <a
              key={section.id}
              href={`#${section.id}`}
              onClick={(event) => go(event, section.id)}
              aria-current={active === section.id ? "true" : undefined}
              className={cn(
                "rounded-md px-3 py-1.5 text-small font-medium transition-colors",
                active === section.id
                  ? "bg-sunk text-foreground"
                  : "text-muted-foreground hover:bg-sunk/60 hover:text-foreground",
              )}
            >
              {t(section.label)}
            </a>
          ))}
        </nav>

        <div className="flex items-center gap-3 sm:gap-4">
          <LanguageSwitch />
          <span aria-hidden className="h-6 w-px bg-border" />
          <Link to={LOGIN_PATH} className={buttonVariants({ variant: "default" })}>
            <LogIn />
            {t("landing.login")}
          </Link>
        </div>
      </div>
    </header>
  );
}

/* SECTIONS ----------------------------------------------------------------------------- */

/** One part of the page: its head — a title, at most one line — then its content. */
function Section({
  id,
  title,
  lead,
  innerRef,
  children,
}: {
  id: string;
  title: Key;
  lead?: Key;
  innerRef?: RefObject<HTMLElement | null>;
  children: ReactNode;
}) {
  const { t } = useT();
  return (
    <section ref={innerRef} id={id} aria-labelledby={`${id}-title`}>
      <div className={cn(CONTAINER, "flex flex-col gap-10 py-14 md:py-16")}>
        {/* The anchor of the header's links, resting `HEADER_PX + REST_PX` under the window's
            top (`sectionNav.ts`): the head, and not the section's top, which left the title a
            band of empty padding under the header. */}
        <div id={`${id}-head`} className="flex max-w-2xl scroll-mt-[5.5rem] flex-col gap-3">
          <h2 id={`${id}-title`} className="font-display font-expanded text-title text-balance">
            {t(title)}
          </h2>
          {lead ? <p className="text-body text-muted-foreground">{t(lead)}</p> : null}
        </div>
        {children}
      </div>
    </section>
  );
}

function Hero() {
  const { t } = useT();
  const facts: Key[] = ["landing.hero.fact1", "landing.hero.fact2", "landing.hero.fact3"];
  return (
    <section id="top" aria-labelledby="top-title">
      <div className={cn(CONTAINER, "grid grid-cols-1 items-center gap-12 pb-14 pt-14 md:pb-16 md:pt-20 lg:grid-cols-2 lg:gap-16")}>
        <div className="flex flex-col gap-6">
          <p className={EYEBROW}>{t("landing.hero.kicker")}</p>
          <h1 id="top-title" className="font-display font-expanded text-display text-balance">
            {t("landing.hero.title")}
          </h1>
          <p className="max-w-[32rem] text-body text-muted-foreground">{t("landing.hero.lead")}</p>
          <div className="pt-2">
            <Link to={DEMO_PATH} className={buttonVariants({ variant: "attention", size: "xl" })}>
              {t("landing.hero.demo")}
              <ArrowRight />
            </Link>
          </div>
          <ul className="flex flex-wrap gap-x-6 gap-y-2 pt-2">
            {facts.map((fact) => (
              <li key={fact} className="flex items-center gap-2 text-small text-muted-foreground">
                <Check aria-hidden className="size-4 text-settled" strokeWidth={2.5} />
                {t(fact)}
              </li>
            ))}
          </ul>
        </div>
        <Example />
      </div>
    </section>
  );
}

/* THE HERO'S EXAMPLE ------------------------------------------------------------------- */

/** One invented example: a passage of the notes, its concept in the syllabus, the exercise. */
interface Sample {
  id: string;
  subject: Key;
  file: Key;
  notes: Key;
  known: [Key, Key];
  target: Key;
  type: Key;
  level: Key;
  statement: Key;
}

/** Three subjects far apart, so the picture says that the subject is the teacher's. */
const SAMPLES: Sample[] = [
  {
    id: "programming",
    subject: "landing.example.programming.subject",
    file: "landing.example.programming.file",
    notes: "landing.example.programming.notes",
    known: ["landing.example.programming.known1", "landing.example.programming.known2"],
    target: "landing.example.programming.target",
    type: "landing.example.programming.type",
    level: "landing.example.programming.level",
    statement: "landing.example.programming.statement",
  },
  {
    id: "pharmacology",
    subject: "landing.example.pharmacology.subject",
    file: "landing.example.pharmacology.file",
    notes: "landing.example.pharmacology.notes",
    known: ["landing.example.pharmacology.known1", "landing.example.pharmacology.known2"],
    target: "landing.example.pharmacology.target",
    type: "landing.example.pharmacology.type",
    level: "landing.example.pharmacology.level",
    statement: "landing.example.pharmacology.statement",
  },
  {
    id: "language",
    subject: "landing.example.language.subject",
    file: "landing.example.language.file",
    notes: "landing.example.language.notes",
    known: ["landing.example.language.known1", "landing.example.language.known2"],
    target: "landing.example.language.target",
    type: "landing.example.language.type",
    level: "landing.example.language.level",
    statement: "landing.example.language.statement",
  },
];

const STRIP = "landing-example";

/**
 * The whole system in one picture: a passage of the notes, the concept it teaches in the
 * syllabus after the ones already covered, and the new exercise on it. A tab per subject.
 *
 * Every example stays mounted in the same cell, so the block is as tall as the longest and
 * changing subject never moves the page. A change fades the shown one out and the chosen
 * one in, one after the other, so two texts never overlap: drawn anew on each change, the
 * three parts came back one by one and the block flickered (the user's report, 2026-10-13).
 * Nothing changes by itself: the visitor turns the tabs, drawn in a frame of their own so
 * they read as a switch and not as a line of words.
 */
function Example() {
  const { t } = useT();
  const [shown, setShown] = useState(SAMPLES[0].id);
  return (
    <figure aria-label={t("landing.example.label")} className="m-0">
      <Card className="flex flex-col gap-5 p-4 sm:p-6">
        <TabStrip
          id={STRIP}
          label={t("landing.example.subjects")}
          items={SAMPLES.map((sample) => ({ value: sample.id, label: t(sample.subject) }))}
          value={shown}
          onChange={setShown}
          // A hairline round the three, and a tint under the one the pointer is on. Narrower
          // tabs on a phone, so the three fit across a 360 px screen.
          className="self-start border border-border [&>[aria-selected=false]:hover]:bg-sunk/40 max-sm:gap-1 max-sm:[&>[role=tab]]:px-2"
        />
        <div className="grid [&>*]:col-start-1 [&>*]:row-start-1">
          {SAMPLES.map((sample) => {
            const on = sample.id === shown;
            const ids = tabIds(STRIP, sample.id);
            return (
              <div
                key={sample.id}
                role="tabpanel"
                id={ids.panel}
                aria-labelledby={ids.tab}
                className={cn(
                  "transition-[opacity,visibility] duration-[var(--motion-micro)] ease-[var(--ease)]",
                  on
                    ? "visible opacity-100 delay-[var(--motion-micro)] motion-reduce:delay-0"
                    : "invisible opacity-0",
                )}
              >
                <Passage sample={sample} />
              </div>
            );
          })}
        </div>
      </Card>
    </figure>
  );
}

/**
 * One example's three parts, joined by an arrow. The room a shorter example leaves goes
 * evenly between its parts, not under the last one.
 */
function Passage({ sample }: { sample: Sample }) {
  const { t } = useT();
  const concepts = [...sample.known, sample.target];
  return (
    <div className="flex h-full flex-col justify-between gap-3">
      <Part caption={t("landing.example.notes")}>
        <div className="well flex flex-col gap-2 p-4">
          <span className="flex items-center gap-1.5 text-small text-muted-foreground">
            <FileText aria-hidden className="size-4 shrink-0" />
            <span className="truncate">{t(sample.file)}</span>
          </span>
          <p className="text-small">{t(sample.notes)}</p>
        </div>
      </Part>

      <Arrow />

      <Part caption={t("landing.example.syllabus")}>
        <div className="flex flex-wrap items-center gap-2">
          {/* A rule joins each concept to the one before it and travels with it to a new
              line; on a phone, where the three never fit on one, the chips stand alone. */}
          {concepts.map((key, index) => (
            <span key={key} className="flex max-w-full items-center gap-2">
              {index > 0 ? <span aria-hidden className="hidden h-px w-4 bg-border sm:block" /> : null}
              <ConceptChip tone={index === concepts.length - 1 ? "primary" : "default"}>{t(key)}</ConceptChip>
            </span>
          ))}
        </div>
        <div className="flex gap-5 text-small text-muted-foreground">
          <span className="flex items-center gap-2">
            <span aria-hidden className="size-2.5 rounded-sm border border-border bg-card" />
            {t("landing.example.known")}
          </span>
          <span className="flex items-center gap-2">
            <span aria-hidden className="size-2.5 rounded-sm bg-ink" />
            {t("landing.example.target")}
          </span>
        </div>
      </Part>

      <Arrow />

      <Part caption={t("landing.example.exercise")}>
        <div className="raised flex flex-col gap-2 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-small font-medium">{t(sample.type)}</span>
            <Badge variant="secondary">{t(sample.level)}</Badge>
          </div>
          <p className="text-body">{t(sample.statement)}</p>
        </div>
      </Part>
    </div>
  );
}

/** A part of the example under its caption. */
function Part({ caption, children }: { caption: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2">
      <p className={EYEBROW}>{caption}</p>
      {children}
    </div>
  );
}

/**
 * The step from one part to the next: a bare arrow. In a round tinted mark it read as a
 * button to press, and nothing happened.
 */
function Arrow() {
  return (
    <div aria-hidden className="flex justify-center text-muted-foreground">
      <ArrowDown className="size-4" strokeWidth={1.75} />
    </div>
  );
}

/* HOW ---------------------------------------------------------------------------------- */

/**
 * A teacher's three moves, flat on the ground: numbered, joined by a rule, each with what
 * it gives. In plain verbs, not the application's names for its steps, which a visitor does
 * not know yet; the last mark is ink, as the bar's door is.
 */
function Moves() {
  const { t } = useT();
  const moves: { title: Key; body: Key }[] = [
    { title: "landing.how.step1Title", body: "landing.how.step1Body" },
    { title: "landing.how.step2Title", body: "landing.how.step2Body" },
    { title: "landing.how.step3Title", body: "landing.how.step3Body" },
  ];
  return (
    <ol className="grid gap-8 md:grid-cols-3 md:gap-7">
      {moves.map((move, index) => {
        const last = index === moves.length - 1;
        return (
          <li key={move.title} className="flex gap-4 md:flex-col">
            <div className="flex items-center gap-3">
              <Mark ink={last}>
                <span className="nums font-condensed text-heading">{index + 1}</span>
              </Mark>
              {last ? null : <span aria-hidden className="hidden h-px flex-1 bg-border md:block" />}
            </div>
            <div className="flex flex-col gap-1 md:pr-6">
              <h3 className="text-heading">{t(move.title)}</h3>
              <p className="text-small text-muted-foreground">{t(move.body)}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function Mark({ children, ink = false }: { children: ReactNode; ink?: boolean }) {
  return (
    <span
      aria-hidden
      className={cn(
        "flex size-10 shrink-0 items-center justify-center rounded-inner",
        ink ? "bg-ink text-ink-foreground" : "bg-sunk text-primary",
      )}
    >
      {children}
    </span>
  );
}

/* DEMO --------------------------------------------------------------------------------- */

/**
 * The demo, presented: what one does in it, the two ways in, and a glimpse of the
 * application as it looks once the construction is closed — drawn with the bar's own marks.
 */
function DemoInvite() {
  const { t } = useT();
  const points: Key[] = ["landing.demo.point1", "landing.demo.point2", "landing.demo.point3"];
  return (
    <Card className="grid gap-10 p-6 md:p-10 lg:grid-cols-[0.75fr_1.25fr] lg:items-center">
      <div className="flex flex-col gap-6">
        <ul className="flex flex-col gap-3">
          {points.map((point) => (
            <li key={point} className="flex items-start gap-3 text-body">
              <Check aria-hidden className="mt-1 size-4 shrink-0 text-settled" strokeWidth={2.5} />
              {t(point)}
            </li>
          ))}
        </ul>
        <div className="flex flex-wrap gap-3">
          <Link to={DEMO_PATH} className={buttonVariants({ variant: "default", size: "lg" })}>
            <Maximize2 />
            {t("landing.demo.open")}
          </Link>
          <Link
            to={`${DEMO_PATH}?${START_AT_GENERATE}`}
            className={buttonVariants({ variant: "outline", size: "lg" })}
          >
            {t("landing.demo.openGenerate")}
          </Link>
        </div>
      </div>
      <GlimpseLink />
    </Card>
  );
}

/**
 * The picture of the application opens it, as a reader expects of a picture of a screen:
 * it looked like something to press and did nothing (the user's request, 2026-10-13). Under
 * the pointer it says what it does. For the pointer alone — out of the tab order and hidden
 * from a screen reader — since «Abrir la demo» beside it is the same move for both.
 */
function GlimpseLink() {
  const { t } = useT();
  const { navigate } = useRouter();
  return (
    <a
      href={DEMO_PATH}
      tabIndex={-1}
      aria-hidden
      title={t("landing.demo.open")}
      onClick={(event) => {
        if (event.metaKey || event.ctrlKey || event.shiftKey) return;
        event.preventDefault();
        navigate(DEMO_PATH);
      }}
      className="group relative block rounded-inner"
    >
      <Glimpse />
      <span className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-inner bg-background/40 opacity-0 transition-opacity duration-[var(--motion-enter)] group-hover:opacity-100">
        <span className="flex items-center gap-2 rounded-lg bg-ink px-4 py-2 text-body font-medium text-ink-foreground shadow-drop">
          <Maximize2 aria-hidden className="size-4" />
          {t("landing.demo.open")}
        </span>
      </span>
    </a>
  );
}

/** The application's bar with the construction closed, and the door's screen under it. */
function Glimpse() {
  const { t } = useT();
  return (
    <div aria-hidden className="well flex flex-col gap-4 overflow-hidden rounded-inner p-4">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        {STEPS.map((step, index) => (
          <span key={step.path} className="flex items-center gap-1.5 whitespace-nowrap text-small text-foreground">
            <StepCounter state="done" n={`${index + 1}`} />
            {t(step.labelKey)}
          </span>
        ))}
        <span aria-hidden className="h-5 w-px bg-border" />
        <span className="flex items-center gap-1.5 rounded-md bg-sunk px-2 py-1 text-small font-medium">
          <Play className="size-4" />
          {t("nav.create")}
        </span>
      </div>
      <div className="flex flex-col gap-3 rounded-inner bg-background p-4">
        <span className="font-display font-expanded text-title">{t("nav.create")}</span>
        <div className="grid grid-cols-3 gap-2">
          {[0, 1, 2].map((index) => (
            <span key={index} className="raised flex h-14 flex-col justify-center gap-1.5 rounded-lg px-3">
              <span className="h-2 w-2/3 rounded-full bg-sunk" />
              <span className="h-2 w-1/2 rounded-full bg-sunk" />
            </span>
          ))}
        </div>
        <span className="h-2 w-5/6 rounded-full bg-sunk" />
        <span className="h-2 w-2/3 rounded-full bg-sunk" />
      </div>
    </div>
  );
}

/* THE WAY IN --------------------------------------------------------------------------- */

/**
 * How one gets in, as the page's one band of ink: the invitation, which is the only door to
 * an account, and the login beside it. The button is the band's inverse — the ink's light
 * on the ink —, the pair `check:color` measures as `--ink-foreground` on `--ink`.
 */
function Join({ innerRef }: { innerRef: RefObject<HTMLElement | null> }) {
  const { t } = useT();
  return (
    <section ref={innerRef} id="join" aria-labelledby="join-title">
      <div className={cn(CONTAINER, "pb-14 md:pb-20")}>
        <div className="flex flex-col gap-6 rounded-block bg-ink p-6 text-ink-foreground sm:p-8 md:flex-row md:items-end md:justify-between md:gap-10 md:p-10">
          <div className="flex max-w-xl flex-col gap-2">
            <h2 id="join-title" className="font-display font-expanded text-title text-balance">
              {t("landing.join.title")}
            </h2>
            <p className="text-body text-pretty opacity-80">{t("landing.join.body")}</p>
          </div>
          <div className="flex shrink-0 flex-col items-start gap-2 md:items-end">
            <span className="text-small opacity-80">{t("landing.join.account")}</span>
            <Link
              to={LOGIN_PATH}
              className={cn(
                buttonVariants({ size: "lg" }),
                "bg-ink-foreground text-ink hover:bg-[color-mix(in_oklab,var(--ink-foreground)_88%,var(--ink))] focus-visible:ring-ink-foreground focus-visible:ring-offset-ink",
              )}
            >
              <LogIn />
              {t("landing.login")}
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}

function Footer({ style }: { style?: CSSProperties }) {
  const { t } = useT();
  return (
    <footer className="border-t border-border" style={style}>
      <div
        className={cn(CONTAINER, "flex flex-col gap-4 py-10 sm:flex-row sm:items-center sm:justify-between")}
      >
        <Lockup />
        <p className="text-small text-muted-foreground">{t("landing.footer.licence")}</p>
      </div>
    </footer>
  );
}
