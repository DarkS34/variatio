import { Check, Cpu, ExternalLink, Rabbit, Turtle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

import { familyOf } from "./models";

/**
 * Which of the offered models writes the item, chosen before how hard it thinks.
 *
 * The two questions are asked in that order because the second depends on the first: the
 * levels a model accepts, and what is worth warning about at each of them, are the model's
 * (`models.ts`), so picking a writer after setting the effort would silently re-clamp it.
 *
 * It is drawn as cards and not as a dropdown because what separates two models here is not
 * their names — it is a trade-off in one sentence, and a select can hold a name and nothing
 * else. The link is OUTSIDE the button rather than inside it: an anchor nested in a button
 * is not a control a browser can resolve, and reading about a model is not choosing it.
 *
 * It renders nothing at all when the installation offers a single model, for the same
 * reason the bank hides its modality filter with one modality declared: a choice of one is
 * not a choice, and the reasoning block below still names the model that will write.
 */
export function ModelChoice({
  offered,
  remote,
  missing,
  value,
  onChange,
}: {
  offered: string[];
  remote: string[];
  missing: string[];
  value: string;
  onChange: (model: string) => void;
}) {
  const { t } = useT();
  if (offered.length < 2) return null;

  return (
    <div className="space-y-2 rounded-lg border border-border bg-muted/30 px-2.5 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 text-body font-medium">
          <Cpu className="size-3.5" />
          {t("form.model.title")}
        </span>
      </div>

      <div
        role="group"
        aria-label={t("form.model.title")}
        className="grid gap-2 sm:grid-cols-2"
      >
        {offered.map((model) => (
          <ModelCard
            key={model}
            model={model}
            active={model === value}
            remote={remote.includes(model)}
            missing={missing.includes(model)}
            onChoose={() => onChange(model)}
          />
        ))}
      </div>
    </div>
  );
}

function ModelCard({
  model,
  active,
  remote,
  missing,
  onChoose,
}: {
  model: string;
  active: boolean;
  remote: boolean;
  missing: boolean;
  onChoose: () => void;
}) {
  const { t } = useT();
  const family = familyOf(model);
  const Speed = family.speed === "fast" ? Rabbit : Turtle;

  return (
    <div
      className={cn(
        "flex flex-col overflow-hidden border transition-colors",
        active ? "border-primary bg-primary/5" : "border-border",
      )}
    >
      <button
        type="button"
        aria-pressed={active}
        onClick={onChoose}
        className={cn(
          "flex-1 p-2.5 text-left transition-colors",
          !active && "hover:bg-accent/40",
        )}
      >
        <span className="flex items-center gap-1.5">
          {active ? <Check className="size-3.5 shrink-0 text-primary" /> : null}
          <span className="text-body font-medium">{family.label || model}</span>
          {family.speed ? (
            <span className="ml-auto flex shrink-0 items-center gap-1 text-micro font-condensed uppercase tracking-wide text-muted-foreground">
              <Speed className="size-3.5" />
              {t(family.speed === "fast" ? "form.model.fast" : "form.model.slow")}
            </span>
          ) : null}
        </span>

        <span className="mt-0.5 flex flex-wrap items-center gap-1.5">
          <span className="font-mono text-[11px] text-muted-foreground">{model}</span>
          {remote ? <Badge variant="outline">{t("form.model.remote")}</Badge> : null}
        </span>

        {family.blurbKey ? (
          <span className="mt-1 block text-small text-muted-foreground">
            {t(family.blurbKey)}
          </span>
        ) : null}

        {/* Offering a model does not download it: the installation names it and the engine
            may simply not have it, in which case the first call is where one would find
            out. Said here instead. */}
        {missing ? (
          <span className="mt-1 block text-small text-destructive">
            {t("form.model.missing")}
          </span>
        ) : null}
      </button>

      {family.url ? (
        <a
          href={family.url}
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-1.5 border-t border-border px-2.5 py-1.5 text-small text-muted-foreground transition-colors hover:text-foreground"
        >
          <ExternalLink className="size-3.5 shrink-0" />
          {t("form.model.readMore")}
        </a>
      ) : null}
    </div>
  );
}
