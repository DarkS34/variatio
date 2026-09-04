import { Skeleton } from "@/components/ui/misc";
import { useT, type Key } from "@/lib/i18n";
import { useContentContext } from "@/state/queries";

const FACT_LABEL: Record<string, Key> = {
  subject: "context.fact.subject",
  educational_level: "context.fact.level",
  language_of_instruction: "context.fact.language",
};


export function WorkspaceContext({ slug }: { slug: string }) {
  const { t } = useT();
  const query = useContentContext(slug);
  const data = query.data;

  if (query.isLoading) return <Skeleton className="h-10" />;

  if (!data)
    return <p className="text-small text-muted-foreground">{t("context.unreadable")}</p>;
  if (!data.exists && !data.narrative && !data.block)
    return <p className="text-small text-muted-foreground">{t("context.none")}</p>;

  const facts = Object.entries(data.facts).filter(([, value]) => value);

  return (
    <div className="space-y-1.5 border-l-2 border-border pl-3">
      <p className="flex items-center gap-2 text-small text-muted-foreground">
        {t("context.title")}
      </p>

      {data.narrative ? (
        <p className="text-small text-muted-foreground">{data.narrative}</p>
      ) : (
        <pre className="whitespace-pre-wrap font-mono text-small text-muted-foreground">
          {data.block}
        </pre>
      )}

      {facts.length > 0 ? (
        <dl className="flex flex-wrap gap-x-4 gap-y-1">
          {facts.map(([key, value]) => (
            <div key={key} className="flex items-baseline gap-1.5">
              <dt className="text-small text-muted-foreground">
                {FACT_LABEL[key] ? t(FACT_LABEL[key]) : key}
              </dt>
              <dd className="text-small">{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </div>
  );
}
