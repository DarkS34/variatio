import { X } from "lucide-react";
import { useRef, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";

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
  const { t } = useT();
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
        className="h-6 rounded-full border border-primary bg-background px-2.5 text-small outline-none"
      />
    );
  }

  return (
    <Badge variant="secondary" className="h-6 py-0 pl-2.5 pr-1">
      <button
        type="button"
        onClick={() => setDraft(value)}
        title={t("chips.editValue")}
        className="max-w-56 truncate"
      >
        {value}
      </button>
      <button
        type="button"
        onClick={onRemove}
        aria-label={t("chips.remove", { value })}
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
  placeholder,
  hint,
  className,
  disabled = false,
  id,
  "aria-describedby": describedBy,
  "aria-label": ariaLabel,
}: {
  values: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  hint?: string;
  className?: string;
  disabled?: boolean;
  /** Forwarded to the inner <input> so that a <Field> wrapping this binds to something
   *  real. Without it the label would point at an id nothing carries, which looks correct
   *  in the markup and does nothing for a screen reader or for a click. */
  id?: string;
  "aria-describedby"?: string;
  "aria-label"?: string;
}) {
  const { t } = useT();
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
    setNotice(repeated.length > 0 ? t("chips.alreadyThere", { values: repeated.join(", ") }) : null);
    setText("");
    if (next.length !== values.length) onChange(next);
  };

  const commitAt = (index: number, value: string) => {
    if (!value) {
      onChange(values.filter((_, i) => i !== index));
      return;
    }
    if (values.some((other, i) => i !== index && other.toLowerCase() === value.toLowerCase())) {
      setNotice(t("chips.alreadyThere", { values: value }));
      return;
    }
    setNotice(null);
    onChange(values.map((other, i) => (i === index ? value : other)));
  };

  return (
    <div className={className}>
      <div
        onClick={() => (disabled ? undefined : inputRef.current?.focus())}
        className={cn(
          "flex min-h-9 w-full flex-wrap items-center gap-1.5 rounded-md border border-input bg-background p-1.5",
          "transition-colors focus-within:ring-2 focus-within:ring-ring",
          disabled && "bg-muted/40",
        )}
      >
        {values.map((value, index) =>
          disabled ? (
            <Badge key={`${index}-${value}`} variant="secondary" className="h-6 py-0">
              {value}
            </Badge>
          ) : (
            <Chip
              key={`${index}-${value}`}
              value={value}
              onCommit={(next) => commitAt(index, next)}
              onRemove={() => onChange(values.filter((_, i) => i !== index))}
            />
          ),
        )}
        {values.length === 0 && disabled ? (
          <span className="px-1 text-body text-muted-foreground">—</span>
        ) : null}
        <input
          hidden={disabled}
          disabled={disabled}
          ref={inputRef}
          id={id}
          aria-describedby={describedBy}
          aria-label={ariaLabel}
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
          placeholder={
            values.length === 0 ? (placeholder ?? t("chips.placeholder")) : t("chips.add")
          }
          className="h-6 min-w-32 flex-1 bg-transparent px-1 text-body outline-none placeholder:text-muted-foreground"
        />
      </div>
      {notice ? (
        <p className="mt-1 text-small text-attention">{notice}</p>
      ) : hint ? (
        <p className="mt-1 text-small text-muted-foreground">{hint}</p>
      ) : null}
    </div>
  );
}
