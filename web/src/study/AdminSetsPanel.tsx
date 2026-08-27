import { Check, CircleSlash, Plus, Send, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Checkbox, Skeleton, Spinner } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { EMPTY_FORM, type FormState } from "@/features/run/commission";
import { Count, GenerateForm } from "@/features/run/GenerateForm";
import { profileLabel } from "@/lib/evaluator";
import { when } from "@/lib/format";
import { cn } from "@/lib/utils";
import { useActiveWorkspace, useKg, useKgGraph, useProfile } from "@/state/queries";

import { toStockParams } from "./commission";
import {
  useAssignSet,
  useAssignableAccounts,
  useEvaluationSets,
  useGenerateEvaluations,
} from "./queries";
import type { AssignableAccount, EvaluationSet, EvaluatorProfile } from "./types";

/**
 * Handing comparisons out, in the order the decision is actually made.
 *
 * WHO first, then WHERE, then WHICH — and that order is the design. With evaluators drawn
 * from different subjects and different years there is no rule that can share a workload
 * out: only the administrator knows who teaches what, and asking somebody to judge a
 * syllabus they have never taught produces an answer of convenience, which is worse than
 * producing none. Starting from the person is what makes «¿puede juzgar esto?» the first
 * question instead of an afterthought.
 *
 * What a copy shares with its source is the three EXERCISES; what it does not share is the
 * order. Two evaluators on one shuffle share a position bias, and an agreement that
 * includes it is not an agreement about the exercises.
 */

// The label is shared with «Cuentas y accesos», which is where it is set; what belongs to
// this screen is the MARK on an account nobody classified — here it decides which wording
// that person will be asked, so it is something to act on before handing anything over.
function Profile({ value }: { value: EvaluatorProfile | null }) {
  return (
    <span className={cn("text-small", value ? "text-muted-foreground" : "text-attention")}>
      {profileLabel(value).toLowerCase()}
    </span>
  );
}

/* 1 · WHO ---------------------------------------------------------------------------- */

function PersonStep({
  accounts,
  chosen,
  onChoose,
}: {
  accounts: AssignableAccount[];
  chosen: AssignableAccount | null;
  onChoose: (account: AssignableAccount | null) => void;
}) {
  if (chosen) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-body font-medium">{chosen.username}</span>
        <Profile value={chosen.evaluator_profile} />
        <Button variant="ghost" size="sm" onClick={() => onChoose(null)}>
          Cambiar
        </Button>
      </div>
    );
  }

  return (
    <div className="flex flex-wrap gap-2">
      {accounts.map((account) => (
        <button
          key={account.id}
          type="button"
          onClick={() => onChoose(account)}
          className="border border-border px-3 py-2 text-left transition-colors hover:bg-accent/40"
        >
          <span className="block text-body font-medium">{account.username}</span>
          <span className="block">
            <Profile value={account.evaluator_profile} />
            <span className="text-small text-muted-foreground">
              {" "}
              · {account.workspaces.length} workspace
              {account.workspaces.length === 1 ? "" : "s"}
            </span>
          </span>
        </button>
      ))}
    </div>
  );
}

/* 2 · WHERE -------------------------------------------------------------------------- */

function WorkspaceStep({
  account,
  chosen,
  onChoose,
}: {
  account: AssignableAccount;
  chosen: string | null;
  onChoose: (slug: string | null) => void;
}) {
  if (account.workspaces.length === 0) {
    return (
      <p className="text-small text-attention">
        «{account.username}» no es miembro de ningún workspace todavía. Dale acceso en
        «Cuentas y accesos» antes de asignarle nada.
      </p>
    );
  }

  if (chosen) {
    const found = account.workspaces.find((entry) => entry.slug === chosen);
    return (
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-body font-medium">{found?.name ?? chosen}</span>
        <span className="font-mono text-small text-muted-foreground">{chosen}</span>
        <Button variant="ghost" size="sm" onClick={() => onChoose(null)}>
          Cambiar
        </Button>
      </div>
    );
  }

  // Only the instances this person can actually open: the rest would 404 in their queue.
  return (
    <div className="flex flex-wrap gap-2">
      {account.workspaces.map((entry) => (
        <button
          key={entry.slug}
          type="button"
          onClick={() => onChoose(entry.slug)}
          className="border border-border px-3 py-2 text-left transition-colors hover:bg-accent/40"
        >
          <span className="block text-body font-medium">{entry.name}</span>
          <span className="block font-mono text-small text-muted-foreground">{entry.slug}</span>
        </button>
      ))}
    </div>
  );
}

/* 3 · WHICH -------------------------------------------------------------------------- */

function SetRow({
  set,
  accountId,
  picked,
  onPick,
}: {
  set: EvaluationSet;
  accountId: number;
  picked: boolean;
  onPick: (next: boolean) => void;
}) {
  const holder = set.holders.find((entry) => entry.account_id === accountId);
  const others = set.holders.filter((entry) => entry.account_id !== accountId);

  return (
    <label
      className={cn(
        "flex cursor-pointer flex-wrap items-center gap-3 border-b border-border px-4 py-3 transition-colors last:border-b-0",
        picked ? "bg-primary/5" : "hover:bg-accent/40",
        holder && "cursor-default opacity-60",
      )}
    >
      <Checkbox
        checked={picked}
        onCheckedChange={onPick}
        disabled={Boolean(holder)}
        label={`Asignar la comparación de ${set.concepts.join(", ")}`}
      />
      <span className="min-w-48 flex-1">
        <span className="block text-body font-medium">
          {set.concepts.join(", ") || "sin conceptos"}
        </span>
        <span className="block text-small text-muted-foreground">
          {when(new Date(set.created_at * 1000).toISOString())}
          {set.think ? " · con razonamiento" : " · sin razonamiento"}
        </span>
      </span>

      {/* Who else holds it, which is what an administrator needs in order to build overlap
          on purpose: two people on one set is the only way agreement can be computed. */}
      <span className="flex flex-wrap items-center gap-1.5">
        {others.map((entry) => (
          <span
            key={entry.session_id}
            className={cn(
              "inline-flex items-center gap-1 border px-2 py-0.5 text-small",
              entry.decided || entry.declined
                ? "border-settled text-settled"
                : "border-border text-muted-foreground",
            )}
          >
            {entry.decided ? <Check className="size-3" /> : null}
            {entry.declined ? <CircleSlash className="size-3" /> : null}
            {entry.account ?? "cuenta borrada"}
          </span>
        ))}
        {others.length === 0 ? (
          <span className="text-small text-muted-foreground">sin repartir</span>
        ) : null}
      </span>

      {holder ? (
        <span className="text-micro font-condensed text-settled uppercase">ya la tiene</span>
      ) : null}
    </label>
  );
}

export function AdminSetsPanel() {
  const accounts = useAssignableAccounts();
  const [account, setAccount] = useState<AssignableAccount | null>(null);
  const [workspace, setWorkspace] = useState<string | null>(null);
  const [picked, setPicked] = useState<string[]>([]);
  const [composing, setComposing] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  // ITS OWN NUMBER, and that is the whole point of it being here. «¿Cuántas comparaciones?»
  // is not «¿cuántos ítems produce este encargo?» — an evaluation always produces one per
  // arm — so the form hides its counter, and reading that hidden counter as this one is
  // what made a single commission arrive as two sessions.
  const [comparisons, setComparisons] = useState(1);

  const sets = useEvaluationSets(workspace);
  const assign = useAssignSet();
  const generate = useGenerateEvaluations();
  const toast = useToast();

  // THE COMMISSION FORM READS THE ACTIVE WORKSPACE, NOT THE CHOSEN ONE, and there is no
  // way round it here: the graph, the profile and the concept list all travel on the
  // `X-Workspace` header the tab sets once. Building a commission against one instance's
  // graph and running it in another's would either 422 at job time («Unknown concepts») or,
  // where the two happen to share a name, quietly produce an exercise about the wrong
  // syllabus. So encargar is offered ONLY while the two agree, and says how to make them.
  const active = useActiveWorkspace();
  const profileQuery = useProfile();
  const kg = useKg();
  const kgGraph = useKgGraph();
  const sameInstance = Boolean(workspace) && workspace === active;

  const free = useMemo(
    () => (sets.data?.sets ?? []).filter((set) => !set.holders.some((h) => h.account_id === account?.id)),
    [sets.data, account],
  );

  // One call per set: the endpoint hands ONE set to a list of people, and this screen is
  // the transpose — one person taking a list of sets. Failures are counted rather than
  // thrown, so a network hiccup on the fourth does not hide that three did land.
  const send = async () => {
    if (!account) return;
    const results = await Promise.all(
      picked.map((setId) =>
        assign
          .mutateAsync({ setId, accounts: [account.id] })
          .then(() => true)
          .catch(() => false),
      ),
    );
    const done = results.filter(Boolean).length;
    const failed = results.length - done;

    toast({
      title: done > 0 ? `Asignadas a ${account.username}` : "No se pudo asignar",
      description:
        done > 0
          ? `${done} comparación(es)${failed ? `; ${failed} falló(aron)` : ""}.`
          : "Ninguna llegó a asignarse. Vuelve a intentarlo.",
      tone: failed && done ? "attention" : done ? "settled" : "danger",
    });
    setPicked([]);
  };

  const launch = () => {
    if (!workspace) return;
    generate.mutate(
      toStockParams(form, workspace, comparisons),
      {
        onSuccess: ({ jobs }) => {
          toast({
            title: `Encargadas ${jobs.length}`,
            description:
              "Se preparan una detrás de otra en la cola; aparecerán aquí en cuanto terminen.",
            tone: "settled",
          });
          setComposing(false);
        },
        onError: (error) =>
          toast({
            title: "No se pudo encargar",
            description: (error as Error).message,
            tone: "danger",
          }),
      },
    );
  };

  if (accounts.isLoading) return <Skeleton className="h-40" />;
  // NEVER a silent `null`. Rendering nothing is what turned a 404 from a route-ordering
  // bug into a card with a heading and no body — which reads as «esta función no existe»
  // rather than «esto falló», and cost a round of «sigo sin ver la opción».
  if (accounts.isError) {
    return (
      <p className="text-small text-destructive">
        No se pudieron leer las cuentas: {(accounts.error as Error).message}
      </p>
    );
  }
  if (!accounts.data) {
    return <p className="text-small text-muted-foreground">Sin datos de cuentas.</p>;
  }
  if (accounts.data.accounts.length === 0) {
    return (
      <p className="text-small text-muted-foreground">
        No hay cuentas activas a las que asignar. Crea alguna en «Cuentas y accesos».
      </p>
    );
  }

  return (
    <div className="space-y-4">
      <Step index={1} title="¿A quién se la asignas?" done={Boolean(account)}>
        <PersonStep
          accounts={accounts.data.accounts}
          chosen={account}
          onChoose={(next) => {
            setAccount(next);
            setWorkspace(null);
            setPicked([]);
          }}
        />
      </Step>

      {account ? (
        <Step index={2} title="¿En cuál de sus workspaces?" done={Boolean(workspace)}>
          <WorkspaceStep
            account={account}
            chosen={workspace}
            onChoose={(slug) => {
              setWorkspace(slug);
              setPicked([]);
            }}
          />
        </Step>
      ) : null}

      {account && workspace ? (
        <Step index={3} title="¿Cuáles?" done={picked.length > 0}>
          {sets.isLoading ? (
            <Skeleton className="h-24" />
          ) : (
            <div className="space-y-3">
              {free.length === 0 && (sets.data?.sets.length ?? 0) === 0 ? (
                <p className="text-small text-muted-foreground">
                  Este workspace todavía no tiene comparaciones. Encarga unas cuantas abajo y
                  reparte las que quieras: las que no asignes se quedan guardadas.
                </p>
              ) : (
                <div className="border border-border">
                  {(sets.data?.sets ?? []).map((set) => (
                    <SetRow
                      key={set.set_id}
                      set={set}
                      accountId={account.id}
                      picked={picked.includes(set.set_id)}
                      onPick={(next) =>
                        setPicked((current) =>
                          next
                            ? [...current, set.set_id]
                            : current.filter((id) => id !== set.set_id),
                        )
                      }
                    />
                  ))}
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  disabled={picked.length === 0 || assign.isPending}
                  onClick={send}
                >
                  {assign.isPending ? <Spinner /> : <Send />}
                  Asignar {picked.length || ""} a {account.username}
                </Button>
                <Button
                  variant="outline"
                  disabled={!sameInstance}
                  onClick={() => setComposing((value) => !value)}
                  title={
                    sameInstance
                      ? undefined
                      : `Cambia arriba a «${workspace}» para encargar comparaciones suyas`
                  }
                >
                  <Plus />
                  Encargar más comparaciones
                </Button>
                {picked.length > 0 ? (
                  <p className="text-small text-muted-foreground">
                    Recibirá los mismos ejercicios con un orden propio.
                  </p>
                ) : null}
              </div>

              {/* Repartir funciona en cualquier caso — lee del servidor por slug. Lo que
                  no puede cruzar instancias es COMPONER un encargo. */}
              {!sameInstance ? (
                <p className="flex items-start gap-2 text-small text-attention">
                  <Sparkles className="mt-0.5 size-3.5 shrink-0" />
                  Para encargar comparaciones de «{workspace}» tienes que tenerlo abierto:
                  cámbialo en el selector de arriba del todo
                  {active ? <> (ahora estás en «{active}»)</> : null}. Repartir las que ya
                  existen sí funciona desde aquí.
                </p>
              ) : null}

              {composing && sameInstance ? (
                <div className="animate-fade-in space-y-3 border border-border bg-muted/30 p-3">
                  <p className="flex items-start gap-2 text-small text-muted-foreground">
                    <Sparkles className="mt-0.5 size-3.5 shrink-0" />
                    Cada comparación son tres propuestas del mismo encargo. Se preparan una
                    detrás de otra en la cola, y las que no repartas se quedan guardadas para
                    otra persona.
                  </p>
                  <div className="flex flex-wrap items-center gap-3">
                    <span className="text-body font-medium">¿Cuántas comparaciones?</span>
                    <Count value={comparisons} onChange={setComparisons} max={10} />
                    <span className="text-small text-muted-foreground">
                      {comparisons === 1
                        ? "una sesión, tres propuestas"
                        : `${comparisons} sesiones del mismo encargo; cada una sortea su orden y su razonamiento por separado`}
                    </span>
                  </div>
                  <GenerateForm
                    state={form}
                    onChange={setForm}
                    profile={profileQuery.data?.profile ?? null}
                    concepts={kg.data?.concepts ?? []}
                    graph={kgGraph.data}
                    disabled={false}
                    running={false}
                    pending={generate.isPending}
                    error={generate.isError ? (generate.error as Error).message : null}
                    blockedInstructions={null}
                    variant="evaluation"
                    launchLabel={`Encargar ${comparisons} comparación${comparisons === 1 ? "" : "es"}`}
                    onLaunch={launch}
                    onCancel={() => setComposing(false)}
                  />
                </div>
              ) : null}
            </div>
          )}
        </Step>
      ) : null}
    </div>
  );
}

/** A numbered step, because here the order genuinely is a dependency: you cannot pick a
 *  workspace before a person, nor a comparison before a workspace. */
function Step({
  index,
  title,
  done,
  children,
}: {
  index: number;
  title: string;
  done: boolean;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-2">
      <div className="flex items-center gap-2.5">
        <span
          className={cn(
            "flex size-6 shrink-0 items-center justify-center rounded-full text-small font-semibold nums",
            done ? "bg-primary/12 text-primary" : "bg-primary text-primary-foreground",
          )}
        >
          {done ? <Check className="size-3.5" /> : index}
        </span>
        <h3 className="text-body font-medium">{title}</h3>
      </div>
      <div className="pl-8.5">{children}</div>
    </section>
  );
}
