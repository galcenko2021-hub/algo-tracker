import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Bar,
  BarChart,
  CartesianGrid,
  PolarAngleAxis,
  PolarGrid,
  PolarRadiusAxis,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, EmptyState, ErrorMessage, Loading, PageTitle } from "../components/ui";
import { useTopics } from "../hooks/queries";
import { useAuth } from "../lib/auth-context";
import { formatInstant } from "../lib/format";
import { sortTopics, type SortKey } from "../lib/topics";

const TOOLTIP = {
  contentStyle: {
    background: "var(--surface)",
    border: "1px solid var(--line)",
    borderRadius: 8,
    fontSize: 13,
    boxShadow: "0 8px 24px -12px rgb(20 28 36 / 0.25)",
  },
  labelStyle: { color: "var(--fg)", fontWeight: 500 },
  itemStyle: { color: "var(--muted)" },
};

/** Muted brick for weak topics, ochre for middling, ink for the rest. */
function weaknessColor(weakness: number): string {
  if (weakness >= 0.6) return "var(--danger)";
  if (weakness >= 0.4) return "var(--warn)";
  return "var(--accent)";
}

const COLUMNS: { key: SortKey; label: string; numeric?: boolean }[] = [
  { key: "tag", label: "Тема" },
  { key: "solved", label: "Решено", numeric: true },
  { key: "avg_rating", label: "Ср. рейтинг", numeric: true },
  { key: "last_solved_at", label: "Последнее" },
  { key: "avg_review_quality", label: "Оценка повторений", numeric: true },
  { key: "weakness", label: "Слабость", numeric: true },
];

export default function TopicsPage() {
  const { user } = useAuth();
  const topics = useTopics();
  const [sort, setSort] = useState<{ key: SortKey; direction: "asc" | "desc" }>({
    key: "weakness",
    direction: "desc",
  });

  const sorted = useMemo(
    () => sortTopics(topics.data ?? [], sort.key, sort.direction),
    [topics.data, sort],
  );
  const bySolved = useMemo(
    () =>
      [...(topics.data ?? [])].sort((a, b) => b.solved - a.solved || a.tag.localeCompare(b.tag)),
    [topics.data],
  );
  const barData = bySolved.slice(0, 15).map((t) => ({ tag: t.tag, solved: t.solved }));
  const radarData = bySolved
    .slice(0, 8)
    .map((t) => ({ tag: t.tag, strength: Math.round((1 - t.weakness) * 100) }));

  function toggleSort(key: SortKey) {
    setSort((prev) =>
      prev.key === key
        ? { key, direction: prev.direction === "desc" ? "asc" : "desc" }
        : { key, direction: key === "tag" ? "asc" : "desc" },
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <PageTitle hint="Сколько решено по каждой теме и где стоит подтянуться.">
        Разбор по темам
      </PageTitle>
      {topics.isPending && <Loading />}
      {topics.isError && (
        <ErrorMessage error={topics.error} onRetry={() => void topics.refetch()} />
      )}
      {topics.data && topics.data.length === 0 && (
        <EmptyState
          title="Тем пока нет"
          hint="Добавьте решения с тегами — здесь появятся статистика и слабые места."
        />
      )}
      {topics.data && topics.data.length > 0 && (
        <>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card>
              <h2 className="mb-4 text-base font-semibold">Решено по темам</h2>
              <div
                className="h-72"
                role="img"
                aria-label="Столбчатая диаграмма решённых задач по темам"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData} margin={{ bottom: 40 }}>
                    <CartesianGrid stroke="var(--line)" vertical={false} />
                    <XAxis
                      dataKey="tag"
                      interval={0}
                      angle={-40}
                      textAnchor="end"
                      tick={{ fill: "var(--muted)", fontSize: 11 }}
                      tickLine={false}
                      axisLine={{ stroke: "var(--line-strong)" }}
                    />
                    <YAxis
                      allowDecimals={false}
                      tick={{ fill: "var(--muted)", fontSize: 11 }}
                      tickLine={false}
                      axisLine={false}
                      width={32}
                    />
                    <Tooltip cursor={{ fill: "var(--surface-2)" }} {...TOOLTIP} />
                    <Bar
                      isAnimationActive={false}
                      dataKey="solved"
                      name="Решено"
                      fill="var(--heat-3)"
                      radius={[4, 4, 0, 0]}
                      maxBarSize={28}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card>
              <h2 className="text-base font-semibold">Уверенность</h2>
              <p className="mb-2 text-[13px] text-muted">100 − слабость, восемь самых частых тем</p>
              <div className="h-72" role="img" aria-label="Радар уверенности по основным темам">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="var(--line)" />
                    <PolarAngleAxis dataKey="tag" tick={{ fill: "var(--muted)", fontSize: 11 }} />
                    <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                    <Radar
                      isAnimationActive={false}
                      dataKey="strength"
                      name="Уверенность"
                      stroke="var(--accent)"
                      fill="var(--accent)"
                      fillOpacity={0.18}
                      strokeWidth={1.5}
                    />
                    <Tooltip {...TOOLTIP} />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <div className="overflow-x-auto rounded-xl border border-line bg-surface">
            <table className="w-full min-w-[44rem] text-left text-sm">
              <thead className="border-b border-line text-[13px] text-muted">
                <tr>
                  {COLUMNS.map((col) => (
                    <th
                      key={col.key}
                      scope="col"
                      aria-sort={
                        sort.key === col.key
                          ? sort.direction === "asc"
                            ? "ascending"
                            : "descending"
                          : "none"
                      }
                      className={`px-4 py-3 font-medium ${col.numeric ? "text-right" : ""}`}
                    >
                      <button
                        type="button"
                        className={`transition-colors hover:text-fg ${sort.key === col.key ? "text-fg" : ""}`}
                        onClick={() => toggleSort(col.key)}
                      >
                        {col.label}
                        {sort.key === col.key && (sort.direction === "asc" ? " ↑" : " ↓")}
                      </button>
                    </th>
                  ))}
                  <th className="px-4 py-3">
                    <span className="sr-only">Ссылки</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {sorted.map((topic) => (
                  <tr
                    key={topic.tag}
                    className="border-t border-line transition-colors first:border-t-0 hover:bg-bg/60"
                  >
                    <td className="px-4 py-3 font-medium">{topic.tag}</td>
                    <td className="px-4 py-3 text-right">{topic.solved}</td>
                    <td className="px-4 py-3 text-right">
                      {topic.avg_rating === null ? "—" : Math.round(topic.avg_rating)}
                    </td>
                    <td className="px-4 py-3 text-muted">
                      {topic.last_solved_at
                        ? formatInstant(topic.last_solved_at, user?.timezone ?? "UTC")
                        : "—"}
                    </td>
                    <td className="px-4 py-3 text-right">
                      {topic.avg_review_quality === null
                        ? "—"
                        : topic.avg_review_quality.toFixed(1)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className="inline-flex items-center justify-end gap-2.5">
                        <span
                          aria-hidden="true"
                          className="inline-block h-1.5 w-16 overflow-hidden rounded-full bg-surface-2"
                        >
                          <span
                            className="block h-full rounded-full opacity-75"
                            style={{
                              width: `${Math.round(topic.weakness * 100)}%`,
                              background: weaknessColor(topic.weakness),
                            }}
                          />
                        </span>
                        <span className="w-8">{topic.weakness.toFixed(2)}</span>
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right text-[13px]">
                      <Link
                        className="text-muted transition-colors hover:text-accent"
                        to={`/solves?tag=${encodeURIComponent(topic.tag)}`}
                      >
                        Решения
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
