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
      <PageTitle>Разбор по темам</PageTitle>
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
              <h2 className="mb-2 font-mono text-base">Решено по темам</h2>
              <div
                className="h-72"
                role="img"
                aria-label="Столбчатая диаграмма решённых задач по темам"
              >
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={barData} margin={{ bottom: 40 }}>
                    <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" />
                    <XAxis
                      dataKey="tag"
                      interval={0}
                      angle={-40}
                      textAnchor="end"
                      tick={{ fill: "var(--muted)", fontSize: 11 }}
                    />
                    <YAxis allowDecimals={false} tick={{ fill: "var(--muted)", fontSize: 11 }} />
                    <Tooltip
                      contentStyle={{
                        background: "var(--surface-2)",
                        border: "1px solid var(--line)",
                      }}
                    />
                    <Bar
                      dataKey="solved"
                      name="Решено"
                      fill="var(--accent)"
                      radius={[3, 3, 0, 0]}
                    />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </Card>
            <Card>
              <h2 className="mb-2 font-mono text-base">Уверенность (100 − слабость)</h2>
              <div className="h-72" role="img" aria-label="Радар уверенности по основным темам">
                <ResponsiveContainer width="100%" height="100%">
                  <RadarChart data={radarData}>
                    <PolarGrid stroke="var(--line)" />
                    <PolarAngleAxis dataKey="tag" tick={{ fill: "var(--muted)", fontSize: 11 }} />
                    <PolarRadiusAxis domain={[0, 100]} tick={false} axisLine={false} />
                    <Radar
                      dataKey="strength"
                      name="Уверенность"
                      stroke="var(--accent)"
                      fill="var(--accent)"
                      fillOpacity={0.35}
                    />
                    <Tooltip
                      contentStyle={{
                        background: "var(--surface-2)",
                        border: "1px solid var(--line)",
                      }}
                    />
                  </RadarChart>
                </ResponsiveContainer>
              </div>
            </Card>
          </div>

          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="w-full min-w-[44rem] text-left text-sm">
              <thead className="bg-surface-2 text-xs uppercase text-muted">
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
                      className={`px-3 py-2 ${col.numeric ? "text-right" : ""}`}
                    >
                      <button
                        type="button"
                        className="uppercase hover:text-fg"
                        onClick={() => toggleSort(col.key)}
                      >
                        {col.label}
                        {sort.key === col.key && (sort.direction === "asc" ? " ↑" : " ↓")}
                      </button>
                    </th>
                  ))}
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {sorted.map((topic) => (
                  <tr key={topic.tag} className="border-t border-line">
                    <td className="px-3 py-2 font-mono">{topic.tag}</td>
                    <td className="px-3 py-2 text-right font-mono">{topic.solved}</td>
                    <td className="px-3 py-2 text-right font-mono">
                      {topic.avg_rating === null ? "—" : Math.round(topic.avg_rating)}
                    </td>
                    <td className="px-3 py-2 font-mono">
                      {topic.last_solved_at
                        ? formatInstant(topic.last_solved_at, user?.timezone ?? "UTC")
                        : "—"}
                    </td>
                    <td className="px-3 py-2 text-right font-mono">
                      {topic.avg_review_quality === null
                        ? "—"
                        : topic.avg_review_quality.toFixed(1)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <span className="inline-flex items-center justify-end gap-2">
                        <span
                          aria-hidden="true"
                          className="inline-block h-1.5 w-16 overflow-hidden rounded bg-surface-2"
                        >
                          <span
                            className="block h-full bg-accent"
                            style={{ width: `${Math.round(topic.weakness * 100)}%` }}
                          />
                        </span>
                        <span className="font-mono">{topic.weakness.toFixed(2)}</span>
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Link
                        className="text-accent hover:underline"
                        to={`/solves?tag=${encodeURIComponent(topic.tag)}`}
                      >
                        Решения →
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
