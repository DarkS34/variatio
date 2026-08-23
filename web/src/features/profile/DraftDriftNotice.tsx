import { Alert } from "@/components/ui/misc";

import { aspectList, hasDrift, modalities, type ProfilePendingDraft } from "./drift";

export function DraftDriftNotice({ pending }: { pending: ProfilePendingDraft | null | undefined }) {
  if (!pending || !hasDrift(pending.drift)) return null;
  const { added, removed, changed } = pending.drift;

  return (
    <Alert tone="attention" title="La última construcción propone otro esquema">
      <p>
        El constructor escribió un borrador que no coincide con el perfil curado. El borrador no se
        lee mientras exista el curado; lo que sigue es solo lo que cambiaría. Una comisión que fije
        un campo que el borrador elimina dejaría de ser reproducible si se adoptara.
      </p>
      <ul className="mt-2 list-disc space-y-0.5 pl-5">
        {removed.map((entry) => (
          <li key={`removed-${entry.field}`}>
            El nuevo borrador elimina «<code className="font-mono">{entry.field}</code>» (usado por{" "}
            {modalities(entry.item_types.length)}
            {entry.decided_by === "user" ? ", y lo decide quien pide el ejercicio" : ""})
          </li>
        ))}
        {added.map((entry) => (
          <li key={`added-${entry.field}`}>
            El nuevo borrador añade «<code className="font-mono">{entry.field}</code>» (en{" "}
            {modalities(entry.item_types.length)})
          </li>
        ))}
        {changed.map((entry) => (
          <li key={`changed-${entry.field}`}>
            El nuevo borrador cambia «<code className="font-mono">{entry.field}</code>»:{" "}
            {aspectList(entry.aspects)} (en {modalities(entry.item_types.length)})
          </li>
        ))}
      </ul>
      <p className="mt-2 text-small text-muted-foreground">
        Borrador en <code className="font-mono">{pending.path}</code>. Para adoptarlo, pégalo en
        la pestaña «JSON crudo» y guarda.
      </p>
    </Alert>
  );
}
