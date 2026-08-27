import { Download, Eraser, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { api } from "@/lib/api";
import { ARTIFACT_STATUS, bytes, when } from "@/lib/format";
import type { AdminOverview, AdminWorkspace } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  useActiveWorkspace,
  useAdminDeleteWorkspace,
  useClearCache,
  useDeleteArtifact,
} from "@/state/queries";

/**
 * The installation's instances, and what this panel writes about them: removing them, or
 * the regenerable half of what they hold.
 *
 * Emptying a stage and deleting the workspace are one decision at two scopes, so they live
 * in the same row: the stage is emptied from its badge, the workspace from the button at the
 * end. Neither builds nor approves anything — for that one enters the instance, which is
 * where what is being touched can be seen.
 */
export function WorkspacesTab({ overview }: { overview: AdminOverview }) {
  const remove = useAdminDeleteWorkspace();
  const toast = useToast();
  const [target, setTarget] = useState<AdminWorkspace | null>(null);
  // Which one this tab has open, which is the one deletion has consequences for on screen:
  // the header, the cache and the stream all belong to it.
  const here = useActiveWorkspace();
  // Mirrors the server, which refuses with a 409: an INSTALLATION with no workspace has
  // nothing to offer anybody. An ACCOUNT with none is a different question and a normal
  // state — that is what `NoWorkspace` is for.
  const only = overview.workspaces.length === 1;
  const total = overview.workspaces.reduce((sum, w) => sum + w.disk.total, 0);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
          Workspaces ({overview.workspaces.length}) · {bytes(total)} en disco
        </h2>
        <InfoHint label="Qué pesa cada parte">
          «Bruto» son los documentos subidos, lo único que no se reconstruye con una GPU y un
          rato. «Instancia» son los artefactos y su contexto. «Caché» son las derivaciones
          —vectores, markdown convertido, descripciones— y «historial» las copias que guarda
          cada edición junto con los registros de ejecución.
        </InfoHint>
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        <Table minWidth="64rem">
          <THead>
            <TR>
              <TH>Workspace</TH>
              <TH>Cadena</TH>
              <TH align="num">Miembros</TH>
              <TH align="num">Variantes</TH>
              <TH>Disco</TH>
              <TH>Creado</TH>
              <TH />
            </TR>
          </THead>
          <TBody>
            {overview.workspaces.map((workspace) => (
              <TR key={workspace.id}>
                <TD className="px-3 py-2">
                  {workspace.name}
                  <span className="ml-2 font-mono text-micro text-muted-foreground">
                    {workspace.slug}
                  </span>
                  {workspace.warm ? (
                    <span className="ml-2 text-micro text-muted-foreground">· en memoria</span>
                  ) : null}
                </TD>
                <TD className="px-3 py-2">
                  <ChainCell workspace={workspace} />
                </TD>
                <TD align="num" className="px-3 py-2 nums">{workspace.members}</TD>
                <TD align="num" className="px-3 py-2 nums">{workspace.generations}</TD>
                <TD className="px-3 py-2">
                  <DiskCell workspace={workspace} />
                </TD>
                <TD className="whitespace-nowrap px-3 py-2 text-small text-muted-foreground">
                  {workspace.created_at ? when(workspace.created_at) : "—"}
                </TD>
                <TD align="num" className="whitespace-nowrap px-3 py-2">
                  <ExportButton workspace={workspace} />
                  <ClearCacheButton workspace={workspace} />
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    disabled={only || remove.isPending}
                    title={
                      only
                        ? "Es el único workspace de la instalación"
                        : "Eliminar el workspace y sus ficheros"
                    }
                    onClick={() => setTarget(workspace)}
                  >
                    <Trash2 />
                  </Button>
                </TD>
              </TR>
            ))}
          </TBody>
        </Table>
      </div>

      <FormError error={remove.error} />

      {target ? (
        <DeleteWorkspaceDialog
          workspace={target}
          here={target.slug === here}
          busy={remove.isPending}
          onClose={() => setTarget(null)}
          onConfirm={() =>
            remove.mutate(target.slug, {
              onSuccess: () => {
                setTarget(null);
                toast({
                  title: "Workspace eliminado",
                  description:
                    target.slug === here
                      ? `${target.slug}, con su árbol de ficheros. Era el que tenías abierto: la interfaz se mueve a donde tenga acceso tu cuenta.`
                      : `${target.slug}, con su árbol de ficheros.`,
                  tone: "attention",
                });
              },
              onError: (error: Error) =>
                toast({
                  title: "No se ha podido eliminar",
                  description: error.message,
                  tone: "danger",
                }),
            })
          }
        />
      ) : null}
    </div>
  );
}

function DiskCell({ workspace }: { workspace: AdminWorkspace }) {
  const { disk } = workspace;
  const parts = [
    ["bruto", disk.raw],
    ["instancia", disk.instance],
    ["caché", disk.cache],
    ["historial", disk.history],
  ] as const;
  return (
    <span
      className="nums text-small"
      title={parts.map(([label, size]) => `${label}: ${bytes(size)}`).join(" · ")}
    >
      {bytes(disk.total)}
      <span className="ml-1 text-micro text-muted-foreground">
        ({parts.filter(([, size]) => size > 0).map(([label, size]) => `${label} ${bytes(size)}`).join(", ") || "vacío"})
      </span>
    </span>
  );
}

/**
 * The regenerable half of the cache: vectors and converted markdown. Offered here because
 * it is the one thing that grows without an artifact changing, and because the next index
 * job rewrites all of it from what is on disk — nothing a person typed is in it.
 */
function ClearCacheButton({ workspace }: { workspace: AdminWorkspace }) {
  const clear = useClearCache();
  const toast = useToast();
  const confirm = () => {
    const message =
      `¿Vaciar la caché regenerable de ${workspace.slug}?\n\n` +
      "Se borran los vectores y el markdown convertido; el próximo trabajo los vuelve a " +
      "calcular (minutos). Las descripciones de conceptos y el anclaje al corpus se quedan.";
    if (!window.confirm(message)) return;
    clear.mutate(workspace.slug, {
      onSuccess: ({ files_removed, bytes_freed }) =>
        toast({
          title: "Caché vaciada",
          description: `${files_removed} fichero(s), ${bytes(bytes_freed)} liberados.`,
        }),
      onError: (error: Error) =>
        toast({ title: "No se ha podido vaciar", description: error.message, tone: "danger" }),
    });
  };
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      disabled={clear.isPending || workspace.disk.cache === 0}
      title={
        workspace.disk.cache === 0
          ? "La caché está vacía"
          : "Vaciar los vectores y el markdown convertido (se regeneran)"
      }
      onClick={confirm}
    >
      {clear.isPending ? <Spinner /> : <Eraser />}
    </Button>
  );
}

/**
 * The instance as its files say it is, as one JSON the browser saves. What a checkout
 * needs to run the same instance elsewhere, and the backup the administrator takes before
 * pressing anything irreversible on this row.
 */
function ExportButton({ workspace }: { workspace: AdminWorkspace }) {
  const [busy, setBusy] = useState(false);
  const toast = useToast();
  const download = async () => {
    setBusy(true);
    try {
      const bundle = await api.adminExportWorkspace(workspace.slug);
      const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `${workspace.slug}-${bundle.exported_at.slice(0, 10)}.json`;
      anchor.click();
      URL.revokeObjectURL(url);
      toast({
        title: "Instancia exportada",
        description: `${Object.keys(bundle.files).length} fichero(s) de ${workspace.slug}.`,
      });
    } catch (error) {
      toast({ title: "No se ha podido exportar", description: (error as Error).message, tone: "danger" });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      disabled={busy}
      title="Descargar la instancia (artefactos, contexto, aprobaciones y currículo) como JSON"
      onClick={download}
    >
      {busy ? <Spinner /> : <Download />}
    </Button>
  );
}

/**
 * An instance's chain, and the place a stage is emptied from.
 *
 * Emptying leaves the artifact «missing» and its workspace standing: the curated file, the
 * draft and the cache derivations that spoke of it are deleted. The copies under
 * `.history/` are untouched, so a mistaken deletion is undone from «Restaurar» on the
 * artifact's screen — and that is exactly what makes offering it here not reckless.
 */
function ChainCell({ workspace }: { workspace: AdminWorkspace }) {
  const discard = useDeleteArtifact();
  const toast = useToast();

  const confirm = (artifact: AdminWorkspace["stages"][number]) => {
    const message =
      `¿Vaciar «${artifact.label}» de ${workspace.slug}?\n\n` +
      "Se borran el fichero del artefacto y las derivaciones de la caché que dependían " +
      "de él; la etapa vuelve a «sin construir» y habrá que reconstruirla.\n\n" +
      "Las copias del historial no se tocan: si te equivocas, se restaura desde la " +
      "pantalla del artefacto.";
    if (!window.confirm(message)) return;
    discard.mutate(
      { slug: workspace.slug, artifact: artifact.artifact },
      {
        onSuccess: () =>
          toast({
            title: "Etapa vaciada",
            description: `«${artifact.label}» de ${workspace.slug}. El historial sigue ahí.`,
            tone: "attention",
          }),
        onError: (error: Error) =>
          toast({ title: "No se ha podido vaciar", description: error.message, tone: "danger" }),
      },
    );
  };

  return (
    <span className="flex flex-wrap items-center gap-1">
      {workspace.stages.map((stage) => {
        const meta = ARTIFACT_STATUS[stage.status];
        const empty = stage.status === "missing";
        return (
          <button
            key={stage.artifact}
            type="button"
            disabled={empty || discard.isPending}
            title={
              empty
                ? `${stage.label}: sin construir`
                : `Vaciar «${stage.label}» de ${workspace.slug}`
            }
            onClick={() => confirm(stage)}
            className={cn(
              "rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              empty ? "cursor-default" : "hover:opacity-75",
            )}
          >
            <Badge variant={meta.tone as never}>
              {stage.label.split(" ")[0]} · {meta.label.toLowerCase()}
            </Badge>
          </button>
        );
      })}
    </span>
  );
}

/**
 * Deleting a workspace is irreversible and takes the files with it, so the slug is typed.
 *
 * Not ceremony: the row next to it looks like this one, the button is an icon, and what
 * disappears includes the documents someone uploaded — the only thing here that cannot be
 * rebuilt with a GPU and a while.
 */
function DeleteWorkspaceDialog({
  workspace,
  here,
  busy,
  onClose,
  onConfirm,
}: {
  workspace: AdminWorkspace;
  /** It is the one this tab has open: everything on screen belongs to it. */
  here: boolean;
  busy: boolean;
  onClose: () => void;
  onConfirm: () => void;
}) {
  const [typed, setTyped] = useState("");
  const built = workspace.stages.filter((stage) => stage.status !== "missing");

  return (
    <Dialog
      open
      onClose={onClose}
      title={`Eliminar «${workspace.name}»`}
      description="No se puede deshacer."
      className="max-w-lg"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            Cancelar
          </Button>
          <Button
            variant="destructive"
            disabled={typed !== workspace.slug || busy}
            onClick={onConfirm}
          >
            {busy ? <Spinner /> : <Trash2 />}
            Eliminar
          </Button>
        </>
      }
    >
      <div className="space-y-3 text-body">
        <p>Desaparecen de la instalación y del disco ({bytes(workspace.disk.total)}):</p>
        <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
          <li>
            {built.length > 0
              ? `sus artefactos construidos (${built.map((s) => s.label.toLowerCase()).join(", ")})`
              : "sus artefactos, que están todos sin construir"}
          </li>
          <li>
            los documentos en bruto que se subieron a esta instancia
            {workspace.disk.raw > 0 ? ` (${bytes(workspace.disk.raw)})` : ""}
          </li>
          <li>sus cachés, sus accesos y sus aprobaciones</li>
          <li>
            {workspace.generations > 0
              ? `sus ${workspace.generations} variante(s) guardada(s) y sus comparaciones`
              : "sus comparaciones de evaluación, si las hubiera"}
          </li>
        </ul>
        {here ? (
          <p className="text-muted-foreground">
            Es el que tienes abierto ahora mismo. Al borrarlo, esta pestaña se mueve sola a
            otro de tus accesos; si no te queda ninguno, la aplicación te ofrece crear uno.
          </p>
        ) : null}
        <div className="space-y-1">
          <Label htmlFor="confirm-slug">
            Escribe <span className="font-mono normal-case">{workspace.slug}</span> para
            confirmar
          </Label>
          <Input
            id="confirm-slug"
            value={typed}
            autoFocus
            autoComplete="off"
            onChange={(event) => setTyped(event.target.value)}
          />
        </div>
      </div>
    </Dialog>
  );
}
