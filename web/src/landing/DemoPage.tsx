import "./i18n";

import { ArrowLeft, FilePlus2, RotateCcw, SkipForward } from "lucide-react";
import { useMemo, useState, useSyncExternalStore } from "react";

import { Badge } from "@/components/ui/badge";
import { Button, buttonVariants } from "@/components/ui/button";
import { Spinner } from "@/components/ui/misc";
import { localeStore, useT } from "@/lib/i18n";
import { Link } from "@/lib/router";
import { cn } from "@/lib/utils";

import { DemoFrame } from "./demo/DemoFrame";
import { createWorld, type Preset } from "./demo/world";
import { LanguageSwitch } from "./LanguageSwitch";

/** The query that opens the demo with the construction closed, on «Generar ejercicios». */
export const START_AT_GENERATE = "start=generate";

function presetOf(search: string): Preset {
  return new URLSearchParams(search).get("start") === "generate" ? "ready" : "fresh";
}

/**
 * THE DEMO, A PAGE OF ITS OWN (`/demo`): the real application over the demo's server, across
 * the whole window, under one slim bar that is the demo's and not the application's.
 *
 * Its own page because inside the landing the application sat in a frame narrower than the
 * screens it draws (the user's request, 2026-10-12: «no lo veo bien»). The bar is a sunk
 * strip, so it never reads as the application's header under it: the way back to the
 * landing on the left, then the demo's name, and on the right its moves and the language.
 * A fresh demo is a new subject with both origins empty, so step 1 is the step to do, and
 * the sample documents come in by themselves a moment later (`world.arrive`) while the bar
 * says so. Should the visitor delete them, the bar offers them again, outside the
 * application, which stays as it is (a file dropped on it works too, and never leaves the
 * browser). Public, and
 * answered by `AuthGate` before the session is asked for, so no live query of the page
 * meets the demo's transport.
 */
export function DemoPage() {
  const { t } = useT();
  // Which demo is mounted: its preset and a number that changes to mount a fresh one.
  const [demo, setDemo] = useState(() => ({ preset: presetOf(window.location.search), seed: 0 }));
  const restart = (preset: Preset) => setDemo((was) => ({ preset, seed: was.seed + 1 }));
  // One world per demo: a restart is a new seed, a new world and a new frame.
  const world = useMemo(
    () =>
      createWorld({
        preset: demo.preset,
        language: () => localeStore.getSnapshot(),
        subjectName: () => t("landing.demo.subject"),
        teacherName: () => t("landing.demo.teacher"),
      }),
    // `t` changes with the language; the names are read through it on every answer anyway.
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [demo],
  );
  useSyncExternalStore(world.subscribe, world.getVersion, world.getVersion);
  const arriving = world.isArriving();
  const missing = !arriving && world.missingDocuments();

  return (
    <div className="flex h-dvh flex-col">
      <div className="flex shrink-0 items-center justify-between gap-3 bg-sunk px-3 py-2 sm:px-5">
        <div className="flex min-w-0 items-center gap-3">
          <Link to="/" className={cn(buttonVariants({ variant: "ghost", size: "sm" }), "shrink-0")}>
            <ArrowLeft />
            {t("landing.demoPage.back")}
          </Link>
          <span aria-hidden className="hidden h-5 w-px bg-border sm:block" />
          <span className="hidden truncate text-small font-medium sm:inline">{t("landing.demo.window")}</span>
          <Badge variant="outline" className="hidden whitespace-nowrap md:inline-flex">
            {t("landing.demo.sample")}
          </Badge>
        </div>
        <div className="flex shrink-0 items-center gap-1 sm:gap-2">
          {arriving ? (
            <span role="status" className="flex items-center gap-2 px-2 text-small text-muted-foreground">
              <Spinner className="size-4" />
              <span className="hidden md:inline">{t("landing.demoPage.arriving")}</span>
            </span>
          ) : null}
          {missing ? (
            <Button
              size="sm"
              aria-label={t("landing.demoPage.samples")}
              title={t("landing.demoPage.samplesHint")}
              onClick={() => world.addSamples()}
            >
              <FilePlus2 />
              <span className="hidden md:inline">{t("landing.demoPage.samples")}</span>
            </Button>
          ) : null}
          <Button
            size="sm"
            variant="ghost"
            aria-label={t("landing.demo.reset")}
            title={t("landing.demo.reset")}
            onClick={() => restart("fresh")}
          >
            <RotateCcw />
            <span className="hidden lg:inline">{t("landing.demo.reset")}</span>
          </Button>
          <Button
            size="sm"
            variant="outline"
            aria-label={t("landing.demo.skip")}
            title={t("landing.demo.skip")}
            onClick={() => restart("ready")}
          >
            <SkipForward />
            <span className="hidden lg:inline">{t("landing.demo.skip")}</span>
          </Button>
          <span aria-hidden className="mx-1 h-5 w-px bg-border" />
          <LanguageSwitch />
        </div>
      </div>
      <DemoFrame key={`${demo.preset}-${demo.seed}`} world={world} className="min-h-0 flex-1" />
    </div>
  );
}
