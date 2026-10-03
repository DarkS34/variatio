import { ArrowUp, ListTree } from "lucide-react";
import { useLayoutEffect, useRef, type KeyboardEvent } from "react";

import { Button } from "@/components/ui/button";
import { ConceptChip } from "@/components/ui/concept-chip";
import { Spinner } from "@/components/ui/misc";
import { useT } from "@/lib/i18n";

import type { SyllabusUnit } from "./syllabus";
import { TopicPicker } from "./TopicPicker";

// The box grows with what is written up to this height, then scrolls inside itself.
const COMPOSER_MAX_PX = 192;

/** Whether the picker is open, and on which unit when something asked for one. */
export type Picking = { unit: number | null } | null;

/**
 * THE BOX TO WRITE IN, AND THE LINE THAT SAYS WHAT THE MESSAGE IS ABOUT.
 *
 * Two rows in one frame. The upper one — «Sobre» — always shows what the tutor takes the
 * conversation to be about: the concept the student chose for the message being written
 * (filled, removable), else the concepts the conversation already stands on (quiet). It is
 * where a wrong guess is seen and corrected, and where the picker opens. Choosing is never
 * required: with nothing chosen the tutor deduces the concept from the message, and the row
 * says so in a word.
 *
 * The lower row is the message and its send button. Enter sends and Shift+Enter breaks the
 * line, as in every chat. A key pressed while an input method is composing a character
 * belongs to that character, so it never sends.
 *
 * A concept chosen with nothing written yet still needs a question, and the commonest one is
 * the same every time. So the empty box offers it — «Explícame «…»» as its placeholder —
 * and Tab writes it, as a completion is accepted everywhere; the key drawn beside it does
 * the same under a finger. Tab is taken ONLY then: with any text in the box, or no concept
 * chosen, it moves the focus on as it always does.
 */
export function Composer({
  value,
  onChange,
  onSubmit,
  disabled,
  canSend,
  sending,
  units,
  focus,
  chosen,
  onChosen,
  picking,
  onPicking,
}: {
  value: string;
  onChange: (value: string) => void;
  onSubmit: () => void;
  disabled: boolean;
  canSend: boolean;
  sending: boolean;
  /** The syllabus to choose from; empty when it could not be read, and then nothing is offered. */
  units: SyllabusUnit[];
  /** The concepts the conversation stands on, as the server last said. */
  focus: string[];
  chosen: string | null;
  onChosen: (concept: string | null) => void;
  picking: Picking;
  onPicking: (picking: Picking) => void;
}) {
  const { t } = useT();
  const box = useRef<HTMLTextAreaElement>(null);
  const trigger = useRef<HTMLSpanElement>(null);

  useLayoutEffect(() => {
    const node = box.current;
    if (!node) return;
    node.style.height = "auto";
    node.style.height = `${Math.min(node.scrollHeight, COMPOSER_MAX_PX)}px`;
  }, [value]);

  const suggestion =
    chosen && value === "" ? t("tutor.composer.suggestion", { name: chosen }) : null;
  const accept = () => {
    if (!suggestion) return;
    onChange(suggestion);
    box.current?.focus();
  };

  const onKey = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.nativeEvent.isComposing) return;
    const bare = !event.shiftKey && !event.altKey && !event.ctrlKey && !event.metaKey;
    if (event.key === "Tab" && bare && suggestion) {
      event.preventDefault();
      accept();
    } else if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      onSubmit();
    }
  };

  const close = () => onPicking(null);
  const pick = (concept: string) => {
    onChosen(concept);
    close();
    box.current?.focus();
  };
  const offered = units.length > 0;
  const about = chosen ? [chosen] : focus;

  return (
    <div className="relative">
      {picking && offered ? (
        <TopicPicker
          units={units}
          chosen={chosen}
          current={focus}
          startUnit={picking.unit}
          anchor={trigger}
          onPick={pick}
          onClose={() => {
            close();
            box.current?.focus();
          }}
        />
      ) : null}

      <div className="rounded-lg border border-input bg-background transition-colors focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-1 focus-within:ring-offset-background">
        {offered || about.length > 0 ? (
          <div className="flex min-h-9 flex-wrap items-center gap-x-2 gap-y-1 border-b border-border px-2.5 py-1">
            <span className="shrink-0 text-micro font-condensed uppercase text-muted-foreground">
              {t("tutor.topic.label")}
            </span>
            {chosen ? (
              <ConceptChip
                tone="primary"
                onRemove={() => onChosen(null)}
                removeLabel={t("tutor.topic.remove", { name: chosen })}
              >
                {chosen}
              </ConceptChip>
            ) : (
              focus.map((name) => <ConceptChip key={name}>{name}</ConceptChip>)
            )}
            {offered ? (
              // The span is what the picker knows as its opener: `Button` takes no ref.
              <span ref={trigger} className="inline-flex">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2"
                  aria-haspopup="dialog"
                  aria-expanded={Boolean(picking)}
                  disabled={disabled}
                  onClick={() => onPicking(picking ? null : { unit: null })}
                >
                  <ListTree />
                  {t(about.length > 0 ? "tutor.topic.change" : "tutor.topic.choose")}
                </Button>
              </span>
            ) : null}
            {offered && about.length === 0 ? (
              <span className="text-small text-muted-foreground">{t("tutor.topic.optional")}</span>
            ) : null}
          </div>
        ) : null}

        <div className="flex items-end gap-2 p-1.5">
          <textarea
            ref={box}
            aria-label={t("tutor.composer.label")}
            rows={1}
            value={value}
            placeholder={suggestion ?? t("tutor.composer.placeholder")}
            onChange={(event) => onChange(event.target.value)}
            onKeyDown={onKey}
            onFocus={() => picking && close()}
            disabled={disabled}
            // The focus is drawn once, by the frame around both rows (`focus-within`
            // above). The stylesheet's floor rule for a bare textarea is unlayered, so no
            // utility switches it off and it drew a second frame inside.
            style={{ outline: "none" }}
            className="thin-scroll min-h-9 flex-1 resize-none overflow-y-auto bg-transparent px-2 py-1.5 text-body leading-relaxed placeholder:text-muted-foreground disabled:cursor-not-allowed disabled:opacity-50"
          />
          {suggestion && !disabled ? (
            <button
              type="button"
              onClick={accept}
              title={t("tutor.composer.useSuggestion", { text: suggestion })}
              aria-label={t("tutor.composer.useSuggestion", { text: suggestion })}
              className="mb-1.5 shrink-0 border border-border px-1.5 py-0.5 font-mono text-small text-muted-foreground transition-colors hover:bg-accent hover:text-foreground"
            >
              {t("tutor.composer.tab")}
            </button>
          ) : null}
          <Button
            variant="attention"
            size="icon"
            className="shrink-0"
            aria-label={t("tutor.composer.send")}
            title={t("tutor.composer.send")}
            disabled={!canSend}
            onClick={onSubmit}
          >
            {sending ? <Spinner className="size-4" /> : <ArrowUp />}
          </Button>
        </div>
      </div>
    </div>
  );
}
