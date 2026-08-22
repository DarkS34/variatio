import { useQuery } from "@tanstack/react-query";
import { Tags } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { api } from "@/lib/api";
import { truncate } from "@/lib/format";
import type { BankItem, BankItemType } from "@/lib/types";

const VISIBLE = 8;

/**
 * Lo que el constructor lleva escrito, mientras lo escribe.
 *
 * La pantalla de una etapa se vacía durante una reconstrucción, y con razón: lo que hay
 * en ella está a punto de dejar de ser lo que se está mirando. Esto no es eso — no es el
 * banco anterior, es el que está saliendo — y por eso vive bajo la barra de progreso y es
 * de solo lectura: no hay nada que editar en un fichero que se sigue escribiendo.
 *
 * Se pregunta por REST y no por el flujo de eventos a propósito: una construcción larga
 * desborda el buffer de eventos, así que un navegador recargado a mitad se quedaría sin
 * nada; el fichero, en cambio, está siempre ahí. Y sale ordenado por id descendente, que
 * es el orden de extracción al revés: lo último escrito, arriba.
 */
export function BankLive() {
  const query = useQuery({
    queryKey: ["bank", "live"],
    queryFn: () => api.bank({ order: "recent", page: 1, page_size: VISIBLE }),
    refetchInterval: 3_000,
    retry: false,
  });

  const listing = query.data;
  const items = listing?.items ?? [];

  const primaryFieldOf = (item: BankItem): string => {
    const types: BankItemType[] = listing?.item_types ?? [];
    if (types.length === 0) return "statement";
    const declared = item.item_type ? types.find((t) => t.key === item.item_type) : undefined;
    return (declared ?? types[0]).primary_field;
  };

  return (
    <Card>
      <CardContent className="space-y-3 py-4">
        <div className="flex items-baseline justify-between gap-3">
          <h4 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Ítems que van saliendo
          </h4>
          {listing ? (
            <span className="text-xs tabular-nums text-muted-foreground">
              {listing.totals.tagged}/{listing.totals.items} etiquetados
            </span>
          ) : null}
        </div>

        {items.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            Todavía no ha salido ningún ítem. Aparecerán aquí en cuanto el primer documento
            termine de extraerse.
          </p>
        ) : (
          <ul className="space-y-2">
            {items.map((item) => {
              const text = String(item[primaryFieldOf(item)] ?? "");
              const concepts = item.concepts ?? [];
              return (
                <li key={item.id} className="rounded-lg border border-border p-2.5">
                  <div className="flex items-baseline gap-2">
                    <code className="shrink-0 font-mono text-xs text-muted-foreground">
                      {item.id}
                    </code>
                    <p className="min-w-0 flex-1 text-sm">{truncate(text, 180)}</p>
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-1">
                    {concepts.length === 0 ? (
                      <span className="flex items-center gap-1 text-xs text-muted-foreground">
                        <Tags className="size-3" />
                        etiquetando…
                      </span>
                    ) : (
                      concepts.map((concept) => (
                        <Badge
                          key={concept}
                          variant={concept === item.primary_concept ? "default" : "secondary"}
                        >
                          {concept}
                        </Badge>
                      ))
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
