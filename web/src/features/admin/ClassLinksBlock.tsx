import { Pause, Play, Trash2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { LoadError, Skeleton } from "@/components/ui/misc";
import { useToast } from "@/components/ui/toast";
import { dateTime } from "@/lib/format";
import { useT } from "@/lib/i18n";
import type { AdminClassLink } from "@/lib/types";
import { useAdminClassLinkActions, useAdminClassLinks } from "@/state/queries";

/**
 * Every subject's live class link, for the administrator: how full, until when, who minted
 * it, and the two things the panel does with one — pause it or revoke it. Its seats and its
 * date stay its teachers' («Clase → Invitar»).
 */
export function ClassLinksBlock({ names }: { names: Record<string, string> }) {
  const { t } = useT();
  const read = useAdminClassLinks();
  const links = read.data?.class_links ?? [];
  return (
    <section className="surface space-y-3 p-5" aria-labelledby="admin-class-links">
      <div className="space-y-1">
        <h3 id="admin-class-links" className="flex items-baseline gap-2 text-heading">
          {t("ws.classLinks.title")}
          {links.length > 0 ? (
            <span className="nums text-small font-normal text-muted-foreground">{links.length}</span>
          ) : null}
        </h3>
        <p className="max-w-3xl text-small text-muted-foreground">{t("ws.classLinks.lead")}</p>
      </div>
      {read.isError ? (
        <LoadError title={t("ws.classLinks.unreadable")} error={read.error} onRetry={() => read.refetch()} />
      ) : read.isLoading ? (
        <Skeleton className="h-16" />
      ) : links.length === 0 ? (
        <p className="text-small text-muted-foreground">{t("ws.classLinks.none")}</p>
      ) : (
        <ul className="rows">
          {links.map((link) => (
            <ClassLinkRow key={link.id} link={link} name={names[link.workspace] ?? link.workspace_name} />
          ))}
        </ul>
      )}
    </section>
  );
}

function ClassLinkRow({ link, name }: { link: AdminClassLink; name: string }) {
  const { t } = useT();
  const confirm = useConfirm();
  const toast = useToast();
  const { pause, revoke } = useAdminClassLinkActions();
  const failed = (error: Error) =>
    toast({ title: t("class.failed"), description: error.message, tone: "danger" });

  const toggle = () =>
    pause.mutate(
      { id: link.id, paused: !link.paused },
      {
        onSuccess: () =>
          toast({ title: t(link.paused ? "class.link.resumedToast" : "class.link.pausedToast"), description: name }),
        onError: failed,
      },
    );

  const retire = async () => {
    const asked = await confirm({
      title: t("ws.classLinks.revokeConfirm", { name }),
      body: t("ws.classLinks.revokeConfirmBody"),
      confirmLabel: t("ws.classLinks.revoke"),
      tone: "danger",
    });
    if (!asked) return;
    revoke.mutate(link.id, {
      onSuccess: () => toast({ title: t("ws.classLinks.revoked"), description: name, tone: "attention" }),
      onError: failed,
    });
  };

  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 py-2">
      <div className="min-w-64 flex-1">
        <p className="flex flex-wrap items-center gap-1.5">
          <span className="font-medium">{name}</span>
          <span className="font-mono text-micro text-muted-foreground">{link.workspace}</span>
          <Badge variant={link.expired || link.paused ? "outline" : "settled"}>
            {t(link.expired ? "class.link.state.expired" : link.paused ? "class.link.state.paused" : "class.link.state.live")}
          </Badge>
        </p>
        <p className="text-small text-muted-foreground">
          <span className="nums">{t("class.link.seats", { uses: link.uses, max: link.max_uses })}</span>
          {" · "}
          {t(link.expired ? "class.link.expiredOn" : "class.link.expiresOn", { date: dateTime(link.expires_at) })}
          {link.created_by ? ` · ${t("class.invitedBy", { name: link.created_by })}` : ""}
        </p>
      </div>
      <div className="ml-auto flex items-center gap-1">
        {link.expired ? null : (
          <Button size="sm" variant="ghost" disabled={pause.isPending} onClick={toggle}>
            {link.paused ? <Play /> : <Pause />}
            {t(link.paused ? "class.link.resume" : "class.link.pause")}
          </Button>
        )}
        <Button
          size="sm"
          variant="ghost"
          className="text-destructive hover:bg-destructive/10"
          disabled={revoke.isPending}
          onClick={retire}
        >
          <Trash2 />
          {t("ws.classLinks.revoke")}
        </Button>
      </div>
    </li>
  );
}
