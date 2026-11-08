import { Badge } from "@/components/ui/badge";
import { LoadError } from "@/components/ui/load-error";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { SectionHeader } from "@/components/Sections";
import { useT, type Key } from "@/lib/i18n";
import { cn } from "@/lib/utils";
import { useAdminEngines } from "@/state/queries";

import { engineState, type EngineState } from "./accounts";
import { ENGINE_KINDS } from "./engineState";

const STATE_LABEL: Record<EngineState, Key> = {
  unused: "acc.engines.state.unused",
  live: "acc.engines.state.live",
  idle: "acc.engines.state.idle",
};

/**
 * «Motores»: the engines the installation offers its accounts, how many accounts run on each,
 * and whether the server holds its instance now.
 *
 * A reading only: an account's engine is chosen in its own row («Gestionar»), where the
 * account is. The names are the registry's, drawn as they come; a name «Motor» knows is
 * followed by what it is called there.
 */
export function EnginesSection() {
  const { t } = useT();
  const engines = useAdminEngines();
  const header = <SectionHeader title={t("acc.engines")} description={t("acc.engines.lead")} />;

  if (engines.isLoading) {
    return (
      <>
        {header}
        <Skeleton className="h-40" />
      </>
    );
  }
  if (!engines.data) {
    return (
      <>
        {header}
        <LoadError title={t("acc.engines.unreadable")} error={engines.error} onRetry={() => engines.refetch()} />
      </>
    );
  }

  const rows = Array.isArray(engines.data.engines) ? engines.data.engines : [];
  return (
    <>
      {header}
      <section className="surface space-y-4 p-5" aria-labelledby="engines-offered">
        <div className="space-y-1">
          <h3 id="engines-offered" className="text-heading">
            {t("acc.engines.title")}
          </h3>
          <p className="text-small text-muted-foreground">{t("acc.engines.note")}</p>
        </div>
        {rows.length === 0 ? (
          <p className="text-small text-muted-foreground">{t("acc.engines.empty")}</p>
        ) : (
          <Table minWidth="0">
            <THead>
              <TR>
                <TH className="w-full">{t("acc.engines.col.engine")}</TH>
                <TH align="num">{t("acc.engines.col.accounts")}</TH>
                <TH className="whitespace-nowrap">{t("acc.engines.col.state")}</TH>
              </TR>
            </THead>
            <TBody>
              {rows.map((engine) => {
                const kind = ENGINE_KINDS[engine.name];
                const state = engineState(engine);
                return (
                  <TR key={engine.name} className="h-11">
                    <TD className="max-w-0">
                      <span className="flex items-center gap-2">
                        <span className="truncate font-mono">{engine.name}</span>
                        {kind ? (
                          <span className="truncate text-muted-foreground">{t(kind.title)}</span>
                        ) : null}
                        {engine.name === engines.data.default ? (
                          <Badge variant="outline">{t("acc.engines.isDefault")}</Badge>
                        ) : null}
                      </span>
                    </TD>
                    <TD align="num">{engine.users}</TD>
                    <TD className={cn("whitespace-nowrap", state !== "live" && "text-muted-foreground")}>
                      {t(STATE_LABEL[state])}
                    </TD>
                  </TR>
                );
              })}
            </TBody>
          </Table>
        )}
      </section>
    </>
  );
}
