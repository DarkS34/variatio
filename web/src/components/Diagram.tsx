import { Code2, Workflow } from "lucide-react";
import { useEffect, useId, useState, useSyncExternalStore } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

type Theme = "light" | "dark";

/**
 * A Mermaid diagram, drawn.
 *
 * Mermaid and not a hand-rolled subset, for KaTeX's reason: what the material contains is
 * class diagrams with attributes, use-case flowcharts with subgraphs and labelled edges,
 * sequence and state diagrams, and a translator for "boxes and arrows" would be wrong on
 * exactly the exercises worth drawing. It is imported lazily, so the ~1 MB of the library
 * and its per-type grammars reach the browser only on a screen that has a diagram to show.
 *
 * It paints in the app's own tokens and in nothing else. Mermaid's `base` theme takes its
 * palette from `themeVariables`, and every one of them is read off the stylesheet at render
 * time — the card for a node's ground, the ink for its border and its text, the muted ground
 * for a cluster — so a diagram is achromatic like the rest of the structure and follows the
 * theme when it changes. Mermaid cannot read `oklch()` itself; `sRGB` converts through a
 * canvas, which is the one place the browser will serialise any colour it can paint.
 *
 * `securityLevel: "strict"` keeps the labels as text — what is drawn here is model output
 * and a bank statement — and `suppressErrorRendering` keeps Mermaid's own "syntax error"
 * bomb off the page: an invalid diagram shows its source and the parser's sentence, which
 * is what a person judging whether it "compiles" needs to see.
 */

type State =
  | { kind: "pending" }
  | { kind: "drawn"; svg: string }
  | { kind: "invalid"; reason: string };

const INK_FALLBACK = { light: ["#ffffff", "#1a1a1e"], dark: ["#26272b", "#f2f2f4"] } as const;

/**
 * One token as a hex colour Mermaid's colour maths can read, or the fallback.
 *
 * Painting one pixel and reading it back is the conversion: a canvas paints any colour the
 * stylesheet can express and `getImageData` always answers in sRGB bytes, where the
 * `fillStyle` getter hands an `oklch()` back unchanged — measured, and Mermaid then threw
 * «Unsupported color format».
 */
function sRGB(token: string, fallback: string): string {
  const raw = getComputedStyle(document.documentElement).getPropertyValue(token).trim();
  if (!raw) return fallback;
  const canvas = document.createElement("canvas");
  canvas.width = 1;
  canvas.height = 1;
  const context = canvas.getContext("2d");
  if (!context) return fallback;
  context.fillStyle = raw;
  context.fillRect(0, 0, 1, 1);
  const [r, g, b, a] = context.getImageData(0, 0, 1, 1).data;
  if (a === 0) return fallback;
  return `#${[r, g, b].map((channel) => channel.toString(16).padStart(2, "0")).join("")}`;
}

function themeVariables(theme: Theme): Record<string, string | boolean> {
  const [paper, ink] = INK_FALLBACK[theme];
  const card = sRGB("--card", paper);
  const foreground = sRGB("--foreground", ink);
  const muted = sRGB("--muted", paper);
  const mutedForeground = sRGB("--muted-foreground", ink);
  const border = sRGB("--border", ink);
  const accent = sRGB("--accent", paper);
  const font = getComputedStyle(document.documentElement).getPropertyValue("--font-sans").trim();
  return {
    darkMode: theme === "dark",
    fontFamily: font || "sans-serif",
    fontSize: "14px",
    background: card,
    mainBkg: card,
    primaryColor: card,
    primaryTextColor: foreground,
    primaryBorderColor: foreground,
    secondaryColor: muted,
    secondaryTextColor: foreground,
    secondaryBorderColor: foreground,
    tertiaryColor: accent,
    tertiaryTextColor: foreground,
    tertiaryBorderColor: border,
    lineColor: foreground,
    textColor: foreground,
    titleColor: foreground,
    nodeBorder: foreground,
    nodeTextColor: foreground,
    clusterBkg: muted,
    clusterBorder: border,
    edgeLabelBackground: card,
    noteBkgColor: muted,
    noteTextColor: foreground,
    noteBorderColor: border,
    actorBkg: card,
    actorBorder: foreground,
    actorTextColor: foreground,
    actorLineColor: mutedForeground,
    signalColor: foreground,
    signalTextColor: foreground,
    labelBoxBkgColor: card,
    labelBoxBorderColor: foreground,
    labelTextColor: foreground,
    loopTextColor: foreground,
    activationBkgColor: muted,
    activationBorderColor: foreground,
    sequenceNumberColor: card,
    classText: foreground,
    attributeBackgroundColorOdd: card,
    attributeBackgroundColorEven: muted,
    arrowheadColor: foreground,
    pieOuterStrokeColor: foreground,
    pieStrokeColor: foreground,
    pieTitleTextColor: foreground,
    pieSectionTextColor: foreground,
    pieLegendTextColor: foreground,
    ...scales(accent, foreground, border, muted),
  };
}

/**
 * The categorical scales Mermaid colours a mind map, a timeline, a journey, a pie or a git
 * graph with. Left alone they are twelve hues rotated off the primary, which is the one
 * thing this palette refuses — colour is evidence, and a branch of a mind map is not — so
 * every step is the same grey, and what tells a section from the next is its position.
 */
function scales(fill: string, label: string, peer: string, alternate: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (let i = 0; i < 12; i += 1) {
    out[`cScale${i}`] = fill;
    out[`cScaleLabel${i}`] = label;
    out[`cScalePeer${i}`] = peer;
    out[`cScaleInv${i}`] = label;
    out[`pie${i + 1}`] = i % 2 ? alternate : fill;
  }
  for (let i = 0; i < 8; i += 1) {
    out[`git${i}`] = fill;
    out[`gitBranchLabel${i}`] = label;
  }
  return out;
}

function reasonOf(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  // Mermaid's parser says «Parse error on line N:», then the offending excerpt, then a
  // caret and the whole list of tokens it expected. The line and the excerpt are what a
  // person acts on — measured on the reference bank, the excerpt was a sentence of the
  // slide the transcription had copied into the code — and the token list is noise.
  const [sentence = "", excerpt = ""] = message.split("\n").map((line) => line.trim());
  const where = sentence.replace(/\s+$/, "");
  return excerpt && !excerpt.startsWith("-") && !excerpt.startsWith("Expecting")
    ? `${where} ${excerpt}`
    : where || "?";
}

/**
 * The RESOLVED theme, read off `<html data-theme>` the way `GraphCanvas` reads it — the
 * store stamps it there, and reading the attribute keeps this module free of the store's
 * `window` access at import time, which is what lets `Markdown` stay importable in a test.
 */
function subscribeToTheme(listener: () => void): () => void {
  const observer = new MutationObserver(listener);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => observer.disconnect();
}

function readTheme(): Theme {
  return document.documentElement.dataset.theme === "dark" ? "dark" : "light";
}

function useTheme(): Theme {
  return useSyncExternalStore(subscribeToTheme, readTheme, () => "light");
}

export function Diagram({ code, className }: { code: string; className?: string }) {
  const { t } = useT();
  const theme = useTheme();
  const id = `diagram-${useId().replace(/[^a-zA-Z0-9]/g, "")}`;
  const [state, setState] = useState<State>({ kind: "pending" });
  const [showSource, setShowSource] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const { default: mermaid } = await import("mermaid");
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: "strict",
          suppressErrorRendering: true,
          theme: "base",
          themeVariables: themeVariables(theme),
          flowchart: { htmlLabels: false, useMaxWidth: true },
          sequence: { useMaxWidth: true },
          class: { useMaxWidth: true },
          state: { useMaxWidth: true },
          er: { useMaxWidth: true },
          gantt: { useMaxWidth: true },
        });
        await mermaid.parse(code);
        const { svg } = await mermaid.render(id, code);
        if (alive) setState({ kind: "drawn", svg });
      } catch (error) {
        // Mermaid leaves its scratch element behind when a render throws.
        document.getElementById(`d${id}`)?.remove();
        if (alive) setState({ kind: "invalid", reason: reasonOf(error) });
      }
    })();
    return () => {
      alive = false;
    };
  }, [code, id, theme]);

  if (state.kind === "invalid") {
    return (
      <div className={cn("space-y-1", className)}>
        <CodeBlock code={code} language="text" maxHeight="18rem" />
        <p className="text-small text-destructive">{t("diagram.invalid", { reason: state.reason })}</p>
      </div>
    );
  }

  if (state.kind === "pending") {
    return (
      <div className={cn("rounded-lg border border-border bg-card px-3 py-2 text-small text-muted-foreground", className)}>
        {t("diagram.drawing")}
      </div>
    );
  }

  return (
    <div className={cn("group relative", className)}>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={() => setShowSource((value) => !value)}
        aria-label={t(showSource ? "diagram.showDiagram" : "diagram.showSource")}
        title={t(showSource ? "diagram.showDiagram" : "diagram.showSource")}
        className="absolute right-1.5 top-1.5 z-10 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
      >
        {showSource ? <Workflow /> : <Code2 />}
      </Button>
      {showSource ? (
        <CodeBlock code={code} language="text" maxHeight="18rem" />
      ) : (
        <div
          className="thin-scroll overflow-x-auto rounded-lg border border-border bg-card p-3 [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
          dangerouslySetInnerHTML={{ __html: state.svg }}
        />
      )}
    </div>
  );
}
