import { Check, Copy, Mail, Trash2 } from "lucide-react";
import { useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { Input, Label, Select } from "@/components/ui/input";
import { Spinner } from "@/components/ui/misc";
import type { Role } from "@/lib/types";
import {
  ROLE_HINTS,
  ROLE_LABELS,
  useCreateInvite,
  useInvites,
  useMemberActions,
  useMembers,
  useRevokeInvite,
  useSession,
} from "@/state/auth";

import { FormError } from "./AuthLayout";

const ROLES: Role[] = ["viewer", "editor", "owner"];

/**
 * Who is in this workspace and who has been invited to it.
 *
 * Only an owner opens this, and the API says so as well — the dialog never decides a
 * permission on its own, it just avoids showing a control that would 403.
 */
export function PeopleDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const session = useSession();
  const members = useMembers(open);
  const invites = useInvites(open);

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="Personas e invitaciones"
      description="Quién puede entrar en esta instancia y con qué permiso."
      className="max-w-3xl"
    >
      <div className="flex flex-col gap-6">
        <InviteForm />

        <section className="flex flex-col gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Miembros
          </h3>
          {members.isLoading ? <Spinner /> : null}
          <ul className="flex flex-col divide-y divide-border rounded-lg border border-border">
            {(members.data?.members ?? []).map((member) => (
              <MemberRowView
                key={member.id}
                id={member.id}
                email={member.email}
                name={member.name}
                role={member.role}
                self={member.id === session.data?.user.id}
              />
            ))}
          </ul>
        </section>

        {(invites.data?.invites ?? []).length > 0 ? (
          <section className="flex flex-col gap-2">
            <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Invitaciones pendientes
            </h3>
            <ul className="flex flex-col divide-y divide-border rounded-lg border border-border">
              {invites.data!.invites.map((invite) => (
                <InviteRowView
                  key={invite.id}
                  id={invite.id}
                  email={invite.email}
                  role={invite.role}
                  expiresAt={invite.expires_at}
                />
              ))}
            </ul>
          </section>
        ) : null}
      </div>
    </Dialog>
  );
}

function InviteForm() {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("editor");
  const create = useCreateInvite();

  return (
    <section className="flex flex-col gap-3">
      <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Invitar a alguien
      </h3>

      <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
        <div className="flex flex-1 flex-col gap-1.5">
          <Label htmlFor="invite-to">Correo (opcional)</Label>
          <Input
            id="invite-to"
            type="email"
            placeholder="colega@universidad.es"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <Label htmlFor="invite-role">Permiso</Label>
          <Select
            id="invite-role"
            value={role}
            onChange={(event) => setRole(event.target.value as Role)}
          >
            {ROLES.map((option) => (
              <option key={option} value={option}>
                {ROLE_LABELS[option]}
              </option>
            ))}
          </Select>
        </div>
        <Button
          onClick={() => create.mutate({ email: email.trim() || null, role })}
          disabled={create.isPending}
        >
          {create.isPending ? <Spinner /> : <Mail />}
          Crear invitación
        </Button>
      </div>

      <p className="text-xs text-muted-foreground">{ROLE_HINTS[role]}</p>
      <FormError error={create.error} />

      {create.isSuccess ? <InviteLink link={create.data.link} mailed={create.data.mailed} /> : null}
    </section>
  );
}

/** The link is shown whether or not the mail went out — with no SMTP it is the delivery. */
function InviteLink({ link, mailed }: { link: string; mailed: boolean }) {
  const [copied, setCopied] = useState(false);
  return (
    <div className="flex flex-col gap-2 rounded-lg border border-border bg-muted/40 p-3">
      <p className="text-sm">
        {mailed
          ? "Invitación enviada. Este es el mismo enlace, por si hace falta."
          : "Sin correo configurado: pásale tú este enlace. Solo sirve una vez."}
      </p>
      <div className="flex items-center gap-2">
        <code className="min-w-0 flex-1 truncate rounded bg-background px-2 py-1 font-mono text-xs">
          {link}
        </code>
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            navigator.clipboard.writeText(link);
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1500);
          }}
        >
          {copied ? <Check /> : <Copy />}
          {copied ? "Copiado" : "Copiar"}
        </Button>
      </div>
    </div>
  );
}

function MemberRowView({
  id,
  email,
  name,
  role,
  self,
}: {
  id: number;
  email: string;
  name: string;
  role: Role;
  self: boolean;
}) {
  const { setRole, remove } = useMemberActions();
  return (
    <li className="flex items-center gap-3 p-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">
          {name}
          {self ? <span className="ml-2 text-xs text-muted-foreground">(tú)</span> : null}
        </p>
        <p className="truncate text-xs text-muted-foreground">{email}</p>
      </div>

      {/* An owner cannot demote or remove themselves: the workspace would be left with
          nobody able to invite, and the API refuses it too. */}
      {self ? (
        <Badge variant="outline">{ROLE_LABELS[role]}</Badge>
      ) : (
        <>
          <Select
            value={role}
            className="h-8 w-36"
            onChange={(event) => setRole.mutate({ id, role: event.target.value as Role })}
          >
            {ROLES.map((option) => (
              <option key={option} value={option}>
                {ROLE_LABELS[option]}
              </option>
            ))}
          </Select>
          <Button
            variant="ghost"
            size="icon-sm"
            title="Quitar del workspace"
            onClick={() => remove.mutate(id)}
          >
            <Trash2 />
          </Button>
        </>
      )}
    </li>
  );
}

function InviteRowView({
  id,
  email,
  role,
  expiresAt,
}: {
  id: number;
  email: string | null;
  role: Role;
  expiresAt: string;
}) {
  const revoke = useRevokeInvite();
  return (
    <li className="flex items-center gap-3 p-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm">{email ?? "Enlace sin destinatario"}</p>
        <p className="text-xs text-muted-foreground">
          Caduca el {new Date(expiresAt).toLocaleDateString("es-ES")}
        </p>
      </div>
      <Badge variant="outline">{ROLE_LABELS[role]}</Badge>
      <Button variant="ghost" size="icon-sm" title="Anular" onClick={() => revoke.mutate(id)}>
        <Trash2 />
      </Button>
    </li>
  );
}
