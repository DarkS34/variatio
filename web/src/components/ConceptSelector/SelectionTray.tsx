import { Check, Lock, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";

export function SelectionTray({
  selected,
  implied,
  total,
  colourFor,
  onRemove,
  onClear,
  onConfirm,
  confirmLabel,
  hidden = 0,
  onShowHidden,
}: {
  selected: string[];
  implied: string[];
  total: number;
  /** How many concepts the exemplar filter is keeping out of the board. */
  hidden?: number;
  /** Lifts that filter, when the caller has one to lift. */
  onShowHidden?: () => void;
  colourFor: (concept: string) => string | undefined;
  onRemove: (concept: string) => void;
  onClear: () => void;
  onConfirm: () => void;
  confirmLabel: string;
}) {
  const { t, plural } = useT();
  // `total` counts what is on offer, which for every current caller includes everything
  // selected; a caller that broke that invariant would otherwise be announced as having
  // chosen more concepts than exist.
  const offered = Math.max(total, selected.length);
  return (
    <footer className="shrink-0 border-t border-border bg-card/95 px-4 py-3 backdrop-blur sm:px-6">
      <div className="mx-auto flex max-w-[110rem] flex-col gap-2">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-small text-muted-foreground">
            <span className="text-body font-semibold nums text-foreground">
              {selected.length}
            </span>{" "}
            {plural("tray.chosenOf", offered)}
            {implied.length > 0 ? (
              <span className="text-primary">{t("tray.byPrerequisite", { n: implied.length })}</span>
            ) : null}
            {/* WHAT IS NOT ON THE BOARD, SAID ON THE BOARD. The exemplar filter is on by
                default and its switch lives in the step BEHIND this overlay, so «0 de 42»
                was the whole truth a person had: the graph has 162 concepts and nothing
                here said the other 120 existed. */}
            {hidden > 0 ? (
              <>
                {" · "}
                <button
                  type="button"
                  onClick={onShowHidden}
                  className="underline underline-offset-4 hover:text-foreground"
                >
                  {plural("tray.hiddenNoExemplars", hidden)}
                </button>
              </>
            ) : null}
          </p>
          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={onClear}
              disabled={selected.length === 0}
              title={t("concept.clearAll")}
            >
              {t("common.clear")}
            </Button>
            <Button size="sm" onClick={onConfirm}>
              <Check />
              {confirmLabel}
            </Button>
          </div>
        </div>

        <div className="thin-scroll max-h-24 overflow-y-auto">
          <div className="flex flex-wrap items-center gap-1.5">
            {selected.length === 0 ? (
              <span className="text-body text-muted-foreground">{t("concept.noneChosen")}</span>
            ) : (
              selected.map((name) => (
                <Badge key={name} variant="secondary" className="pr-1">
                  <span
                    className="size-1.5 shrink-0 rounded-full"
                    style={{ background: colourFor(name) }}
                  />
                  <span className="max-w-64 truncate">{name}</span>
                  <button
                    type="button"
                    onClick={() => onRemove(name)}
                    aria-label={t("concept.remove", { name })}
                    className="rounded-full p-0.5 hover:bg-background/60"
                  >
                    <X className="size-3" />
                  </button>
                </Badge>
              ))
            )}
          </div>
        </div>

        {implied.length > 0 ? (
          <div className="thin-scroll max-h-20 overflow-y-auto border-t border-dashed border-border pt-2">
            <div className="flex flex-wrap items-center gap-1.5">
              <span className="mr-1 text-micro font-medium uppercase tracking-wide text-muted-foreground">
                {t("tray.byPrerequisiteLabel")}
              </span>
              {implied.map((name) => (
                <Badge
                  key={name}
                  className="border-dashed border-primary/40 bg-primary/10 text-primary/80"
                  title={t("concept.byPrerequisite")}
                >
                  <Lock className="size-3 shrink-0" />
                  <span className="max-w-64 truncate">{name}</span>
                </Badge>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </footer>
  );
}
