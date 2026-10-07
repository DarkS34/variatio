import { CARD_CHOICE, CARD_CHOSEN, ChoiceMark } from "@/components/ui/choice";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Skeleton } from "@/components/ui/misc";
import { useRadioGroup } from "@/components/ui/radio";
import type { EngineSettings } from "@/features/admin/EngineSettings";
import { ENGINE_KINDS } from "@/features/admin/engineState";
import { settingHint } from "@/features/admin/hints";
import { useT } from "@/lib/i18n";
import { cn } from "@/lib/utils";

/**
 * WHICH ENGINE THE INSTALLATION RUNS, AS THE FIRST THING ON THE TAB.
 *
 * It used to be one row among the local settings, named after its variable, and it is the
 * one choice here that decides everything else: which models every phase names, whether a
 * remote half exists at all, where the corpus travels. So it is drawn as the two things
 * somebody actually chooses between and not as a select.
 *
 * It writes the tab's draft like every other setting, so choosing is not saving: the save
 * bar says what the change will swap before anything happens.
 */
export function EngineChoice({ config }: { config: EngineSettings }) {
  const { t } = useT();
  const setting = config.engine[0];
  const value = setting ? String(config.valueOf(setting) ?? "") : "";
  const choices = setting?.choices ?? [value];
  const radios = useRadioGroup(choices, value, (choice) => {
    if (setting) config.change(setting.key, choice);
  });
  if (config.loading) return <Skeleton className="h-36" />;
  if (!setting) return null;

  const pending = setting.key in config.draft;
  const lockedByEnv = setting.source === "env";
  const disabled = !setting.editable || lockedByEnv;
  const hintKey = settingHint(setting.key);

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle id="engine-choice-title">{t("eng.kind.title")}</CardTitle>
          {hintKey ? (
            <InfoHint label={t("cfg.hintLabel", { label: t("eng.kind.title") })}>{t(hintKey)}</InfoHint>
          ) : null}
        </div>
        <CardDescription>{t("eng.cfg.engineNote")}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-2">
        <div
          role="radiogroup"
          aria-labelledby="engine-choice-title"
          className="grid gap-3 sm:grid-cols-2"
          {...radios.group}
        >
          {choices.map((choice) => {
            const kind = ENGINE_KINDS[choice];
            const chosen = choice === value;
            return (
              <button
                key={choice}
                {...radios.radio(choice)}
                type="button"
                role="radio"
                aria-checked={chosen}
                disabled={disabled}
                onClick={() => config.change(setting.key, choice)}
                className={cn(
                  CARD_CHOICE,
                  "flex items-start gap-3 p-3",
                  chosen && CARD_CHOSEN,
                  chosen && pending && "ring-1 ring-attention",
                )}
              >
                {/* The square the mark is made of: filled is the one in force. */}
                <ChoiceMark chosen={chosen} className="mt-1.5" />
                <span className="min-w-0 space-y-0.5">
                  <span className="flex flex-wrap items-baseline gap-x-2">
                    <span className="font-expanded text-heading">
                      {kind ? t(kind.title) : choice}
                    </span>
                    {kind ? (
                      <span className="font-mono text-small text-muted-foreground">{choice}</span>
                    ) : null}
                  </span>
                  {kind ? (
                    <span className="block text-small text-muted-foreground">{t(kind.note)}</span>
                  ) : null}
                </span>
              </button>
            );
          })}
        </div>
        {lockedByEnv ? (
          <p className="text-small text-muted-foreground">
            {t("cfg.fixedBy", { env: setting.env ?? "" })}
          </p>
        ) : !setting.editable ? (
          <p className="text-small text-muted-foreground">{t("cfg.notEditable")}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
