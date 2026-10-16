import { RefreshCw } from "lucide-react";

import { errorText } from "@/lib/errors";
import { useT } from "@/lib/i18n";
import { Alert } from "./alert";
import { Button } from "./button";

/**
 * A READ THAT FAILED SAYS SO. NO SCREEN MAY RENDER NOTHING INSTEAD.
 *
 * The rule is the evaluation panel's, learned from a route-ordering bug that turned into a card
 * with a heading and no body — "esta función no existe" rather than "esto falló". It was
 * fixed there and nowhere else: with `/api/kg` down, the graph screen still drew its header,
 * its APROBADO badge and "Grafo listo para etiquetar" over an empty page, which is worse
 * than silence — it asserts that the stage is fine while showing none of it. Measured in a
 * browser with the request cut; `/admin` did the same.
 *
 * The retry is part of it: a failed read is very often a blip, and the alternative on offer
 * was reloading the whole application.
 */
export function LoadError({
  title,
  error,
  onRetry,
  className,
}: {
  title: string;
  error: unknown;
  onRetry?: () => void;
  className?: string;
}) {
  const { t } = useT();
  return (
    <Alert
      tone="danger"
      title={title}
      className={className}
      action={
        onRetry ? (
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw />
            {t("common.retry")}
          </Button>
        ) : undefined
      }
    >
      <p>{errorText(error, t)}</p>
    </Alert>
  );
}
