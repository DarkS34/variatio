import { Cloud, Download, Timer } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { InfoHint } from "@/components/ui/hint";
import { Alert, Progress } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import type { CerebrasModel, CerebrasState, CerebrasWindow } from "@/lib/types";

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
 * it answers what comes next («qué fase se lo está comiendo») and leaves in a spreadsheet.
 *
 * Colour follows the palette's own rule rather than a severity scale: a meter is ink while
 * it is merely a quantity, --attention on the ONE window currently holding a call back
 * (that is literally «act here»), and --destructive only when a call is being refused.
 * Tinting every near-full meter would spend colour on something nobody can act on.
 */
export function CerebrasCard({ cerebras }: { cerebras: CerebrasState }) {
  const waiting = cerebras.inflight?.waiting_until != null;
  const blocked = cerebras.usage.some(
    (entry) => entry.windows.day.requests_remaining <= 0 || entry.windows.day.tokens_remaining <= 0,
  );

  // Only ever rendered while the engine routes here, so there is no «motor inactivo» state
  // to name: with the plain `ollama` engine the whole half is gone from the tab.
  const state = blocked
    ? { label: "presupuesto diario agotado", tone: "danger" as const }
    : waiting
      ? { label: "esperando presupuesto", tone: "attention" as const }
      : cerebras.inflight
        ? { label: "en marcha", tone: "settled" as const }
        : !cerebras.configured
          ? { label: "sin clave", tone: "outline" as const }
          : { label: "en reposo", tone: "settled" as const };

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex flex-wrap items-center gap-2">
          <Cloud className="size-4 text-muted-foreground" />
          <CardTitle>Cerebras</CardTitle>
          <Badge variant={state.tone}>{state.label}</Badge>
          <InfoHint label="Cómo se cuenta el presupuesto">
            La cuota es por modelo, y la de esta cuenta no es la que anuncia el catálogo: los
            headers «limit» reportan la del modelo, y solo los «remaining» dejan ver la real.
            Medido el 2026-08-26 sobre «gemma-4-31b»: el catálogo anuncia 500 peticiones por
            minuto y la cuenta admite 5. Lo que ves aquí son los techos de «Configuración»,
            que el limitador sube solo si alguna vez ve que queda más de lo que dicen.
            <br />
            <br />
            Los tokens se cuentan con el «usage» exacto de cada respuesta y no con los
            headers, que van con retraso. Y como la API no manda ningún «reset», la ventana
            es deslizante: se reconstruye con las marcas de tiempo de nuestras propias
            llamadas.
          </InfoHint>
        </div>
        <CardDescription>
          {cerebras.routed.length > 0 ? (
            <span className="font-mono">{cerebras.routed.join(", ")}</span>
          ) : (
            "Ningún modelo enrutado"
          )}
          {cerebras.configured ? "" : " · falta CEREBRAS_API_KEY en el entorno"}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        <Flight cerebras={cerebras} />
        {cerebras.usage.length === 0 ? (
          <p className="text-small text-muted-foreground">
            Todavía no se ha gastado nada. Los medidores aparecen con la primera llamada.
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
  const flying = cerebras.inflight;
  if (!flying) {
    return (
      <div className="flex items-center gap-3 border border-border bg-muted px-3 py-2.5 text-small text-muted-foreground">
        <span className="size-2 rounded-full bg-muted-foreground/40" />
        Sin llamadas en curso
      </div>
    );
  }

  const held = flying.waiting_until != null ? Math.max(0, flying.waiting_until - Date.now() / 1000) : 0;
  const waiting = flying.waiting_until != null;

  return (
    <div
      className={
        waiting
          ? "flex flex-wrap items-center gap-3 border border-[color-mix(in_oklch,var(--attention)_40%,transparent)] bg-[color-mix(in_oklch,var(--attention)_8%,transparent)] px-3 py-2.5"
          : "flex flex-wrap items-center gap-3 border border-border bg-muted px-3 py-2.5"
      }
    >
      <span
        className={
          waiting
            ? "size-2 shrink-0 animate-pulse rounded-full bg-attention"
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
      <span className="grow" />
      {waiting ? (
        <span className="nums flex items-center gap-1.5 text-small font-semibold text-attention">
          <Timer className="size-3.5" />
          sale en {Math.ceil(held)} s
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
  const day = entry.windows.day;
  const exhausted = day.requests_remaining <= 0 || day.tokens_remaining <= 0;

  return (
    <div className="space-y-4">
      {single ? null : <p className="font-mono text-small font-semibold">{entry.model}</p>}

      {exhausted ? (
        <Alert tone="danger" title="Las llamadas a Cerebras se están rechazando">
          El presupuesto del día no se libera hasta dentro de {hours(day.resets_in)}, y esperar
          tanto sería un build colgado sin explicación. Cambia el motor a «ollama», sube el
          techo en «Configuración» o espera.
        </Alert>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2">
        <Meter
          label="Peticiones · minuto"
          used={entry.windows.minute.requests_used}
          limit={entry.windows.minute.requests_limit}
          remaining={entry.windows.minute.requests_remaining}
          resets={entry.windows.minute.resets_in}
          rolling="La ventana rueda en"
        />
        <Meter
          label="Tokens · minuto"
          used={entry.windows.minute.tokens_used}
          limit={entry.windows.minute.tokens_limit}
          remaining={entry.windows.minute.tokens_remaining}
          resets={entry.windows.minute.resets_in}
          rolling="La ventana rueda en"
        />
        <Meter
          label="Peticiones · día"
          used={day.requests_used}
          limit={day.requests_limit}
          remaining={day.requests_remaining}
          resets={day.resets_in}
          rolling="Se libera en"
          daily
        />
        <Meter
          label="Tokens · día"
          used={day.tokens_used}
          limit={day.tokens_limit}
          remaining={day.tokens_remaining}
          resets={day.resets_in}
          rolling="Se libera en"
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
        {used.toLocaleString("es-ES")}{" "}
        <span className="text-small font-normal text-muted-foreground">
          de {limit.toLocaleString("es-ES")}
        </span>
      </p>
      <Progress value={used} max={limit} tone={tone} />
      <p className={`nums text-micro text-muted-foreground ${emphasis}`}>
        {remaining <= 0
          ? `Agotado · ${rolling.toLowerCase()} ${daily ? hours(resets) : `${Math.ceil(resets)} s`}`
          : daily
            ? "Ventana deslizante de 24 h"
            : resets > 0
              ? `${rolling} ${Math.ceil(resets)} s`
              : "Sin llamadas en el último minuto"}
      </p>
    </div>
  );
}

// Secondary on purpose: it answers the question AFTER the meters, and the meters are what
// somebody opens this card to see. The bar compares each phase against the largest one and
// not against the day — at the day's scale every row but the first would be invisible.
function Breakdown({ entry }: { entry: CerebrasModel }) {
  if (entry.phases.length === 0) return null;
  const top = entry.phases[0].tokens || 1;
  const ceiling = entry.windows.day.tokens_limit || 1;

  return (
    <div className="space-y-2 border-t border-border pt-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <p className="text-micro font-condensed uppercase text-muted-foreground">
            Consumo por fase
          </p>
          <p className="text-small text-muted-foreground">
            Últimas 24 h, sobre el presupuesto diario
          </p>
        </div>
        <a
          className="inline-flex items-center gap-1.5 border border-input px-3 py-1.5 text-small font-medium hover:bg-muted"
          href="/api/admin/engine/cerebras/export.csv"
          download
        >
          <Download className="size-3.5" />
          Descargar CSV
        </a>
      </div>
      <Table>
        <THead>
          <TR>
            <TH>Fase</TH>
            <TH className="text-right">Peticiones</TH>
            <TH className="text-right">Tokens</TH>
            <TH className="text-right">Del día</TH>
          </TR>
        </THead>
        <TBody>
          {entry.phases.map((row) => (
            <TR key={row.phase}>
              <TD className="font-mono">{row.phase}</TD>
              <TD className="nums text-right">{row.requests.toLocaleString("es-ES")}</TD>
              <TD className="nums text-right">{row.tokens.toLocaleString("es-ES")}</TD>
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

export type { CerebrasWindow };
