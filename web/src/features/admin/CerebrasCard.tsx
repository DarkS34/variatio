import { Download, Timer } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Alert, Progress } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import type { CerebrasModel, CerebrasState } from "@/lib/types";
import { cerebrasState } from "@/features/admin/engineState";
import { useT } from "@/lib/i18n";

/**
 * The remote half of the engine, which the rest of this tab cannot describe.
 *
 * Everything else here is about the one GPU — what is resident on it, the tunnel that
 * reaches it, the models on its disk. None of that says anything about Cerebras, where
 * there are no weights to load and nothing to free, and where what limits the work is not
 * memory but a rate limit measured in requests and tokens per window.
 *
 * WHAT THE METERS ARE FOR is one question: am I about to be held back, and by which
 * window. So the four run first and the per-phase breakdown sits under them as support —
 * it answers what comes next ("which phase is eating it") and leaves in a spreadsheet.
 *
 * Colour follows the palette's own rule rather than a severity scale: a meter is ink while
 * it is merely a quantity, --attention on the ONE window currently holding a call back
 * (that is literally "act here"), and --destructive only when a call is being refused.
 * Tinting every near-full meter would spend colour on something nobody can act on.
 */
export function CerebrasCard({ cerebras }: { cerebras: CerebrasState }) {
  const { t } = useT();
  const state = cerebrasState(cerebras);

  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center gap-2">
          <CardTitle>Cerebras</CardTitle>
          <Badge variant={state.tone}>{t(state.labelKey)}</Badge>
          <InfoHint label={t("cere.budgetHint")}>
            {t("cere.budgetHint.body1")}
            <br />
            <br />
            {t("cere.budgetHint.body2")}
          </InfoHint>
        </div>
        <CardDescription>
          {cerebras.routed.length > 0 ? (
            <span className="font-mono">{cerebras.routed.join(", ")}</span>
          ) : (
            t("cere.noRouted")
          )}
          {cerebras.configured ? "" : t("cere.noKeyEnv")}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        <Flight cerebras={cerebras} />
        {cerebras.usage.length === 0 ? (
          <p className="text-small text-muted-foreground">
            {t("cere.nothingSpent")}
          </p>
        ) : (
          cerebras.usage.map((entry) => (
            <ModelBudget key={entry.model} entry={entry} single={cerebras.usage.length === 1} />
          ))
        )}
      </CardContent>
    </Card>
  );
}

/* What is happening right now ------------------------------------------------------------ */

// The strip is the whole point of the card being live rather than a report: a build that
// looks frozen is usually a build being held twelve seconds at a time, and there was no
// screen in the application that could say so.
function Flight({ cerebras }: { cerebras: CerebrasState }) {
  const { t } = useT();
  const flying = cerebras.inflight;
  if (!flying) {
    return (
      // A strip the block holds, so a well (it was a bordered box, the last of the tab).
      <div className="well flex items-center gap-3 px-3 py-2.5 text-small text-muted-foreground">
        <span className="size-2 rounded-full bg-muted-foreground/40" />
        {t("cere.noCalls")}
      </div>
    );
  }

  const held = flying.waiting_until != null ? Math.max(0, flying.waiting_until - Date.now() / 1000) : 0;
  const waiting = flying.waiting_until != null;
  const others = Math.max(0, (cerebras.inflight_count ?? 1) - 1);

  return (
    <div
      className={
        waiting
          ? "well flex flex-wrap items-center gap-3 bg-[color-mix(in_oklab,var(--attention)_8%,var(--card))] px-3 py-2.5"
          : "well flex flex-wrap items-center gap-3 px-3 py-2.5"
      }
    >
      <span
        className={
          waiting
            ? "size-2 shrink-0 animate-pulse rounded-full bg-attention-fill"
            : "size-2 shrink-0 animate-pulse rounded-full bg-primary"
        }
      />
      <span className="font-mono text-small">{flying.model}</span>
      {flying.phase ? (
        <>
          <span className="text-muted-foreground">·</span>
          <span className="text-small text-muted-foreground">{flying.phase}</span>
        </>
      ) : null}
      {/* The strip draws ONE call, and since the remote lane got room there can be several:
          saying how many are behind this one is the difference between a slow phase and
          four jobs sharing the quota. Absent from an API older than this bundle. */}
      {others > 0 ? (
        <>
          <span className="text-muted-foreground">·</span>
          <span className="nums text-small text-muted-foreground">
            {t("cere.alsoFlying", { n: others })}
          </span>
        </>
      ) : null}
      <span className="grow" />
      {waiting ? (
        <span className="nums flex items-center gap-1.5 text-small font-semibold text-attention">
          <Timer className="size-3.5" />
          {t("cere.leavesIn", { n: Math.ceil(held) })}
        </span>
      ) : (
        <span className="nums text-small text-muted-foreground">
          {flying.elapsed.toFixed(1)} s
        </span>
      )}
    </div>
  );
}

/* The four meters, and the breakdown under them ------------------------------------------- */

function ModelBudget({ entry, single }: { entry: CerebrasModel; single: boolean }) {
  const { t } = useT();
  const day = entry.windows.day;
  const exhausted = day.requests_remaining <= 0 || day.tokens_remaining <= 0;

  return (
    <div className="space-y-4">
      {single ? null : <p className="font-mono text-small font-semibold">{entry.model}</p>}

      {exhausted ? (
        <Alert tone="danger" title={t("cere.refusing")}>
          {t("cere.refusing.body", { hours: hours(day.resets_in) })}
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <Meter
          label={t("cere.meter.requestsMinute")}
          used={entry.windows.minute.requests_used}
          limit={entry.windows.minute.requests_limit}
          remaining={entry.windows.minute.requests_remaining}
          resets={entry.windows.minute.resets_in}
          rolling={t("cere.rolling.window")}
        />
        <Meter
          label={t("cere.meter.tokensMinute")}
          used={entry.windows.minute.tokens_used}
          limit={entry.windows.minute.tokens_limit}
          remaining={entry.windows.minute.tokens_remaining}
          resets={entry.windows.minute.resets_in}
          rolling={t("cere.rolling.window")}
        />
        <Meter
          label={t("cere.meter.requestsDay")}
          used={day.requests_used}
          limit={day.requests_limit}
          remaining={day.requests_remaining}
          resets={day.resets_in}
          rolling={t("cere.rolling.day")}
          daily
        />
        <Meter
          label={t("cere.meter.tokensDay")}
          used={day.tokens_used}
          limit={day.tokens_limit}
          remaining={day.tokens_remaining}
          resets={day.resets_in}
          rolling={t("cere.rolling.day")}
          daily
        />
      </div>

      <Breakdown entry={entry} />
    </div>
  );
}

function Meter({
  label,
  used,
  limit,
  remaining,
  resets,
  rolling,
  daily = false,
}: {
  label: string;
  used: number;
  limit: number;
  remaining: number;
  resets: number;
  rolling: string;
  daily?: boolean;
}) {
  const { t, language } = useT();
  // Three tones and no gradient between them, because the middle of a meter is not a state
  // anybody can act on: ink while there is room, attention when this window is the one with
  // nothing left, red when it is a daily one and therefore a refusal rather than a wait.
  const tone = remaining > 0 ? "primary" : daily ? "danger" : "attention";
  const emphasis =
    remaining > 0 ? "" : daily ? "text-destructive" : "text-attention";

  return (
    <div className="space-y-1.5">
      <p className={`text-micro font-condensed uppercase text-muted-foreground ${emphasis}`}>
        {label}
      </p>
      <p className={`nums text-title ${emphasis}`}>
        {used.toLocaleString(language)}{" "}
        <span className="text-small font-normal text-muted-foreground">
          {t("cere.ofLimit", { limit: limit.toLocaleString(language) })}
        </span>
      </p>
      <Progress value={used} max={limit} tone={tone} />
      <p className={`nums text-small text-muted-foreground ${emphasis}`}>
        {remaining <= 0
          ? t("cere.exhaustedIn", {
              rolling: rolling.toLowerCase(),
              time: daily ? hours(resets) : `${Math.ceil(resets)} s`,
            })
          : daily
            ? t("cere.slidingDay")
            : resets > 0
              ? t("cere.resetsIn", { rolling, n: Math.ceil(resets) })
              : t("cere.noCallsLastMinute")}
      </p>
    </div>
  );
}

// Secondary on purpose: it answers the question AFTER the meters, and the meters are what
// somebody opens this card to see. The bar compares each phase against the largest one and
// not against the day — at the day's scale every row but the first would be invisible.
function Breakdown({ entry }: { entry: CerebrasModel }) {
  const { t, language } = useT();
  if (entry.phases.length === 0) return null;
  const top = entry.phases[0].tokens || 1;
  const ceiling = entry.windows.day.tokens_limit || 1;

  return (
    <div className="space-y-2 border-t border-border pt-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-micro font-condensed uppercase text-muted-foreground">
            {t("cere.byPhase")}
          </p>
          <p className="text-small text-muted-foreground">{t("cere.byPhase.sub")}</p>
        </div>
        {/* A link that downloads, drawn as the outline button every other CSV is. */}
        <a
          className={buttonVariants({ variant: "outline", size: "sm" })}
          href="/api/admin/engine/cerebras/export.csv"
          download
        >
          <Download />
          {t("cere.downloadCsv")}
        </a>
      </div>
      <Table>
        <THead>
          <TR>
            <TH>{t("cere.col.phase")}</TH>
            <TH className="text-right">{t("cere.col.requests")}</TH>
            <TH className="text-right">{t("cere.col.tokens")}</TH>
            <TH className="text-right">{t("cere.col.ofDay")}</TH>
          </TR>
        </THead>
        <TBody>
          {entry.phases.map((row) => (
            <TR key={row.phase}>
              <TD className="font-mono">{row.phase}</TD>
              <TD className="nums text-right">{row.requests.toLocaleString(language)}</TD>
              <TD className="nums text-right">{row.tokens.toLocaleString(language)}</TD>
              <TD>
                <div className="flex items-center justify-end gap-2">
                  <span className="h-1 w-11 bg-primary/10">
                    <span
                      className="block h-full bg-settled"
                      style={{ width: `${Math.max(2, (row.tokens * 100) / top)}%` }}
                    />
                  </span>
                  <span className="nums w-12 text-right">
                    {((row.tokens * 100) / ceiling).toFixed(1).replace(".", ",")} %
                  </span>
                </div>
              </TD>
            </TR>
          ))}
        </TBody>
      </Table>
    </div>
  );
}

function hours(seconds: number): string {
  if (seconds < 90) return `${Math.ceil(seconds)} s`;
  if (seconds < 5_400) return `${Math.round(seconds / 60)} min`;
  return `${(seconds / 3_600).toFixed(1).replace(".", ",")} h`;
}

