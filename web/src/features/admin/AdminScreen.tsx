import { ShieldCheck } from "lucide-react";
import { useState } from "react";

import { GuideLink } from "@/components/GuideLink";
import { InfoHint } from "@/components/ui/hint";
import { EmptyState, LoadError, Skeleton } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import type { AdminOverview } from "@/lib/types";
import { useSession } from "@/state/auth";
import { useAdminOverview } from "@/state/queries";

import { AccountsTab } from "./AccountsTab";
import { StatTile } from "./charts";
import { ConfigTab } from "./ConfigTab";
import { EngineTab } from "./EngineTab";
import { MaintenanceSwitch } from "./MaintenanceSwitch";
import { WorkspacesTab } from "./WorkspacesTab";
import { useT } from "@/lib/i18n";
import { jobName } from "@/lib/names";

/**
 * The installation seen from outside: four tabs, one per thing an administrator runs.
 *
 * "Cuentas" decides who exists and where they get in;
 * "Workspaces" lists the instances and what they weigh; "Motor" is the machine and the
 * process — the GPU, the tunnel, the models on disk, the queue; "Configuración" is every
 * value the registry exposes. Each tab is its own file, because the screen that crosses
 * every account and every workspace is also the one that grows.
 */
export function AdminScreen() {
  const { t } = useT();
  const session = useSession();
  const [tab, setTab] = useState("cuentas");

  const overview = useAdminOverview();

  if (!session.data?.user.is_admin) {
    return (
      <EmptyState icon={<ShieldCheck className="size-6" />} title={t("admin.notAdmin")}>
        {t("admin.notAdmin.body")}
      </EmptyState>
    );
  }

  if (overview.isLoading) return <Skeleton className="h-96" />;

  return (
    <div className="space-y-5">
      <header className="space-y-1.5">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="font-display font-expanded text-display">{t("admin.title")}</h1>
          <InfoHint label={t("admin.whatIsThis")}>{t("admin.whatIsThis.body")}</InfoHint>
        </div>
        <GuideLink slug="admin" />
      </header>

      <MaintenanceSwitch />

      {/* Above the tabs on purpose: three of the four render nothing without this data, and
          an empty tab with no explanation reads as a feature that does not exist. */}
      {overview.data ? (
        <Totals overview={overview.data} />
      ) : (
        <LoadError
          title={t("admin.unreadable")}
          error={overview.error}
          onRetry={overview.refetch}
        />
      )}

      <Tabs
        items={[
          { value: "cuentas", label: t("admin.tab.accounts") },
          { value: "workspaces", label: t("admin.tab.workspaces") },
          { value: "motor", label: t("admin.tab.engine") },
          { value: "config", label: t("admin.tab.config") },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "cuentas" && overview.data ? <AccountsTab overview={overview.data} /> : null}

      {tab === "workspaces" && overview.data ? (
        <WorkspacesTab overview={overview.data} />
      ) : null}

      {tab === "motor" && overview.data ? <EngineTab overview={overview.data} /> : null}

      {tab === "config" ? <ConfigTab /> : null}
    </div>
  );
}

function Totals({ overview }: { overview: AdminOverview }) {
  const { t, plural, language } = useT();
  const { totals, engine } = overview;
  return (
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
      <StatTile label={t("admin.stat.accounts")} value={totals.users} />
      <StatTile label={t("admin.stat.workspaces")} value={totals.workspaces} />
      <StatTile
        label={t("admin.stat.generations")}
        value={totals.generations.toLocaleString(language)}
      />
      <StatTile
        label={t("admin.stat.engine")}
        value={engine.busy ? t("admin.stat.busy") : t("admin.stat.free")}
        tone={engine.busy ? "accent" : "plain"}
        hint={
          engine.busy
            ? t("admin.stat.busyHint", {
                label: engine.job ? jobName(engine.job.kind, t, engine.job.label) : t("admin.stat.job"),
                n: engine.queued,
              })
            : plural("admin.warmContexts", engine.warm_contexts.length)
        }
      />
    </div>
  );
}
