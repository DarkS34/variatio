import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Library } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { fieldLabel, itemTypeOf } from "@/lib/profile";
import type { GenerationRow } from "@/lib/types";
import { useInvalidateChain, useKg, useProfile } from "@/state/queries";

import { AddExerciseDialog } from "./AddExercise";
import { typeSummaries } from "./exercise";

/**
 * «Pasar al banco»: a teacher's generated exercise goes into the bank as an exemplar.
 *
 * The same dialog as writing one by hand, opened on the exercise as the model wrote it, to be
 * corrected first if need be — the correction goes to the bank, and the file stays the record
 * of what the model wrote. A field the commission left out opens the form to write it, since
 * an exemplar carries every field of its type. The system tags it by default, as every other
 * exemplar was; «Los elijo yo» opens on the concepts it was generated for.
 */
export function PromoteDialog({
  generation,
  onClose,
}: {
  generation: GenerationRow;
  onClose: (promoted: boolean) => void;
}) {
  const { t, plural } = useT();
  const client = useQueryClient();
  const invalidate = useInvalidateChain();
  const profile = useProfile().data?.profile ?? null;
  const concepts = useKg().data?.concepts ?? [];
  const spec = profile ? itemTypeOf(profile, { item_type: generation.item_type }) : null;
  const typeLabel = spec?.label || generation.item_type;
  const missing = (generation.omit ?? []).filter((field) => spec?.fields?.[field]);
  const named = missing.map((field) => fieldLabel(field, spec));
  const targets = generation.targets?.length ? generation.targets : generation.concepts;

  return (
    <AddExerciseDialog
      itemTypes={typeSummaries(profile)}
      profile={profile}
      concepts={concepts}
      start={{
        itemType: generation.item_type || null,
        fields: generation.item,
        concepts: targets,
        primary: targets[0] ?? null,
        note: missing.length ? plural("bank.promote.missing", missing.length, { fields: named.join(", ") }) : null,
        reading: missing.length === 0,
        lockType: true,
      }}
      title={t("bank.promote.title")}
      description={t("bank.promote.description", { type: typeLabel })}
      saveLabel={t("bank.promote")}
      another={false}
      // A server that says what may be passed in says what the class sees too.
      canShow={"promotable" in generation}
      save={(body) =>
        api.promote(generation.id, {
          fields: body.fields,
          tag: body.tag,
          concepts: body.concepts,
          primary_concept: body.primary_concept,
          visibility: body.visibility,
        })
      }
      onClose={(saved) => {
        if (saved.length > 0) {
          invalidate();
          client.invalidateQueries({ queryKey: ["generations"] });
        }
        onClose(saved.length > 0);
      }}
    />
  );
}

/**
 * «Pasar al banco» on a generated exercise of «Generar ejercicios», or what it became.
 *
 * Drawn only where the server says this account may pass it (`promotable`): a teacher's own,
 * not in the bank. One in the bank says so instead. An API that sends neither draws nothing.
 */
export function PromoteButton({ row }: { row: GenerationRow }) {
  const { t } = useT();
  const [open, setOpen] = useState(false);
  if (row.in_bank) {
    return (
      <Badge variant="secondary" className="gap-1 self-center">
        <Library className="size-3" />
        {t("generations.inBank", { id: row.in_bank })}
      </Badge>
    );
  }
  if (!row.promotable) return null;
  return (
    <>
      <Button variant="outline" size="sm" className="h-7" onClick={() => setOpen(true)}>
        <Library />
        {t("bank.promote")}
      </Button>
      {open ? <PromoteDialog generation={row} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

/** `PromoteButton` for a result of the run, read off its saved file once it exists. */
export function PromoteSaved({ id }: { id: string }) {
  const detail = useQuery({
    queryKey: ["generations", "detail", id],
    queryFn: () => api.generation(id),
  });
  const row = detail.data?.generation;
  return row ? <PromoteButton row={row} /> : null;
}
