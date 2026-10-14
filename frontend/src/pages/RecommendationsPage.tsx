import { Badge, Card, EmptyState, ErrorMessage, Loading, PageTitle } from "../components/ui";
import { useRecommendations } from "../hooks/queries";

export default function RecommendationsPage() {
  const recs = useRecommendations(6);

  return (
    <div className="flex flex-col gap-4">
      <PageTitle>Что решать дальше</PageTitle>
      {recs.isPending && (
        <Loading label="Подбираем задачи… (первый запрос может занять несколько секунд)" />
      )}
      {recs.isError && <ErrorMessage error={recs.error} onRetry={() => void recs.refetch()} />}

      {recs.data && (
        <>
          <div className="flex flex-wrap items-center gap-2 text-sm text-muted">
            <span>Ваш уровень:</span>
            <span className="font-mono text-fg">{recs.data.level}</span>
            <Badge tone={recs.data.method === "ml" ? "accent" : "muted"}>
              {recs.data.method === "ml" ? "ML" : "эвристика"}
            </Badge>
          </div>
          {recs.data.fallback_reason && (
            <p className="rounded-md border border-line bg-surface p-3 text-sm text-muted">
              Используется эвристика. {recs.data.fallback_reason}.
            </p>
          )}
          {recs.data.items.length === 0 && (
            <EmptyState
              title="Подходящих задач не нашлось"
              hint="Каталог Codeforces пуст или все задачи вашего уровня уже решены."
            />
          )}
          <ul className="grid grid-cols-1 gap-4 md:grid-cols-2">
            {recs.data.items.map((item) => (
              <li key={item.problem.external_id}>
                <Card className="flex h-full flex-col gap-3">
                  <div className="flex items-start justify-between gap-2">
                    <h2 className="font-mono text-base">{item.problem.title}</h2>
                    <Badge tone={recs.data.method === "ml" ? "accent" : "muted"}>
                      {recs.data.method === "ml" ? "ML" : "эвристика"}
                    </Badge>
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5">
                    {item.problem.rating !== null && (
                      <Badge tone="accent">{item.problem.rating}</Badge>
                    )}
                    {item.problem.tags.map((tag) => (
                      <Badge key={tag}>{tag}</Badge>
                    ))}
                  </div>
                  <p className="flex-1 text-sm text-muted">{item.reason}</p>
                  {item.predicted_solve_prob !== null && (
                    <p className="font-mono text-xs text-muted">
                      Вероятность решить: {Math.round(item.predicted_solve_prob * 100)}%
                    </p>
                  )}
                  <a
                    href={item.problem.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center justify-center rounded-md bg-accent px-3 py-2 text-sm font-medium text-accent-fg hover:opacity-90"
                  >
                    Открыть на Codeforces ↗
                  </a>
                </Card>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
