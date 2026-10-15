import { useMutation, useQuery } from "@tanstack/react-query";
import { Trash2 } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useConfirm } from "@/components/ui/confirm";
import { Alert } from "@/components/ui/misc";
import { api } from "@/lib/api";
import { fieldText } from "@/lib/fields";
import { truncate } from "@/lib/format";
import { useT } from "@/lib/i18n";
import type { BankItemType, ExemplarsProfile, KgConcept, SetAsideItem } from "@/lib/types";
import { useActiveWorkspace } from "@/state/queries";

import { AddExerciseDialog } from "./AddExercise";

// What an exercise carries beside its fields, which the form does not edit.
const META = new Set(["origin", "added_by", "added_at", "concepts", "primary_concept", "_tagging", "source", "item_type"]);

/**
 * The exercises a re-extraction could not keep, over the bank's table while there are any.
 *
 * A teacher's exercise, or a generated one passed in, comes from no document: a re-extraction
 * keeps it (`bank_edit.seed`), unless it no longer fits its type of exercise — then it is put
 * aside instead of lost. Each comes back corrected, through the dialog of «Nuevo ejercicio»,
 * as it was: where it came from, who added it and when. Or it is let go, asked first.
 */
export function SetAside({
  itemTypes,
  profile,
  concepts,
  onBack,
}: {
  itemTypes: BankItemType[];
  profile: ExemplarsProfile | null;
  concepts: KgConcept[];
  /** Called once one is back in the bank. */
  onBack: () => void;
}) {
  const { t, plural } = useT();
  const confirm = useConfirm();
  const workspace = useActiveWorkspace();
  const [restoring, setRestoring] = useState<SetAsideItem | null>(null);
  const listing = useQuery({ queryKey: ["bank", workspace, "set-aside"], queryFn: api.setAside });
  const drop = useMutation({
    mutationFn: (key: string) => api.dropSetAside(key),
    onSuccess: () => listing.refetch(),
  });
  const items = listing.data?.items ?? [];
  if (items.length === 0) return null;

  return (
    <>
      <Alert tone="attention" title={plural("bank.aside.title", items.length)}>
        <p>{t("bank.aside.body")}</p>
        <ul className="rows rows-tight mt-2">
          {items.map((entry) => {
            const type = itemTypes.find((candidate) => candidate.key === entry.item.item_type) ?? itemTypes[0];
            const statement = type ? fieldText(entry.item[type.primary_field]) : "";
            return (
              <li key={entry.key} className="flex items-center gap-3">
                <span className="font-mono text-small text-muted-foreground">{entry.id}</span>
                <span className="min-w-0 flex-1 truncate text-foreground">{truncate(statement, 160)}</span>
                <Button size="sm" variant="outline" className="h-7" onClick={() => setRestoring(entry)}>
                  {t("bank.aside.restore")}
                </Button>
                <Button
                  size="icon-sm"
                  variant="ghost"
                  aria-label={t("bank.aside.drop", { id: entry.id })}
                  title={t("bank.aside.drop", { id: entry.id })}
                  onClick={async () => {
                    if (await confirm({ title: t("bank.aside.dropConfirm", { id: entry.id }), tone: "danger" }))
                      drop.mutate(entry.key);
                  }}
                >
                  <Trash2 />
                </Button>
              </li>
            );
          })}
        </ul>
      </Alert>

      {restoring ? (
        <AddExerciseDialog
          itemTypes={itemTypes}
          profile={profile}
          concepts={concepts}
          start={{
            itemType: typeof restoring.item.item_type === "string" ? restoring.item.item_type : null,
            fields: Object.fromEntries(Object.entries(restoring.item).filter(([name]) => !META.has(name))),
            concepts: Array.isArray(restoring.item.concepts) ? (restoring.item.concepts as string[]) : [],
            primary: typeof restoring.item.primary_concept === "string" ? restoring.item.primary_concept : null,
          }}
          title={t("bank.aside.restoreTitle")}
          description={t("bank.aside.restoreDescription")}
          saveLabel={t("bank.aside.restoreTitle")}
          another={false}
          save={(body) => api.addItem({ ...body, set_aside: restoring.key })}
          onClose={(saved) => {
            setRestoring(null);
            listing.refetch();
            if (saved.length > 0) onBack();
          }}
        />
      ) : null}
    </>
  );
}
