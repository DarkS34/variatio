import { X } from "lucide-react";
import { useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

const SEPARATORS = /[\n,;]+/;

function Chip({
  value,
  onCommit,
  onRemove,
}: {
  value: string;
  onCommit: (next: string) => void;
  onRemove: () => void;
}) {
  const [draft, setDraft] = useState<string | null>(null);
  const cancelled = useRef(false);

  if (draft !== null) {
    return (
      <input
        autoFocus
        value={draft}
        onChange={(event) => setDraft(event.target.value)}
        onBlur={() => {
          if (!cancelled.current) onCommit(draft.trim());
          cancelled.current = false;
          setDraft(null);
        }}
        onKeyDown={(event) => {
          if (event.key === "Enter") event.currentTarget.blur();
          if (event.key === "Escape") {
            cancelled.current = true;
            event.currentTarget.blur();
          }
        }}
        style={{ width: `${Math.max(draft.length, 4) + 2}ch` }}
        className="h-6 rounded-full border border-primary bg-background px-2.5 text-xs outline-none"
      />
    );
  }

  return (
    <Badge variant="secondary" className="h-6 py-0 pl-2.5 pr-1">
      <button
        type="button"
        onClick={() => setDraft(value)}
        title="Editar valor"
        className="max-w-56 truncate"
      >
        {value}
      </button>
      <button
        type="button"
        onClick={onRemove}
        aria-label={`Quitar ${value}`}
        className="rounded-full p-0.5 text-muted-foreground transition-colors hover:bg-background/70 hover:text-foreground"
      >
        <X className="size-3" />
      </button>
    </Badge>
  );
}

export function ChipInput({
  values,
  onChange,
  placeholder = "Escribe un valor y pulsa Enter…",
  hint,
  className,
}: {
  values: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  hint?: string;
  className?: string;
}) {
  const [text, setText] = useState("");
  const [notice, setNotice] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const add = (raw: string) => {
    const parts = raw
      .split(SEPARATORS)
      .map((part) => part.trim())
      .filter(Boolean);
    if (parts.length === 0) {
      setText("");
      return;
    }
    const next = [...values];
    const repeated: string[] = [];
    for (const part of parts) {
      if (next.some((value) => value.toLowerCase() === part.toLowerCase())) repeated.push(part);
      else next.push(part);
    }
    setNotice(repeated.length > 0 ? `Ya estaba en la lista: ${repeated.join(", ")}` : null);
    setText("");
    if (next.length !== values.length) onChange(next);
  };

  const commitAt = (index: number, value: string) => {
    if (!value) {
      onChange(values.filter((_, i) => i !== index));
      return;
    }
    if (values.some((other, i) => i !== index && other.toLowerCase() === value.toLowerCase())) {
      setNotice(`Ya estaba en la lista: ${value}`);
      return;
    }
    setNotice(null);
    onChange(values.map((other, i) => (i === index ? value : other)));
  };

  return (
    <div className={className}>
      <div
        onClick={() => inputRef.current?.focus()}
        className={cn(
          "flex min-h-9 w-full flex-wrap items-center gap-1.5 rounded-md border border-input bg-background p-1.5",
          "transition-colors focus-within:ring-2 focus-within:ring-ring",
        )}
      >
        {values.map((value, index) => (
          <Chip
            key={`${index}-${value}`}
            value={value}
            onCommit={(next) => commitAt(index, next)}
            onRemove={() => onChange(values.filter((_, i) => i !== index))}
          />
        ))}
        <input
          ref={inputRef}
          value={text}
          onChange={(event) => setText(event.target.value)}
          onBlur={() => add(text)}
          onPaste={(event) => {
            const pasted = event.clipboardData.getData("text");
            if (!SEPARATORS.test(pasted)) return;
            event.preventDefault();
            add(text + pasted);
          }}
          onKeyDown={(event) => {
            if (event.key === "Enter" || event.key === ",") {
              event.preventDefault();
              add(text);
            } else if (event.key === "Backspace" && text === "" && values.length > 0) {
              event.preventDefault();
              onChange(values.slice(0, -1));
            }
          }}
          placeholder={values.length === 0 ? placeholder : "añadir…"}
          className="h-6 min-w-32 flex-1 bg-transparent px-1 text-sm outline-none placeholder:text-muted-foreground"
        />
      </div>
      {notice ? (
        <p className="mt-1 text-xs text-[var(--warning)]">{notice}</p>
      ) : hint ? (
        <p className="mt-1 text-xs text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}
