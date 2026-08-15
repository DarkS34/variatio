import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import { useChangePassword } from "@/state/auth";

import { FormError } from "./AuthLayout";

export function ChangePasswordDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const change = useChangePassword();

  const mismatch = repeat.length > 0 && next !== repeat;

  const close = () => {
    setCurrent("");
    setNext("");
    setRepeat("");
    change.reset();
    onClose();
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (mismatch) return;
    change.mutate({ current, next });
  };

  return (
    <Dialog
      open={open}
      onClose={close}
      title="Cambiar la contraseña"
      // Said out loud because it is surprising otherwise: the change signs out every
      // other device on purpose, since the usual reason to change it is a suspicion.
      description="Se cerrará la sesión en el resto de dispositivos."
      className="max-w-md"
    >
      {change.isSuccess ? (
        <div className="flex flex-col gap-4">
          <p className="text-sm">Hecho. Esta pestaña sigue abierta con una sesión nueva.</p>
          <Button onClick={close}>Cerrar</Button>
        </div>
      ) : (
        <form onSubmit={submit} className="flex flex-col gap-4">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="current-password">Contraseña actual</Label>
            <Input
              id="current-password"
              type="password"
              autoComplete="current-password"
              required
              value={current}
              onChange={(event) => setCurrent(event.target.value)}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="next-password">Nueva</Label>
            <Input
              id="next-password"
              type="password"
              autoComplete="new-password"
              required
              value={next}
              onChange={(event) => setNext(event.target.value)}
            />
            <p className="text-xs text-muted-foreground">Al menos 12 caracteres.</p>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="repeat-password">Repítela</Label>
            <Input
              id="repeat-password"
              type="password"
              autoComplete="new-password"
              required
              value={repeat}
              onChange={(event) => setRepeat(event.target.value)}
            />
            {mismatch ? <p className="text-xs text-destructive">Las dos no coinciden.</p> : null}
          </div>

          <FormError error={change.error} />

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={close}>
              Cancelar
            </Button>
            <Button type="submit" disabled={change.isPending || mismatch}>
              {change.isPending ? <Spinner /> : null}
              Guardar
            </Button>
          </div>
        </form>
      )}
    </Dialog>
  );
}
