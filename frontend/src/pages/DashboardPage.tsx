import { useState } from "react";
import { Link } from "react-router-dom";
import Heatmap from "../components/Heatmap";
import { Card, EmptyState, ErrorMessage, Loading, PageTitle } from "../components/ui";
import { useDue, useHeatmap, useSummary } from "../hooks/queries";
import { useAuth } from "../lib/auth-context";
import { formatDays, pluralize, todayIn } from "../lib/format";
import { gridStart, PERIOD_LABELS, PERIOD_WEEKS, type Period } from "../lib/heatmap";

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <Card>
      <p className="text-xs uppercase tracking-wide text-muted">{label}</p>
      <p className="mt-1 font-mono text-3xl font-semibold">{value}</p>
      {hint && <p className="mt-1 text-xs text-muted">{hint}</p>}
    </Card>
  );
}

export default function DashboardPage() {
  const { user } = useAuth();
  const [period, setPeriod] = useState<Period>("year");
  const weeks = PERIOD_WEEKS[period];
  const today = todayIn(user?.timezone ?? "UTC");
  const from = gridStart(today, weeks);

  const summary = useSummary();
  const due = useDue();
  const heatmap = useHeatmap(from, today);

  return (
    <div className="flex flex-col gap-6">
      <PageTitle>Дашборд</PageTitle>

      {due.data && due.data.count > 0 && (
        <Link
          to="/reviews"
          className="flex items-center justify-between rounded-lg border border-accent bg-accent/10 px-4 py-3 hover:bg-accent/20"
        >
          <span>
            Сегодня к повторению: <strong className="font-mono">{due.data.count}</strong>
          </span>
          <span className="text-sm text-accent">Начать →</span>
        </Link>
      )}

      {summary.isPending && <Loading />}
      {summary.isError && (
        <ErrorMessage error={summary.error} onRetry={() => void summary.refetch()} />
      )}
      {summary.data && (
        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <Stat label="Всего решено" value={summary.data.total} />
          <Stat
            label="Серия"
            value={summary.data.current_streak}
            hint={`${pluralize(summary.data.current_streak, ["день", "дня", "дней"])} подряд · рекорд ${formatDays(summary.data.longest_streak)}`}
          />
          <Stat label="За 7 дней" value={summary.data.last_7_days} />
          <Stat label="За 30 дней" value={summary.data.last_30_days} />
        </div>
      )}

      <Card>
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-mono text-base">Активность</h2>
          <div role="group" aria-label="Период теплокарты" className="flex gap-1">
            {(Object.keys(PERIOD_LABELS) as Period[]).map((key) => (
              <button
                key={key}
                type="button"
                aria-pressed={period === key}
                onClick={() => setPeriod(key)}
                className={`rounded-md border px-2.5 py-1 text-xs transition ${
                  period === key
                    ? "border-accent text-accent"
                    : "border-line text-muted hover:text-fg"
                }`}
              >
                {PERIOD_LABELS[key]}
              </button>
            ))}
          </div>
        </div>
        {heatmap.isPending && <Loading />}
        {heatmap.isError && (
          <ErrorMessage error={heatmap.error} onRetry={() => void heatmap.refetch()} />
        )}
        {heatmap.data && <Heatmap days={heatmap.data} end={today} weeks={weeks} />}
      </Card>

      {summary.data?.total === 0 && (
        <EmptyState
          title="Пока нет решённых задач"
          hint="Добавьте первую задачу вручную или импортируйте историю с Codeforces."
          action={
            <div className="flex justify-center gap-3 text-sm">
              <Link className="text-accent underline" to="/solves">
                Добавить задачу
              </Link>
              <Link className="text-accent underline" to="/settings">
                Импорт с Codeforces
              </Link>
            </div>
          }
        />
      )}
    </div>
  );
}
