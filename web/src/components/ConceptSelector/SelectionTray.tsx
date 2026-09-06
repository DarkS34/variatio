import { Check } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ConceptChip } from "@/components/ui/concept-chip";
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
}: {
  selected: string[];
  /**
   * What the graph places before the chosen concepts. Reported and never withheld: these
   * are pickable like any other, so it is a statement about the choice and not the
   * explanation of a refusal.
   */
  implied: string[];
  total: number;
  /** How many concepts the exemplar scope is keeping out of the board. */
  hidden?: number;
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
            {/* What is not on the board, said on the board: without it "0 de 42" is the
                whole truth a person has over a graph of 162 concepts. The count is the
                statement; the lever is the scope switch in the header alone. */}
            {hidden > 0 ? (
              <span>
                {" · "}
                {plural("tray.hiddenNoExemplars", hidden)}
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
                <ConceptChip
                  key={name}
                  tone="primary"
                  colour={colourFor(name)}
                  onRemove={() => onRemove(name)}
                  removeLabel={t("concept.remove", { name })}
                >
                  {name}
                </ConceptChip>
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
                <ConceptChip key={name} tone="prerequisite" title={t("concept.byPrerequisite")}>
                  {name}
                </ConceptChip>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </footer>
  );
}
