import { Fragment, useMemo, type ReactNode } from "react";

import { CodeBlock } from "@/components/CodeBlock";
import { Diagram } from "@/components/Diagram";
import { TeX } from "@/components/Math";
import { diagramSource, isDiagramTag } from "@/lib/diagram";
import { DISPLAY_OPEN, splitInlineMath, takeDisplayMath } from "@/lib/math";
import { cn } from "@/lib/utils";

/**
 * A deliberately small markdown renderer, for the same reason `CodeBlock` is a
 * deliberately small highlighter: the markdown in this corpus is what a teacher writes
 * — fenced snippets, option lists, the odd table Docling pulled out of a PDF — and a
 * full CommonMark engine would cost more than it returns.
 *
 * Two departures from CommonMark, both forced by the content:
 * - a single newline inside a paragraph is a line break, not a space. Multiple-choice
 *   options arrive as consecutive lines (`a) …` / `b) …`) and joining them is wrong.
 * - an unlabelled fence is plain text, not code. Half of them hold ASCII art the
 *   exercise asks the student to reproduce, so Python colouring would be a lie.
 *
 * Maths is the third departure and the one that had to come from a library: `$…$` and a
 * paragraph of `$$…$$` are cut out BEFORE any markup is looked for, because a formula is
 * not markdown — `q_{error}` is a subscript and `(0|1)^*` is a closure, and letting the
 * emphasis rules near either of them corrupts the exercise rather than merely misdrawing it.
 *
 * A diagram is the fourth and came from a library too: a ```mermaid fence is drawn, and so
 * is a field that IS a bare diagram — the extraction copies a fence's body without the
 * fence, so a bank solution and a generated one usually arrive as `classDiagram …` with no
 * fence around it (`lib/diagram.ts` says where that judgement lives).
 */

type Language = "python" | "json" | "text";

type Block =
  | { kind: "code"; code: string; language: Language }
  | { kind: "diagram"; code: string }
  | { kind: "math"; tex: string }
  | { kind: "heading"; level: number; text: string }
  | { kind: "list"; ordered: boolean; start: number; items: string[] }
  | { kind: "quote"; text: string }
  | { kind: "table"; header: string[]; rows: string[][] }
  | { kind: "rule" }
  | { kind: "paragraph"; text: string };

const FENCE = /^\s{0,3}(```|~~~)\s*([\w+#-]*)\s*$/;
const HEADING = /^\s{0,3}(#{1,6})\s+(.*)$/;
const RULE = /^\s{0,3}([-*_])\s*(?:\1\s*){2,}$/;
const UNORDERED = /^\s*[-*+]\s+(.*)$/;
const ORDERED = /^\s*(\d+)[.)]\s+(.*)$/;
const QUOTE = /^\s{0,3}>\s?(.*)$/;
const TABLE_RULE = /^\s*\|?(?:\s*:?-{2,}:?\s*\|)+\s*:?-{2,}:?\s*\|?\s*$/;

const LANGUAGES: Record<string, Language> = {
  py: "python",
  python: "python",
  python3: "python",
  json: "json",
};

function languageOf(tag: string): Language {
  return LANGUAGES[tag.toLowerCase()] ?? "text";
}

function cells(row: string): string[] {
  return row
    .trim()
    .replace(/^\|/, "")
    .replace(/\|$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

function parseBlocks(source: string): Block[] {
  const bare = diagramSource(source);
  if (bare !== null) return [{ kind: "diagram", code: bare }];

  const lines = source.replace(/\r\n?/g, "\n").split("\n");
  const blocks: Block[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];

    if (!line.trim()) {
      index += 1;
      continue;
    }

    const fence = FENCE.exec(line);
    if (fence) {
      const marker = fence[1];
      const body: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trimStart().startsWith(marker)) {
        body.push(lines[index]);
        index += 1;
      }
      index += 1;
      if (isDiagramTag(fence[2])) blocks.push({ kind: "diagram", code: body.join("\n") });
      else blocks.push({ kind: "code", code: body.join("\n"), language: languageOf(fence[2]) });
      continue;
    }

    if (DISPLAY_OPEN.test(line)) {
      const { tex, next } = takeDisplayMath(lines, index);
      index = next;
      // `$$$$` is not a formula, and an empty KaTeX block is an empty box on the card.
      if (tex) blocks.push({ kind: "math", tex });
      continue;
    }

    if (RULE.test(line)) {
      blocks.push({ kind: "rule" });
      index += 1;
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      blocks.push({ kind: "heading", level: heading[1].length, text: heading[2] });
      index += 1;
      continue;
    }

    if (QUOTE.test(line)) {
      const body: string[] = [];
      while (index < lines.length) {
        const quoted = QUOTE.exec(lines[index]);
        if (!quoted) break;
        body.push(quoted[1]);
        index += 1;
      }
      blocks.push({ kind: "quote", text: body.join("\n") });
      continue;
    }

    // A header row is only a table if the next line is the alignment rule; without that
    // check any prose containing a pipe would become a one-column table.
    if (line.includes("|") && index + 1 < lines.length && TABLE_RULE.test(lines[index + 1])) {
      const header = cells(line);
      const rows: string[][] = [];
      index += 2;
      while (index < lines.length && lines[index].includes("|") && lines[index].trim()) {
        rows.push(cells(lines[index]));
        index += 1;
      }
      blocks.push({ kind: "table", header, rows });
      continue;
    }

    const ordered = ORDERED.test(line);
    const pattern = UNORDERED.test(line) ? UNORDERED : ordered ? ORDERED : null;
    if (pattern) {
      const items: string[] = [];
      // Where the numbering starts. It is what saves a list that DID get split into two blocks
      // — because there is a paragraph or a code block in between — from starting again at 1 in
      // the second piece.
      const start = ordered ? Number(ORDERED.exec(line)![1]) : 1;
      while (index < lines.length) {
        const match = pattern.exec(lines[index]);
        if (match) {
          items.push(ordered ? match[2] : match[1]);
          index += 1;
          continue;
        }
        // A blank line does not close the list when what follows is still the same list. The model
        // separates the items with one break too many, and cutting there opened a new <ol> for each
        // item, all numbered from 1.
        if (!lines[index].trim()) {
          let ahead = index;
          while (ahead < lines.length && !lines[ahead].trim()) ahead += 1;
          if (ahead < lines.length && pattern.test(lines[ahead])) {
            index = ahead;
            continue;
          }
          break;
        }
        // A wrapped continuation line belongs to the item above it, not to a new block.
        if (items.length > 0 && !FENCE.test(lines[index])) {
          items[items.length - 1] += `\n${lines[index].trim()}`;
          index += 1;
          continue;
        }
        break;
      }
      blocks.push({ kind: "list", ordered, start, items });
      continue;
    }

    const paragraph: string[] = [];
    while (index < lines.length && lines[index].trim()) {
      const next = lines[index];
      if (FENCE.test(next) || HEADING.test(next) || RULE.test(next) || QUOTE.test(next)) break;
      if (UNORDERED.test(next) || ORDERED.test(next) || DISPLAY_OPEN.test(next)) break;
      paragraph.push(next);
      index += 1;
    }
    if (paragraph.length === 0) {
      index += 1;
      continue;
    }
    blocks.push({ kind: "paragraph", text: paragraph.join("\n") });
  }

  return blocks;
}

const INLINE =
  /(`+)([\s\S]+?)\1|\*\*([\s\S]+?)\*\*|__([\s\S]+?)__|(?<![\w*])\*(?!\s)([\s\S]+?)(?<!\s)\*|(?<![\w_])_(?!\s)([\s\S]+?)(?<!\s)_|~~([\s\S]+?)~~|\[([^\]]+)\]\(([^)\s]+)[^)]*\)/;

// What this renderer is handed is a generated item field or a bank statement — text a
// poisoned raw corpus reaches through the model — so a link's scheme is attacker input and
// `[pulsa aquí](javascript:…)` is a live anchor unless something says otherwise. The
// allowlist is that something: today only the CSP stands between that anchor and a click.
//
// Relative URLs stay allowed because they cost nothing to allow and cannot carry script;
// everything with a scheme has to be one of the three. The strip is not decoration — a
// browser removes C0 controls before it parses the scheme, so `java\x01script:` is a URL
// the allowlist would otherwise never recognise.
const SAFE_SCHEMES = new Set(["http", "https", "mailto"]);
const SCHEME = /^([a-zA-Z][a-zA-Z0-9+.-]*):/;

export function safeHref(href: string): string | null {
  const cleaned = href.replace(/[\u0000-\u0020\u007f]/g, "");
  const scheme = SCHEME.exec(cleaned);
  if (!scheme) return cleaned;
  return SAFE_SCHEMES.has(scheme[1].toLowerCase()) ? cleaned : null;
}

/**
 * Inline spans, with the formulas taken out first.
 *
 * The order is the whole point: `$q_{error}$` and `$(0|1)^*$` are full of characters the
 * markdown layer claims — `_`, `*`, `|` — and letting it in first turns a subscript into
 * emphasis and a Kleene closure into a bullet. Only the text BETWEEN formulas is markdown.
 */
function renderInline(text: string, key = "i"): ReactNode[] {
  const pieces = splitInlineMath(text);
  if (pieces.length > 1 || pieces.some((piece) => piece.kind === "math")) {
    return pieces.map((piece, i) =>
      piece.kind === "math" ? (
        <TeX key={`${key}-m${i}`} tex={piece.tex} />
      ) : (
        <Fragment key={`${key}-m${i}`}>{renderMarkup(piece.value, `${key}-m${i}`)}</Fragment>
      ),
    );
  }
  return renderMarkup(text, key);
}

/** The markdown spans proper, plus the newline-as-break rule the block layer relies on. */
function renderMarkup(text: string, key = "i"): ReactNode[] {
  const out: ReactNode[] = [];
  let rest = text;
  let n = 0;

  while (rest) {
    const match = INLINE.exec(rest);
    if (!match) {
      out.push(...withBreaks(rest, `${key}-${n}`));
      break;
    }
    if (match.index > 0) out.push(...withBreaks(rest.slice(0, match.index), `${key}-${n}t`));

    const id = `${key}-${n}`;
    const [, , code, strongStar, strongUnderscore, emStar, emUnderscore, strike, label, href] =
      match;

    if (code !== undefined) {
      out.push(
        <code
          key={id}
          className="rounded bg-muted px-1 py-0.5 font-mono text-[0.9em] text-foreground"
        >
          {code}
        </code>,
      );
    } else if (strongStar !== undefined || strongUnderscore !== undefined) {
      out.push(
        <strong key={id} className="font-semibold">
          {renderInline(strongStar ?? strongUnderscore, id)}
        </strong>,
      );
    } else if (emStar !== undefined || emUnderscore !== undefined) {
      out.push(<em key={id}>{renderInline(emStar ?? emUnderscore, id)}</em>);
    } else if (strike !== undefined) {
      out.push(
        <span key={id} className="line-through opacity-70">
          {renderInline(strike, id)}
        </span>,
      );
    } else if (label !== undefined) {
      const safe = safeHref(href);
      // A refused scheme keeps its label and loses only the link: the sentence a student
      // is reading still reads, and dropping the words would be the more visible damage.
      out.push(
        safe === null ? (
          <Fragment key={id}>{renderInline(label, id)}</Fragment>
        ) : (
          <a
            key={id}
            href={safe}
            target="_blank"
            rel="noreferrer noopener"
            className="text-primary underline underline-offset-2"
          >
            {renderInline(label, id)}
          </a>
        ),
      );
    }

    rest = rest.slice(match.index + match[0].length);
    n += 1;
  }

  return out;
}

function withBreaks(text: string, key: string): ReactNode[] {
  const parts = text.split("\n");
  return parts.map((part, i) => (
    <Fragment key={`${key}-${i}`}>
      {i > 0 ? <br /> : null}
      {part}
    </Fragment>
  ));
}

export function Markdown({
  children,
  className,
  codeMaxHeight = "20rem",
}: {
  children: string;
  className?: string;
  codeMaxHeight?: string;
}) {
  const blocks = useMemo(() => parseBlocks(children ?? ""), [children]);
  if (blocks.length === 0) return null;

  return (
    <div className={cn("space-y-2 text-body leading-relaxed break-words", className)}>
      {blocks.map((block, index) => {
        const key = `b${index}`;
        switch (block.kind) {
          case "code":
            return (
              <CodeBlock
                key={key}
                code={block.code}
                language={block.language}
                maxHeight={codeMaxHeight}
              />
            );
          case "diagram":
            return <Diagram key={key} code={block.code} />;
          case "heading": {
            const Tag = `h${Math.min(block.level + 2, 6)}` as "h3";
            return (
              <Tag
                key={key}
                className={cn(
                  "mt-3 font-semibold first:mt-0",
                  block.level <= 2 ? "text-[1.0625rem]" : "text-body",
                )}
              >
                {renderInline(block.text, key)}
              </Tag>
            );
          }
          case "list": {
            const Tag = block.ordered ? "ol" : "ul";
            return (
              <Tag
                key={key}
                start={block.ordered && block.start !== 1 ? block.start : undefined}
                className={cn(
                  "space-y-1 pl-5 marker:text-muted-foreground",
                  block.ordered ? "list-decimal" : "list-disc",
                )}
              >
                {block.items.map((item, i) => (
                  <li key={i}>{renderInline(item, `${key}-${i}`)}</li>
                ))}
              </Tag>
            );
          }
          case "quote":
            return (
              <blockquote
                key={key}
                className="border-l-2 border-border pl-3 text-muted-foreground"
              >
                {renderInline(block.text, key)}
              </blockquote>
            );
          case "table":
            return (
              <div key={key} className="thin-scroll overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-small">
                  <thead>
                    <tr className="border-b border-border bg-muted/40">
                      {block.header.map((cell, i) => (
                        <th key={i} className="px-2.5 py-1.5 text-left font-medium">
                          {renderInline(cell, `${key}-h${i}`)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {block.rows.map((row, r) => (
                      <tr key={r} className="border-b border-border last:border-0">
                        {row.map((cell, c) => (
                          <td key={c} className="px-2.5 py-1.5 align-top">
                            {renderInline(cell, `${key}-${r}-${c}`)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          case "math":
            return <TeX key={key} tex={block.tex} display />;
          case "rule":
            return <hr key={key} className="border-border" />;
          case "paragraph":
            return <p key={key}>{renderInline(block.text, key)}</p>;
        }
      })}
    </div>
  );
}
