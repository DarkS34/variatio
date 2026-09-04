import { Check, X } from "lucide-react";

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
  onShowAll,
}: {
  selected: string[];
  /**
   * What the graph places before the chosen concepts. Reported, never withheld: since
   * 2026-09-04 these are pickable like any other, so this is a statement about the choice
   * and not the explanation of a refusal.
   */
  implied: string[];
  total: number;
  /** How many concepts the exemplar scope is keeping out of the board. */
  hidden?: number;
  /** Lifts that scope. Drawn beside the count, where the absence is felt. */
  onShowAll?: () => void;
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
            {/* WHAT IS NOT ON THE BOARD, SAID ON THE BOARD. Without it «0 de 42» is the
                whole truth a person has, over a graph of 162 concepts. The count is the
                statement and the link beside it is the lever — the same one the header's
                scope switch holds, repeated here because this is where the absence is
                felt. */}
            {hidden > 0 ? (
              <span>
                {" · "}
                {plural("tray.hiddenNoExemplars", hidden)}
                {onShowAll ? (
                  <>
                    {" · "}
                    <button
                      type="button"
                      onClick={onShowAll}
                      className="font-medium text-attention underline-offset-2 hover:underline"
                    >
                      {t("tray.showAll")}
                    </button>
                  </>
                ) : null}
              </span>
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
                  className="border-dashed border-primary/50 bg-primary/10 text-primary"
                  title={t("concept.byPrerequisite")}
                >
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
