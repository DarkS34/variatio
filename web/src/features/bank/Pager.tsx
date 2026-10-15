import { ChevronLeft, ChevronRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useT } from "@/lib/i18n";

/** Which page of the bank, and the two steps either side of it. */
export function Pager({
  page,
  pages,
  total,
  onPage,
}: {
  page: number;
  pages: number;
  total: number;
  onPage: (next: number) => void;
}) {
  const { t, plural } = useT();
  return (
    <>
      <span className="text-small nums text-muted-foreground">
        {plural("bank.pageOf", total, { page, pages })}
      </span>
      {pages > 1 ? (
        <div className="flex gap-1">
          <Button
            variant="outline"
            size="icon-sm"
            aria-label={t("common.previous")}
            title={t("common.previous")}
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
          >
            <ChevronLeft />
          </Button>
          <Button
            variant="outline"
            size="icon-sm"
            aria-label={t("common.next")}
            title={t("common.next")}
            disabled={page >= pages}
            onClick={() => onPage(page + 1)}
          >
            <ChevronRight />
          </Button>
        </div>
      ) : null}
    </>
  );
}
