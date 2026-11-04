import { useCallback } from "react";

import { useConfirm } from "@/components/ui/confirm";
import { useT } from "@/lib/i18n";

/**
 * Ask before a model changes what it serves: one dialog per change, before it enters the
 * draft (the user's request of 2026-11-04). Which model reads, extracts or writes for a
 * phase decides what every later build or exercise is made of, and the select that changes
 * it sits one stray click away from the reasoning switch beside it.
 *
 * `what` names the phase or function, `from` and `to` the model (or models) before and
 * after; null reads as "none".
 */
export function useConfirmModelChange() {
  const confirm = useConfirm();
  const { t } = useT();
  return useCallback(
    (what: string, from: string | null, to: string | null) =>
      confirm({
        title: t("cfg.modelChange.title", { what }),
        body: t("cfg.modelChange.body", {
          from: from || t("cfg.modelChange.none"),
          to: to || t("cfg.modelChange.none"),
        }),
        confirmLabel: t("cfg.modelChange.confirm"),
      }),
    [confirm, t],
  );
}
