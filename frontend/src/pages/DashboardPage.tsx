import { useState } from "react";
import { Link } from "react-router-dom";
import Heatmap from "../components/Heatmap";
import { Card, EmptyState, ErrorMessage, Loading, PageTitle, SectionTitle } from "../components/ui";
import { useDue, useHeatmap, useSummary } from "../hooks/queries";
import { useAuth } from "../lib/auth-context";
import { formatDays, formatProblemCount, pluralize, todayIn } from "../lib/format";
import { gridStart, PERIOD_LABELS, PERIOD_WEEKS, type Period } from "../lib/heatmap";
import { linkClass } from "../lib/styles";

function Stat({ label, value, hint }: { label: string; value: string | number; hint?: string }) {
  return (
    <div className="bg-surface px-5 py-4">
      <dt className="text-[13px] text-muted">{label}</dt>
      <dd className="mt-1 text-[28px] font-medium leading-tight tracking-tight">{value}</dd>
      {hint && <dd className="mt-0.5 text-xs text-muted">{hint}</dd>}
    </div>
  );
}

function longToday(timeZone: string): string {
  const text = new Intl.DateTimeFormat("ru-RU", {
    weekday: "long",
    day: "numeric",
    month: "long",
    timeZone,
  }).format(new Date());
  return text.charAt(0).toUpperCase() + text.slice(1);
}

export default function DashboardPage() {
  const { user } = useAuth();
  const timezone = user?.timezone ?? "UTC";
  const [period, setPeriod] = useState<Period>("year");
  const weeks = PERIOD_WEEKS[period];
  const today = todayIn(timezone);
  const from = gridStart(today, weeks);

  const summary = useSummary();
  const due = useDue();
  const heatmap = useHeatmap(from, today);
  const periodTotal = heatmap.data?.reduce((sum, day) => sum + day.count, 0) ?? 0;

  return (
    <div className="flex flex-col gap-6">
      <PageTitle hint={longToday(timezone)}>Дашборд</PageTitle>

      {due.data && due.data.count > 0 && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-accent/20 bg-accent-soft px-5 py-3.5">
          <p className="text-sm">
            Сегодня к повторению{" "}
            <strong className="font-semibold">
              {due.data.count} {pluralize(due.data.count, ["карточка", "карточки", "карточек"])}
            </strong>
          </p>
          <Link
            to="/reviews"
            className="rounded-md bg-accent px-3.5 py-1.5 text-sm font-medium text-accent-fg transition-colors hover:bg-accent/90"
          >
            Начать повторение
          </Link>
        </div>
      )}

      {summary.isPending && <Loading />}
      {summary.isError && (
        <ErrorMessage error={summary.error} onRetry={() => void summary.refetch()} />
      )}
      {summary.data && (
        <dl className="grid grid-cols-2 gap-px overflow-hidden rounded-xl border border-line bg-line md:grid-cols-4">
          <Stat label="Всего решено" value={summary.data.total} />
          <Stat
            label="Серия"
            value={formatDays(summary.data.current_streak)}
            hint={`подряд, рекорд ${formatDays(summary.data.longest_streak)}`}
          />
          <Stat label="За 7 дней" value={summary.data.last_7_days} />
          <Stat label="За 30 дней" value={summary.data.last_30_days} />
        </dl>
      )}

      <Card className="p-5 sm:p-6">
        <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
          <div>
            <SectionTitle>Активность</SectionTitle>
            {heatmap.data && (
              <p className="mt-0.5 text-[13px] text-muted">
                {formatProblemCount(periodTotal)} за {PERIOD_LABELS[period].toLowerCase()}
              </p>
            )}
          </div>
          <div
            role="group"
            aria-label="Период теплокарты"
            className="flex rounded-lg bg-surface-2 p-0.5"
          >
            {(Object.keys(PERIOD_LABELS) as Period[]).map((key) => (
              <button
                key={key}
                type="button"
                aria-pressed={period === key}
                onClick={() => setPeriod(key)}
                className={`rounded-md px-3 py-1 text-[13px] transition-colors ${
                  period === key
                    ? "bg-surface font-medium text-fg shadow-[0_0_0_1px_var(--line)]"
                    : "text-muted hover:text-fg"
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
            <div className="flex justify-center gap-5 text-sm">
              <Link className={linkClass} to="/solves">
                Добавить задачу
              </Link>
              <Link className={linkClass} to="/settings">
                Импорт с Codeforces
              </Link>
            </div>
          }
        />
      )}
    </div>
  );
}
