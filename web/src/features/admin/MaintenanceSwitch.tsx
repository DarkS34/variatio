import { Wrench } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { InfoHint } from "@/components/ui/hint";
import { Textarea } from "@/components/ui/input";
import { Switch } from "@/components/ui/misc";
import { when } from "@/lib/format";
import { useAdminMaintenance, useSetMaintenance } from "@/state/queries";
import { useT } from "@/lib/i18n";

/**
 * The door of the installation, on the panel that runs it.
 *
 * It is deliberately NOT a seventh tab, nor a section of one. The six tabs are six subjects
 * an administrator works on; this is one switch that changes what everybody else sees, and
 * burying a switch of that reach one click deep is how it gets left on. It sits in the
 * header, silent while the door is open — one line beside the title, what it does behind an
 * (i) — and unmissable while it is not: a block of its own across the page, in red.
 *
 * The notice is editable while closed and the clock does not restart when it is: what the
 * waiting screen counts is how long the installation has been down, not how long ago
 * somebody rephrased the sentence.
 */
export function MaintenanceSwitch() {
  const { t } = useT();
  const maintenance = useAdminMaintenance();
  const save = useSetMaintenance();
  const state = maintenance.data;
  const active = state?.active ?? false;

  const [message, setMessage] = useState("");
  const [editing, setEditing] = useState(false);

  // The stored notice is the starting point, and only while nobody is mid-edit: writing
  // over somebody's half-typed sentence every time the poll answers would be worse than
  // showing a stale one.
  useEffect(() => {
    if (!editing && state) setMessage(state.message);
  }, [state?.message, editing, state]);

  const dirty = Boolean(state) && message.trim() !== state!.message && message.trim().length > 0;

  const toggle = (
    <Switch
      checked={active}
      disabled={save.isPending || maintenance.isLoading}
      label={t("maint.title")}
      onCheckedChange={(next) =>
        save.mutate({ active: next, message: next ? message.trim() || null : null })
      }
    />
  );

  if (!active) {
    return (
      <div className="flex items-center gap-2 pb-1 text-small text-muted-foreground">
        <Wrench className="size-4 shrink-0" />
        <span className="text-foreground">{t("maint.title")}</span>
        <InfoHint label={t("maint.hintLabel")}>{t("maint.body")}</InfoHint>
        <span className="ml-2">{t("maint.stateOpen")}</span>
        {toggle}
      </div>
    );
  }

  return (
    <section className="surface w-full bg-[color-mix(in_oklab,var(--destructive)_10%,var(--card))] p-4 sm:p-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <Wrench className="mt-0.5 size-4 shrink-0 animate-pulse-soft text-destructive" />
          <div className="min-w-0">
            <p className="font-medium">{t("maint.closed")}</p>
            <p className="text-small text-muted-foreground">
              {t("maint.closedBy", {
                by: state?.by ? t("maint.closedByWho", { name: state.by }) : "",
                when: when(state?.since ?? null),
              })}
            </p>
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          <span className="text-small text-muted-foreground">{t("maint.stateClosed")}</span>
          {toggle}
        </div>
      </div>

      <div className="mt-4 space-y-2 border-t border-border/60 pt-4">
        <Field
          label={t("maint.messageLabel")}
          description={t("maint.messageHelp")}
        >
          <Textarea
            value={message}
            // Empty is a legitimate state, so the placeholder is the very sentence the
            // waiting screen falls back to — in the reader's own language, there and here.
            placeholder={t("maintenance.defaultMessage")}
            maxLength={400}
            rows={2}
            onFocus={() => setEditing(true)}
            onBlur={() => setEditing(false)}
            onChange={(event) => setMessage(event.target.value)}
          />
        </Field>
        <div className="flex flex-wrap items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={!dirty || save.isPending}
            onClick={() => {
              setEditing(false);
              save.mutate({ active: true, message: message.trim() });
            }}
          >
            {t("maint.saveNotice")}
          </Button>
          {save.isError ? (
            <span className="text-small text-destructive">{(save.error as Error).message}</span>
          ) : null}
        </div>
      </div>
    </section>
  );
}
