import { Crown, Download, Eraser, Eye, MessagesSquare, Pencil, Trash2 } from "lucide-react";
import { lazy, Suspense, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Select } from "@/components/ui/input";
import { Skeleton, Spinner } from "@/components/ui/misc";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/table";
import { useConfirm } from "@/components/ui/confirm";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { api } from "@/lib/api";
import { ARTIFACT_STATUS, bytes, when } from "@/lib/format";
import type { AdminAccount, AdminOverview, AdminWorkspace } from "@/lib/types";
import { cn } from "@/lib/utils";
import {
  useActiveWorkspace,
  useAdminDeleteWorkspace,
  useAdminRenameWorkspace,
  useClearCache,
  useDeleteArtifact,
  useMembershipActions,
} from "@/state/queries";
import { ROLE_LABEL_KEYS } from "@/state/auth";
import { PeopleWhoLoseAccess } from "@/features/workspaces/PeopleWhoLoseAccess";
import { useT, withCatalogues } from "@/lib/i18n";
import { artifactName } from "@/lib/names";

import { ClassLinksBlock } from "./ClassLinksBlock";
import { SectionHeader } from "./Sections";
import { WorkspaceGenerations } from "./WorkspaceGenerations";

// The tutor's code, fetched when the administrator opens a subject's conversations. Offered
// whatever the tutor's mode: the administrator reads them read-only even with it closed.
const AdminConversations = lazy(() =>
  withCatalogues(import("@/tutor/AdminConversations")).then((m) => ({
    default: m.AdminConversations,
  })),
);

/**
 * The installation's instances, and what this panel writes about them: their name, their
 * removal, or the regenerable half of what they hold.
 *
 * Its exercise count opens every exercise generated there, read-only: the one place anybody
 * reads exercises that are not their own.
 *
 * Emptying a stage and deleting the workspace are one decision at two scopes, so they live
 * in the same row. Neither builds nor approves anything — for that one enters the instance,
 * where what is being touched can be seen.
 *
 * Renaming is here and NOWHERE else, and the owner-facing route is gone rather than merely
 * hidden: the client never decides a permission. This is the screen where every instance is
 * visible at once, which is what makes it the place to notice a name colliding.
 */
export function WorkspacesTab({ overview }: { overview: AdminOverview }) {
  const { t, plural } = useT();
  const remove = useAdminDeleteWorkspace();
  const toast = useToast();
  const [target, setTarget] = useState<AdminWorkspace | null>(null);
  const [renaming, setRenaming] = useState<AdminWorkspace | null>(null);
  // Which one this tab has open, which is the one deletion has consequences for on screen:
  // the header, the cache and the stream all belong to it.
  const here = useActiveWorkspace();
  // There is deliberately no "it is the last one" guard, here or on the server: an
  // installation holding zero workspaces is a normal state the panel draws — it offers to
  // create one — and `leave` already reached it from the other side, by walking the last
  // member out. The guard refused the tidy way of doing what the untidy one allowed.
  const [viewingSlug, setViewingSlug] = useState<string | null>(null);
  // By slug, so the view follows the overview's refreshes and closes if the row goes.
  const viewing = overview.workspaces.find((w) => w.slug === viewingSlug) ?? null;
  const setViewing = (workspace: AdminWorkspace | null) => setViewingSlug(workspace?.slug ?? null);
  // The tutor's conversations of one subject, the administrator's other read across accounts.
  const [talksSlug, setTalksSlug] = useState<string | null>(null);
  const talks = overview.workspaces.find((w) => w.slug === talksSlug) ?? null;
  // The subject whose owner is being chosen, by slug for the same reason as `viewing`.
  const [owningSlug, setOwningSlug] = useState<string | null>(null);
  const owning = overview.workspaces.find((w) => w.slug === owningSlug) ?? null;

  // One section, so no list of sections beside it (the user's call, 2026-10-04): the tab
  // is its header and its table at full width, and the two reads opened from a row — a
  // subject's exercises, its conversations — take the table's place.
  if (viewing) {
    return <WorkspaceGenerations workspace={viewing} onBack={() => setViewing(null)} />;
  }
  if (talks) {
    return (
      <Suspense fallback={<Skeleton className="h-96" />}>
        <AdminConversations workspace={talks} onBack={() => setTalksSlug(null)} />
      </Suspense>
    );
  }

  return (
    <div className="space-y-7">
      <SectionHeader
        title={t("admin.tab.workspaces")}
        description={t("ws.note", {
          subjects: plural("ws.count", overview.workspaces.length),
          exercises: plural("acc.savedVariants", overview.totals.generations),
        })}
      />

      <div className="surface overflow-hidden p-2">
        <Table minWidth="60rem">
          <THead>
            <TR>
              <TH>{t("ws.col.workspace")}</TH>
              <TH>{t("ws.col.chain")}</TH>
              <TH>{t("ws.col.owner")}</TH>
              <TH align="num">{t("ws.col.students")}</TH>
              <TH align="num">{t("ws.col.variants")}</TH>
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
                <TD className="px-3 py-2">
                  <OwnerCell workspace={workspace} onChoose={() => setOwningSlug(workspace.slug)} />
                </TD>
                <TD align="num" className="px-3 py-2 nums">
                  {workspace.people ? workspace.people.students : "—"}
                </TD>
                <TD align="num" className="px-3 py-2 nums">
                  {workspace.generations > 0 ? (
                    // A button that says what it opens: as a bare underlined figure it read
                    // as a number, not as the way into the subject's exercises.
                    <Button
                      variant="outline"
                      size="sm"
                      title={t("ws.viewVariants", { name: workspace.name })}
                      onClick={() => setViewing(workspace)}
                    >
                      <Eye />
                      {plural("ws.viewCount", workspace.generations)}
                    </Button>
                  ) : (
                    <span className="text-muted-foreground">0</span>
                  )}
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
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    title={t("tutor.admin.view", { name: workspace.name })}
                    aria-label={t("tutor.admin.view", { name: workspace.name })}
                    onClick={() => setTalksSlug(workspace.slug)}
                  >
                    <MessagesSquare />
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

      <ClassLinksBlock
        names={Object.fromEntries(overview.workspaces.map((row) => [row.slug, row.name]))}
      />

      {renaming ? (
        <RenameWorkspaceDialog workspace={renaming} onClose={() => setRenaming(null)} />
      ) : null}

      {owning ? (
        <ChooseOwnerDialog
          workspace={owning}
          accounts={overview.accounts}
          onClose={() => setOwningSlug(null)}
        />
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
 * Who owns the subject, by name; or that nobody does, with the way to choose somebody. An
 * API older than the field says nothing rather than «Sin propietario».
 */
function OwnerCell({ workspace, onChoose }: { workspace: AdminWorkspace; onChoose: () => void }) {
  const { t } = useT();
  if (!workspace.owners) return <span className="text-muted-foreground">—</span>;
  if (workspace.owners.length === 0) {
    return (
      <span className="flex flex-wrap items-center gap-2">
        <Badge variant="danger">{t("ws.noOwner")}</Badge>
        <Button size="sm" variant="outline" onClick={onChoose}>
          <Crown />
          {t("ws.chooseOwner")}
        </Button>
      </span>
    );
  }
  return (
    <span className="block max-w-[14rem] truncate" title={workspace.owners.map((o) => o.username).join(", ")}>
      {workspace.owners.map((owner) => owner.name).join(", ")}
    </span>
  );
}

/**
 * Giving a subject with nobody to own it an owner: one of its own people raised, or a
 * teacher's account let in as owner. The membership is the administrator's grant
 * (`POST /api/admin/accounts/{id}/memberships`), which raises a role and never lowers one.
 */
function ChooseOwnerDialog({
  workspace,
  accounts,
  onClose,
}: {
  workspace: AdminWorkspace;
  accounts: AdminAccount[];
  onClose: () => void;
}) {
  const { t } = useT();
  const toast = useToast();
  const { grant } = useMembershipActions();
  const inside = accounts.filter(
    (account) =>
      !account.disabled &&
      account.workspaces.some((row) => row.slug === workspace.slug && !row.disabled),
  );
  const outside = accounts.filter(
    (account) =>
      !account.disabled &&
      account.evaluator_profile === "teacher" &&
      !account.workspaces.some((row) => row.slug === workspace.slug),
  );
  const [other, setOther] = useState<string>("");

  const make = (account: AdminAccount) =>
    grant.mutate(
      { id: account.id, workspace: workspace.slug, role: "owner" },
      {
        onSuccess: () => {
          toast({ title: t("ws.ownerChosen", { name: account.name, subject: workspace.name }) });
          onClose();
        },
        onError: (error: Error) =>
          toast({ title: t("ws.ownerFailed"), description: error.message, tone: "danger" }),
      },
    );

  return (
    <Dialog
      open
      onClose={onClose}
      title={t("ws.chooseOwnerTitle", { name: workspace.name })}
      description={t("ws.chooseOwnerBody")}
      className="max-w-lg"
    >
      <div className="space-y-4">
        {inside.length > 0 ? (
          <ul className="rows">
            {inside.map((account) => {
              const role = account.workspaces.find((row) => row.slug === workspace.slug)?.role;
              return (
                <li key={account.id} className="flex items-center gap-3 py-2">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-medium">{account.name}</span>
                    <span className="block truncate text-small text-muted-foreground">
                      <span className="font-mono">{account.username}</span>
                      {role ? ` · ${t(ROLE_LABEL_KEYS[role])}` : ""}
                    </span>
                  </span>
                  <Button size="sm" variant="outline" disabled={grant.isPending} onClick={() => make(account)}>
                    <Crown />
                    {t("ws.makeOwner")}
                  </Button>
                </li>
              );
            })}
          </ul>
        ) : (
          <p className="text-small text-muted-foreground">{t("ws.nobodyInside")}</p>
        )}
        {outside.length > 0 ? (
          <div className="flex flex-wrap items-end gap-2">
            <div className="min-w-0 flex-1 space-y-1">
              <Label htmlFor="owner-other">{t("ws.otherTeacher")}</Label>
              <Select id="owner-other" value={other} onChange={(event) => setOther(event.target.value)}>
                <option value="">—</option>
                {outside.map((account) => (
                  <option key={account.id} value={String(account.id)}>
                    {account.name} ({account.username})
                  </option>
                ))}
              </Select>
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={!other || grant.isPending}
              onClick={() => {
                const account = outside.find((row) => String(row.id) === other);
                if (account) make(account);
              }}
            >
              <Crown />
              {t("ws.makeOwner")}
            </Button>
          </div>
        ) : null}
      </div>
    </Dialog>
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
 * Emptying leaves the artifact "missing" and its workspace standing: the curated file, the
 * draft and the cache derivations that spoke of it are deleted. The copies under
 * `.history/` are untouched, so a mistaken deletion is undone from "Restaurar" on the
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
        <PeopleWhoLoseAccess people={workspace.people} others={0} />
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
