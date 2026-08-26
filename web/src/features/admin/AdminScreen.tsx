import { ShieldCheck } from "lucide-react";
import { useState } from "react";

import { InfoHint } from "@/components/ui/hint";
import { EmptyState, Skeleton } from "@/components/ui/misc";
import { Tabs } from "@/components/ui/tabs";
import type { AdminOverview } from "@/lib/types";
import { useSession } from "@/state/auth";
import { useAdminOverview } from "@/state/queries";

import { StudyTab } from "@/study/AdminStudyTab";
import { useAdminEvaluations } from "@/study/queries";

import { AccountsTab } from "./AccountsTab";
import { StatTile } from "./charts";
import { ConfigTab } from "./ConfigTab";
import { EngineTab } from "./EngineTab";
import { MaintenanceSwitch } from "./MaintenanceSwitch";
import { WorkspacesTab } from "./WorkspacesTab";

/**
 * The installation seen from outside: five tabs, one per thing an administrator runs.
 *
 * «Evaluaciones» is the study; «Cuentas» decides who exists and where they get in;
 * «Workspaces» lists the instances and what they weigh; «Motor» is the machine and the
 * process — the GPU, the tunnel, the models on disk, the queue; «Configuración» is every
 * value the registry exposes. Each tab is its own file, because the screen that crosses
 * every account and every workspace is also the one that grows.
 */
export function AdminScreen() {
  const session = useSession();
  const [tab, setTab] = useState("estudio");
  const [workspace, setWorkspace] = useState<string | null>(null);
  const [account, setAccount] = useState<number | null>(null);

  const overview = useAdminOverview();
  const study = useAdminEvaluations({ workspace, account });

  if (!session.data?.user.is_admin) {
    return (
      <EmptyState icon={<ShieldCheck className="size-6" />} title="Solo para administración">
        Esta pantalla es del administrador de la instalación. Tu cuenta no lo es.
      </EmptyState>
    );
  }

  if (overview.isLoading) return <Skeleton className="h-96" />;

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-center gap-2">
        <h1 className="font-display font-expanded text-display">Administración</h1>
        <InfoHint label="Qué es esto">
          La instalación entera vista desde fuera: quién la usa, quién puede entrar y en
          qué, cuántos workspaces hay, qué hace la máquina y cómo va el estudio de
          evaluación. Es la única pantalla que cruza cuentas, y el único sitio desde el que
          se dan accesos.
        </InfoHint>
      </header>

      <MaintenanceSwitch />

      {overview.data ? <Totals overview={overview.data} /> : null}

      <Tabs
        items={[
          { value: "estudio", label: "Evaluaciones" },
          { value: "cuentas", label: "Cuentas y accesos" },
          { value: "workspaces", label: "Workspaces" },
          { value: "motor", label: "Motor" },
          { value: "config", label: "Configuración" },
        ]}
        value={tab}
        onChange={setTab}
      />

      {tab === "estudio" ? (
        <StudyTab
          data={study.data}
          loading={study.isLoading}
          workspace={workspace}
          account={account}
          onWorkspace={setWorkspace}
          onAccount={setAccount}
        />
      ) : null}

      {tab === "cuentas" && overview.data ? (
        <AccountsTab
          overview={overview.data}
          onInspect={(id) => {
            setAccount(id);
            setTab("estudio");
          }}
        />
      ) : null}

      {tab === "workspaces" && overview.data ? (
        <WorkspacesTab overview={overview.data} />
      ) : null}

      {tab === "motor" && overview.data ? <EngineTab overview={overview.data} /> : null}

      {tab === "config" ? <ConfigTab /> : null}
    </div>
  );
}

function Totals({ overview }: { overview: AdminOverview }) {
  const { totals, engine } = overview;
  return (
    <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-5">
      <StatTile label="Cuentas" value={totals.users} />
      <StatTile label="Workspaces" value={totals.workspaces} />
      <StatTile label="Variantes generadas" value={totals.generations.toLocaleString("es-ES")} />
      <StatTile
        label="Comparaciones"
        value={totals.evaluations}
        hint={`${totals.decided} con elección registrada`}
      />
      <StatTile
        label="Motor"
        value={engine.busy ? "ocupado" : "libre"}
        tone={engine.busy ? "accent" : "plain"}
        hint={
          engine.busy
            ? `${engine.job?.label ?? "trabajo"} · ${engine.queued} en cola`
            : `${engine.warm_contexts.length} contexto(s) caliente(s)`
        }
      />
    </div>
  );
}
