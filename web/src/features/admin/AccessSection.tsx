import { useQuery, useQueryClient, useMutation } from "@tanstack/react-query";
import { Plus, X } from "lucide-react";
import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input, Label } from "@/components/ui/input";
import { LoadError, Skeleton, Spinner } from "@/components/ui/misc";
import { RowAction, RowGestures } from "@/components/ui/table";
import { useToast } from "@/components/ui/toast";
import { FormError } from "@/features/auth/AuthLayout";
import { api } from "@/lib/api";
import { useT, type Key } from "@/lib/i18n";
import { readNetwork } from "@/lib/networks";
import type { ConfigPayload } from "@/lib/types";

import { SectionHeader } from "./Sections";

/** The setting this section edits, and the query its value is read from. */
export const TRUSTED_NETWORKS_KEY = "access.trusted_networks";
const CONFIG_KEY = ["admin", "config"] as const;

/** The school networks the installation lists, as the panel's settings answer them. */
export function trustedNetworksOf(payload: ConfigPayload | undefined): string[] | null {
  const setting = payload?.settings.find((row) => row.key === TRUSTED_NETWORKS_KEY);
  if (!setting) return null;
  const value = setting.value ?? setting.default;
  return Array.isArray(value) ? value.map(String) : [];
}

/** Read the installation's settings, shared with every tab that reads them. */
export function useAdminConfig() {
  return useQuery({ queryKey: CONFIG_KEY, queryFn: api.adminConfig });
}

const ERRORS: Record<"invalid" | "tooWide" | "duplicate", Key> = {
  invalid: "acc.access.invalid",
  tooWide: "acc.access.tooWide",
  duplicate: "acc.access.duplicate",
};

/**
 * «Acceso»: the networks a whole class reaches the installation from, behind one address.
 *
 * Behind a school's NAT a hundred students are one address, and the per-address limit on
 * logging in refused the ninth; from a network listed here only each account's own limit is
 * counted. The list is a draft until «Guardar los cambios», like every setting in the panel,
 * and the server has the last word on each network: what it stores is what the list shows
 * after saving. Set in the environment (`VARIATIO_TRUSTED_NETWORKS`), it is read-only here.
 */
export function AccessSection() {
  const { t } = useT();
  const toast = useToast();
  const client = useQueryClient();
  const config = useAdminConfig();
  const [draft, setDraft] = useState<string[] | null>(null);
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<Key | null>(null);

  const setting = config.data?.settings.find((row) => row.key === TRUSTED_NETWORKS_KEY);
  const saved = trustedNetworksOf(config.data) ?? [];
  const list = draft ?? saved;
  const fixed = setting?.source === "env" || setting?.editable === false;
  const dirty = draft !== null && (draft.length !== saved.length || draft.some((item, at) => item !== saved[at]));

  const save = useMutation({
    mutationFn: (networks: string[]) => api.updateAdminConfig({ [TRUSTED_NETWORKS_KEY]: networks }),
    onSuccess: (payload) => {
      client.setQueryData(CONFIG_KEY, payload);
      setDraft(null);
      toast({ title: t("acc.access.saved") });
    },
  });

  const add = (event: FormEvent) => {
    event.preventDefault();
    const reading = readNetwork(typed);
    if ("error" in reading) return setError(ERRORS[reading.error]);
    if (list.includes(reading.network)) return setError(ERRORS.duplicate);
    setDraft([...list, reading.network]);
    setTyped("");
    setError(null);
  };

  const header = (
    <SectionHeader title={t("acc.access")} description={t("acc.access.lead")} />
  );

  if (config.isLoading) {
    return (
      <>
        {header}
        <Skeleton className="h-40" />
      </>
    );
  }
  if (!setting) {
    return (
      <>
        {header}
        <LoadError title={t("acc.access.unreadable")} error={config.error} onRetry={() => config.refetch()} />
      </>
    );
  }

  return (
    <>
      {header}
      <section className="surface space-y-4 p-5" aria-labelledby="access-networks">
        <div className="space-y-1">
          <h3 id="access-networks" className="text-heading">
            {t("acc.access.networks")}
          </h3>
          <p className="text-small text-muted-foreground">{t("acc.access.help")}</p>
        </div>

        {list.length === 0 ? (
          <p className="text-small text-muted-foreground">{t("acc.access.empty")}</p>
        ) : (
          <ul className="rows max-w-xl rows-tight">
            {list.map((network) => (
              <li key={network} className="group flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate font-mono">{network}</span>
                {fixed ? null : (
                  <RowGestures>
                    <RowAction
                      label={t("acc.access.remove", { network })}
                      title={t("acc.access.removeShort")}
                      icon={<X />}
                      disabled={save.isPending}
                      onClick={() => setDraft(list.filter((item) => item !== network))}
                      danger
                    />
                  </RowGestures>
                )}
              </li>
            ))}
          </ul>
        )}

        {fixed ? (
          <p className="text-small text-muted-foreground">
            {t("acc.access.fixed", { env: setting.env ?? "VARIATIO_TRUSTED_NETWORKS" })}
          </p>
        ) : (
          <>
            <form onSubmit={add} className="max-w-xl space-y-1" noValidate>
              <Label htmlFor="access-network">{t("acc.access.label")}</Label>
              <div className="flex gap-2">
                <Input
                  id="access-network"
                  value={typed}
                  autoComplete="off"
                  spellCheck={false}
                  placeholder="192.168.1.0/24"
                  className="font-mono"
                  aria-invalid={error !== null}
                  aria-describedby="access-network-rule"
                  onChange={(event) => {
                    setTyped(event.target.value);
                    setError(null);
                  }}
                />
                <Button type="submit" variant="outline" disabled={!typed.trim() || save.isPending}>
                  <Plus />
                  {t("acc.access.add")}
                </Button>
              </div>
              {error ? (
                <p role="alert" className="text-small text-destructive">
                  {t(error)}
                </p>
              ) : (
                <p id="access-network-rule" className="text-small text-muted-foreground">
                  {t("acc.access.rule")}
                </p>
              )}
            </form>
            <FormError error={save.error} />
            <div className="flex flex-wrap items-center gap-2">
              <Button disabled={!dirty || save.isPending} onClick={() => draft && save.mutate(draft)}>
                {save.isPending ? <Spinner /> : null}
                {t("acc.access.save")}
              </Button>
              {dirty ? (
                <Button variant="ghost" disabled={save.isPending} onClick={() => setDraft(null)}>
                  {t("acc.access.discard")}
                </Button>
              ) : null}
            </div>
          </>
        )}
      </section>
    </>
  );
}
