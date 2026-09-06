import { useEffect, useState, type ReactNode } from "react";

import { Button } from "./button";
import { Dialog } from "./dialog";
import { Input } from "./input";
import { Spinner } from "./misc";
import { useT } from "@/lib/i18n";

/**
 * ASKING AND CONFIRMING, IN THIS APPLICATION'S OWN LANGUAGE.
 *
 * The graph asked for a unit's name with `window.prompt` and destroyed one with
 * `window.confirm`, while deleting a workspace opened a considered dialog that makes you
 * type the slug. Two visual languages for one act, and the cheaper one guarded the more
 * destructive operation: `window.confirm` on "eliminar la unidad y sus 28 conceptos"
 * against a typed confirmation on an empty instance.
 *
 * The native dialogs are also the only surfaces in the product that ignore the theme, the
 * typography and the focus ring, and `prompt` cannot validate: it does not know which
 * names are taken, so the only way to find out was to press OK and read the error.
 *
 * Two components, one primitive:
 *   - `PromptDialog` asks for one line, validating as it is typed.
 *   - `ConfirmDialog` confirms an action, with `tone` deciding how much ceremony it gets.
 */

export function PromptDialog({
  open,
  title,
  description,
  label,
  initial = "",
  confirmLabel,
  validate,
  onCancel,
  onConfirm,
  pending = false,
}: {
  open: boolean;
  title: string;
  description?: ReactNode;
  label: string;
  initial?: string;
  confirmLabel?: string;
  /** The reason this value is not acceptable, or null. Runs on every keystroke. */
  validate?: (value: string) => string | null;
  onCancel: () => void;
  onConfirm: (value: string) => void;
  pending?: boolean;
}) {
  const { t } = useT();
  const [value, setValue] = useState(initial);
  const [touched, setTouched] = useState(false);

  // Reopening for a different subject must not inherit the last answer: the graph reuses
  // one dialog for "nueva unidad" and "renombrar", and the second arrives with the current
  // name in it.
  useEffect(() => {
    if (open) {
      setValue(initial);
      setTouched(false);
    }
  }, [open, initial]);

  const trimmed = value.trim();
  const error = trimmed ? (validate?.(trimmed) ?? null) : t("prompt.required");
  const submit = () => {
    setTouched(true);
    if (!error) onConfirm(trimmed);
  };

  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title={title}
      description={description}
      className="max-w-md"
      footer={
        <>
          <Button variant="outline" onClick={onCancel}>
            {t("common.cancel")}
          </Button>
          <Button onClick={submit} disabled={pending}>
            {pending ? <Spinner /> : null}
            {confirmLabel ?? t("common.save")}
          </Button>
        </>
      }
    >
      <div className="space-y-1.5">
        <Input
          aria-label={label}
          placeholder={label}
          autoFocus
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              submit();
            }
          }}
        />
        {touched && error ? <p className="text-small text-destructive">{error}</p> : null}
      </div>
    </Dialog>
  );
}

export function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  tone = "default",
  onCancel,
  onConfirm,
  pending = false,
}: {
  open: boolean;
  title: string;
  children?: ReactNode;
  confirmLabel?: string;
  /** `danger` paints the confirming button as destructive. Nothing else changes. */
  tone?: "default" | "danger";
  onCancel: () => void;
  onConfirm: () => void;
  pending?: boolean;
}) {
  const { t } = useT();
  return (
    <Dialog
      open={open}
      onClose={onCancel}
      title={title}
      className="max-w-md"
      footer={
        <>
          <Button variant="outline" onClick={onCancel}>
            {t("common.cancel")}
          </Button>
          <Button
            variant={tone === "danger" ? "destructive" : "default"}
            onClick={onConfirm}
            disabled={pending}
          >
            {pending ? <Spinner /> : null}
            {confirmLabel ?? t("common.confirm")}
          </Button>
        </>
      }
    >
      {children ? <div className="space-y-2 text-body">{children}</div> : null}
    </Dialog>
  );
}
