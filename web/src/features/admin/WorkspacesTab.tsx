import { Download, Eraser, Pencil, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { InfoHint } from "@/components/ui/hint";
import { Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { api } from "@/lib/api";
import { ARTIFACT_STATUS, bytes, when } from "@/lib/format";
import type { AdminOverview, AdminWorkspace } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  useActiveWorkspace,
  useAdminDeleteWorkspace,
  useAdminRenameWorkspace,
  useClearCache,
  useDeleteArtifact,
} from "@/state/queries";
import { useT } from "@/lib/i18n";
import { artifactName } from "@/lib/names";

/**
 * The installation's instances, and what this panel writes about them: their name, their
 * removal, or the regenerable half of what they hold.
 *
 * Emptying a stage and deleting the workspace are one decision at two scopes, so they live
 * in the same row: the stage is emptied from its badge, the workspace from the button at the
 * end. Neither builds nor approves anything — for that one enters the instance, which is
 * where what is being touched can be seen.
 *
 * RENAMING IS HERE AND NOWHERE ELSE (2026-08-28, explicit user request). It used to be the
 * owner's, from the switcher; it is the administrator's now, and the owner-facing route is
 * gone rather than merely hidden — the client never decides a permission. This is the screen
 * where every instance is visible at once, which is what makes it the place to notice that a
 * new name collides with another.
 */
export function WorkspacesTab({ overview }: { overview: AdminOverview }) {
  const { t } = useT();
  const remove = useAdminDeleteWorkspace();
  const toast = useToast();
  const [target, setTarget] = useState<AdminWorkspace | null>(null);
  const [renaming, setRenaming] = useState<AdminWorkspace | null>(null);
  // Which one this tab has open, which is the one deletion has consequences for on screen:
  // the header, the cache and the stream all belong to it.
  const here = useActiveWorkspace();
  // There is deliberately no «it is the last one» guard, here or on the server: an
  // installation holding zero workspaces is a normal state the panel draws — it offers to
  // create one — and `leave` already reached it from the other side, by walking the last
  // member out. The guard refused the tidy way of doing what the untidy one allowed.
  const total = overview.workspaces.reduce((sum, w) => sum + w.disk.total, 0);

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-small font-medium uppercase tracking-wide text-muted-foreground">
          {t("ws.heading", { n: overview.workspaces.length, size: bytes(total) })}
        </h2>
        <InfoHint label={t("ws.diskHint")}>{t("ws.diskHint.body")}</InfoHint>
      </div>

      <div className="overflow-hidden rounded-lg border border-border">
        <Table minWidth="64rem">
          <THead>
            <TR>
              <TH>{t("ws.col.workspace")}</TH>
              <TH>{t("ws.col.chain")}</TH>
              <TH align="num">{t("ws.col.members")}</TH>
              <TH align="num">{t("ws.col.variants")}</TH>
              <TH>{t("ws.col.disk")}</TH>
              <TH>{t("ws.col.created")}</TH>
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
                    <span className="ml-2 text-small text-muted-foreground">
                      {t("ws.inMemory")}
                    </span>
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
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    title={t("ws.renameNamed", { name: workspace.name })}
                    onClick={() => setRenaming(workspace)}
                  >
                    <Pencil />
                  </Button>
                  <ExportButton workspace={workspace} />
                  <ClearCacheButton workspace={workspace} />
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    disabled={remove.isPending}
                    title={t("ws.deleteTitle")}
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

      {renaming ? (
        <RenameWorkspaceDialog workspace={renaming} onClose={() => setRenaming(null)} />
      ) : null}

      {target ? (
        <DeleteWorkspaceDialog
          workspace={target}
          here={target.slug === here}
          busy={remove.isPending}
          onClose={() => setTarget(null)}
          onConfirm={() =>
            remove.mutate(target.slug, {
              // Three outcomes, and the toast is the only place the middle one is visible:
              // you were moved to another instance, you were left with none, or the one that
              // went was not yours to be standing in.
              onSuccess: ({ landed }) => {
                setTarget(null);
                toast({
                  title: t("ws.deleted"),
                  description:
                    target.slug !== here
                      ? t("ws.deletedOther", { slug: target.slug })
                      : landed
                        ? t("ws.deletedMoved", { slug: target.slug, next: landed })
                        : t("ws.deletedHere", { slug: target.slug }),
                  tone: "attention",
                });
              },
              onError: (error: Error) =>
                toast({
                  title: t("ws.deleteFailed"),
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

/**
 * Only the NAME changes. The slug stays: it names the directory tree, the `X-Workspace`
 * header and every row that points at the workspace, so renaming it is not a rename but a
 * migration nobody has asked for — which is why it is shown, in monospace, and not offered.
 */
function RenameWorkspaceDialog({
  workspace,
  onClose,
}: {
  workspace: AdminWorkspace;
  onClose: () => void;
}) {
  const { t } = useT();
  const rename = useAdminRenameWorkspace();
  const [name, setName] = useState(workspace.name);
  const trimmed = name.trim();
  const valid = trimmed.length > 0 && trimmed.length <= 200 && trimmed !== workspace.name;

  return (
    <Dialog
      open
      onClose={onClose}
      title={t("ws.renameNamed", { name: workspace.name })}
      description={t("ws.slugUnchanged", { slug: workspace.slug })}
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button
            disabled={!valid || rename.isPending}
            onClick={() =>
              rename.mutate({ slug: workspace.slug, name: trimmed }, { onSuccess: onClose })
            }
          >
            {rename.isPending ? <Spinner /> : <Pencil />}
            {t("common.rename")}
          </Button>
        </>
      }
    >
      <div className="space-y-2">
        <Label htmlFor="workspace-name">{t("workspace.newName")}</Label>
        <Input
          id="workspace-name"
          autoFocus
          value={name}
          maxLength={200}
          onChange={(event) => setName(event.target.value)}
        />
        <FormError error={rename.error} />
      </div>
    </Dialog>
  );
}

function DiskCell({ workspace }: { workspace: AdminWorkspace }) {
  const { t } = useT();
  const { disk } = workspace;
  const parts = [
    [t("ws.disk.raw"), disk.raw],
    [t("ws.disk.instance"), disk.instance],
    [t("ws.disk.cache"), disk.cache],
    [t("ws.disk.history"), disk.history],
  ] as const;
  return (
    <span
      className="nums text-small"
      title={parts.map(([label, size]) => `${label}: ${bytes(size)}`).join(" · ")}
    >
      {bytes(disk.total)}
      <span className="ml-1 text-small text-muted-foreground">
        (
        {parts
          .filter(([, size]) => size > 0)
          .map(([label, size]) => `${label} ${bytes(size)}`)
          .join(", ") || t("ws.disk.empty")}
        )
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
  const { plural, t } = useT();
  const clear = useClearCache();
  const toast = useToast();
  const confirm = useConfirm();
  const askAndClear = async () => {
    const message = t("ws.clearConfirm", { slug: workspace.slug });
    if (!(await confirm({ title: message, tone: "danger" }))) return;
    clear.mutate(workspace.slug, {
      onSuccess: ({ files_removed, bytes_freed }) =>
        toast({
          title: t("ws.cacheCleared"),
          description: t("ws.cacheClearedBody", {
            files: plural("ws.files", files_removed),
            size: bytes(bytes_freed),
          }),
        }),
      onError: (error: Error) =>
        toast({ title: t("ws.clearFailed"), description: error.message, tone: "danger" }),
    });
  };
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      disabled={clear.isPending || workspace.disk.cache === 0}
      title={
        workspace.disk.cache === 0
          ? t("ws.cacheEmpty")
          : t("ws.clearHint")
      }
      onClick={askAndClear}
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
  const { plural, t } = useT();
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
        title: t("ws.exported"),
        description: t("ws.exportedBody", {
          files: plural("ws.files", Object.keys(bundle.files).length),
          slug: workspace.slug,
        }),
      });
    } catch (error) {
      toast({
        title: t("ws.exportFailed"),
        description: (error as Error).message,
        tone: "danger",
      });
    } finally {
      setBusy(false);
    }
  };
  return (
    <Button
      variant="ghost"
      size="icon-sm"
      disabled={busy}
      title={t("ws.exportHint")}
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
  const { t } = useT();
  const discard = useDeleteArtifact();
  const toast = useToast();

  const confirm = useConfirm();
  const askAndDiscard = async (artifact: AdminWorkspace["stages"][number]) => {
    const message = t("ws.discardConfirm", { label: artifact.label, slug: workspace.slug });
    if (!(await confirm({ title: message, tone: "danger" }))) return;
    discard.mutate(
      { slug: workspace.slug, artifact: artifact.artifact },
      {
        onSuccess: () =>
          toast({
            title: t("ws.stageCleared"),
            description: t("ws.stageClearedBody", {
              label: artifact.label,
              slug: workspace.slug,
            }),
            tone: "attention",
          }),
        onError: (error: Error) =>
          toast({ title: t("ws.clearFailed"), description: error.message, tone: "danger" }),
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
                ? t("ws.stageMissing", { label: artifactName(stage.artifact, t, stage.label) })
                : t("ws.clearStage", { label: artifactName(stage.artifact, t, stage.label), slug: workspace.slug })
            }
            onClick={() => askAndDiscard(stage)}
            className={cn(
              "rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              empty ? "cursor-default" : "hover:opacity-75",
            )}
          >
            <Badge variant={meta.tone as never}>
              {artifactName(stage.artifact, t, stage.label).split(" ")[0]} · {t(meta.labelKey).toLowerCase()}
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
  const { plural, t } = useT();
  const [typed, setTyped] = useState("");
  const built = workspace.stages.filter((stage) => stage.status !== "missing");

  return (
    <Dialog
      open
      onClose={onClose}
      title={t("ws.deleteDialog", { name: workspace.name })}
      description={t("ws.cannotUndo")}
      className="max-w-lg"
      footer={
        <>
          <Button variant="outline" onClick={onClose}>
            {t("common.cancel")}
          </Button>
          <Button
            variant="destructive"
            disabled={typed !== workspace.slug || busy}
            onClick={onConfirm}
          >
            {busy ? <Spinner /> : <Trash2 />}
            {t("common.delete")}
          </Button>
        </>
      }
    >
      <div className="space-y-3 text-body">
        <p>{t("ws.disappear", { size: bytes(workspace.disk.total) })}</p>
        <ul className="list-disc space-y-1 pl-5 text-muted-foreground">
          <li>
            {built.length > 0
              ? t("ws.builtArtifacts", {
                  names: built.map((s) => s.label.toLowerCase()).join(", "),
                })
              : t("ws.unbuiltArtifacts")}
          </li>
          <li>
            {t("ws.rawDocuments")}
            {workspace.disk.raw > 0 ? ` (${bytes(workspace.disk.raw)})` : ""}
          </li>
          <li>{t("ws.cachesAccess")}</li>
          <li>
            {workspace.generations > 0
              ? plural("ws.itsVariants", workspace.generations, {
                  n: plural("acc.savedVariants", workspace.generations),
                })
              : t("ws.itsComparisons")}
          </li>
        </ul>
        {here ? (
          <p className="text-muted-foreground">
            {t("ws.hereNow")}
          </p>
        ) : null}
        <div className="space-y-1">
          <Label htmlFor="confirm-slug">
            {t("ws.typeToConfirm")}
            <span className="font-mono normal-case">{workspace.slug}</span>
            {t("ws.typeToConfirm.tail")}
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
