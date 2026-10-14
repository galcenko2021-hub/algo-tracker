import { Badge, EmptyState, ErrorMessage, Loading, PageTitle } from "../components/ui";
import { useRecommendations } from "../hooks/queries";

export default function RecommendationsPage() {
  const recs = useRecommendations(6);

  return (
    <div className="flex flex-col gap-6">
      <PageTitle hint="Задачи с Codeforces чуть выше вашего уровня по темам, где вы слабее.">
        Что решать дальше
      </PageTitle>
      {recs.isPending && (
        <Loading label="Подбираем задачи… (первый запрос может занять несколько секунд)" />
      )}
      {recs.isError && <ErrorMessage error={recs.error} onRetry={() => void recs.refetch()} />}

      {recs.data && (
        <>
          <div className="flex flex-wrap items-center gap-x-6 gap-y-2 text-sm">
            <p className="text-muted">
              Ваш уровень <span className="ml-1 font-semibold text-fg">{recs.data.level}</span>
            </p>
            <p className="text-muted">
              Метод{" "}
              <span className="ml-1 font-semibold text-fg">
                {recs.data.method === "ml" ? "ML-модель" : "эвристика"}
              </span>
            </p>
          </div>
          {recs.data.fallback_reason && (
            <p className="rounded-lg border border-line bg-surface-2/60 px-4 py-3 text-sm text-muted">
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
              <li
                key={item.problem.external_id}
                className="flex flex-col gap-3 rounded-xl border border-line bg-surface p-5"
              >
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="font-mono text-xs text-muted">{item.problem.external_id}</p>
                    <h2 className="mt-0.5 text-base font-semibold">{item.problem.title}</h2>
                  </div>
                  {item.problem.rating !== null && (
                    <span className="shrink-0 rounded-md bg-accent-soft px-2 py-0.5 text-sm font-semibold text-accent">
                      {item.problem.rating}
                    </span>
                  )}
                </div>
                <div className="flex flex-wrap items-center gap-1.5">
                  {item.problem.tags.map((tag) => (
                    <Badge key={tag}>{tag}</Badge>
                  ))}
                </div>
                <p className="flex-1 text-sm leading-relaxed text-muted">{item.reason}</p>
                <div className="flex items-center justify-between gap-3 border-t border-line pt-3">
                  {item.predicted_solve_prob !== null ? (
                    <p className="text-[13px] text-muted">
                      Шанс решить{" "}
                      <span className="font-medium text-fg">
                        {Math.round(item.predicted_solve_prob * 100)}%
                      </span>
                    </p>
                  ) : (
                    <span />
                  )}
                  <a
                    href={item.problem.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="rounded-md border border-line px-3 py-1.5 text-sm font-medium transition-colors hover:border-accent/50 hover:bg-accent-soft hover:text-accent"
                  >
                    Открыть на Codeforces ↗
                  </a>
                </div>
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
