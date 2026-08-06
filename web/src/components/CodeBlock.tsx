import { Check, Copy } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const KEYWORDS =
  /\b(and|as|assert|async|await|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|True|try|while|with|yield|self|print|range|len|int|str|float|bool|list|dict|set|tuple|input)\b/;

type Token = { text: string; kind: string };

/**
 * A deliberately small Python highlighter.
 *
 * Solutions in this corpus are short teaching snippets; pulling in a full grammar
 * engine to colour them would cost more than it returns. Tokenising in one pass keeps
 * strings and comments from being re-highlighted, which is where naive regex colouring
 * usually falls apart.
 */
function tokenize(source: string): Token[] {
  const tokens: Token[] = [];
  let index = 0;

  while (index < source.length) {
    const rest = source.slice(index);

    const comment = /^#[^\n]*/.exec(rest);
    if (comment) {
      tokens.push({ text: comment[0], kind: "comment" });
      index += comment[0].length;
      continue;
    }

    const string = /^("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')/.exec(rest);
    if (string) {
      tokens.push({ text: string[0], kind: "string" });
      index += string[0].length;
      continue;
    }

    const number = /^\b\d+(\.\d+)?\b/.exec(rest);
    if (number) {
      tokens.push({ text: number[0], kind: "number" });
      index += number[0].length;
      continue;
    }

    const word = /^[A-Za-z_]\w*/.exec(rest);
    if (word) {
      tokens.push({ text: word[0], kind: KEYWORDS.test(word[0]) ? "keyword" : "plain" });
      index += word[0].length;
      continue;
    }

    tokens.push({ text: rest[0], kind: /[=+\-*/%<>!,:]/.test(rest[0]) ? "operator" : "plain" });
    index += 1;
  }

  return tokens;
}

const COLOURS: Record<string, string> = {
  comment: "text-muted-foreground italic",
  string: "text-[var(--code-string)]",
  number: "text-[var(--code-number)]",
  keyword: "text-primary font-medium",
  operator: "text-muted-foreground",
  plain: "",
};

export function CodeBlock({
  code,
  language = "python",
  className,
  maxHeight = "24rem",
}: {
  code: string;
  language?: "python" | "text" | "json";
  className?: string;
  maxHeight?: string;
}) {
  const [copied, setCopied] = useState(false);
  const tokens = useMemo(
    () => (language === "python" ? tokenize(code) : [{ text: code, kind: "plain" }]),
    [code, language],
  );

  const copy = async () => {
    await navigator.clipboard.writeText(code);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1400);
  };

  return (
    <div className={cn("group relative rounded-lg border border-border bg-muted/40", className)}>
      <Button
        variant="ghost"
        size="icon-sm"
        onClick={copy}
        aria-label="Copiar"
        className="absolute right-1.5 top-1.5 opacity-0 transition-opacity group-hover:opacity-100 focus-visible:opacity-100"
      >
        {copied ? <Check className="text-[var(--success)]" /> : <Copy />}
      </Button>
      <pre
        className="thin-scroll overflow-auto p-3 font-mono text-xs leading-relaxed"
        style={{ maxHeight }}
      >
        <code>
          {tokens.map((token, i) => (
            <span key={i} className={COLOURS[token.kind]}>
              {token.text}
            </span>
          ))}
        </code>
      </pre>
    </div>
  );
}
