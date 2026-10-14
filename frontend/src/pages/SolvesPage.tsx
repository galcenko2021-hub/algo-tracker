import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import type { Platform, Solve } from "../api/types";
import SolveFormModal from "../components/SolveFormModal";
import TagInput from "../components/TagInput";
import {
  Badge,
  Button,
  Card,
  EmptyState,
  ErrorMessage,
  Loading,
  PageTitle,
} from "../components/ui";
import { useDeleteSolve, useSolves } from "../hooks/queries";
import { useAuth } from "../lib/auth-context";
import { formatInstant } from "../lib/format";
import { inputClass, labelClass, linkClass } from "../lib/styles";
import { PLATFORM_LABELS } from "../lib/validation";

const PAGE_SIZE = 20;

export default function SolvesPage() {
  const { user } = useAuth();
  const timezone = user?.timezone ?? "UTC";
  const [params, setParams] = useSearchParams();
  const [editing, setEditing] = useState<Solve | "new" | null>(null);

  const tags = params.getAll("tag");
  const platform = (params.get("platform") ?? "") as Platform | "";
  const from = params.get("from") ?? "";
  const to = params.get("to") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? 1) || 1);
  const q = params.get("q") ?? "";

  const [search, setSearch] = useState(q);
  const solves = useSolves({
    tag: tags,
    platform,
    from,
    to,
    q,
    page,
    page_size: PAGE_SIZE,
  });
  const remove = useDeleteSolve();

  function update(changes: Record<string, string | string[]>) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        for (const [key, value] of Object.entries(changes)) {
          next.delete(key);
          (Array.isArray(value) ? value : [value])
            .filter(Boolean)
            .forEach((v) => next.append(key, v));
        }
        if (!("page" in changes)) next.delete("page");
        return next;
      },
      { replace: true },
    );
  }

  // Debounce the free-text search so every keystroke does not hit the API.
  useEffect(() => {
    if (search === q) return;
    const timer = setTimeout(() => update({ q: search }), 300);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);

  const data = solves.data;
  const pages = data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1;
  const hasFilters = tags.length > 0 || platform || from || to || q;

  function confirmDelete(solve: Solve) {
    if (
      window.confirm(`Удалить решение «${solve.problem.title}»? Карточка повторения тоже удалится.`)
    ) {
      remove.mutate(solve.id);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <PageTitle hint="Все задачи, которые вы решили, с тегами и заметками.">Решения</PageTitle>
        <Button onClick={() => setEditing("new")}>Добавить решение</Button>
      </div>

      <Card>
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <div className="flex flex-col gap-1">
            <label htmlFor="filter-q" className={labelClass}>
              Поиск
            </label>
            <input
              id="filter-q"
              className={inputClass}
              placeholder="Название или ID"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="filter-platform" className={labelClass}>
              Платформа
            </label>
            <select
              id="filter-platform"
              className={inputClass}
              value={platform}
              onChange={(e) => update({ platform: e.target.value })}
            >
              <option value="">Все</option>
              {(Object.keys(PLATFORM_LABELS) as Platform[]).map((p) => (
                <option key={p} value={p}>
                  {PLATFORM_LABELS[p]}
                </option>
              ))}
            </select>
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="filter-from" className={labelClass}>
              С даты
            </label>
            <input
              id="filter-from"
              type="date"
              className={inputClass}
              value={from}
              onChange={(e) => update({ from: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1">
            <label htmlFor="filter-to" className={labelClass}>
              По дату
            </label>
            <input
              id="filter-to"
              type="date"
              className={inputClass}
              value={to}
              onChange={(e) => update({ to: e.target.value })}
            />
          </div>
          <div className="flex flex-col gap-1 sm:col-span-2 lg:col-span-4">
            <label htmlFor="filter-tags" className={labelClass}>
              Теги (должны быть все)
            </label>
            <TagInput id="filter-tags" value={tags} onChange={(next) => update({ tag: next })} />
          </div>
        </div>
        {hasFilters && (
          <button
            type="button"
            className={`mt-4 text-sm ${linkClass}`}
            onClick={() => {
              setSearch("");
              setParams({}, { replace: true });
            }}
          >
            Сбросить фильтры
          </button>
        )}
      </Card>

      {solves.isPending && <Loading />}
      {solves.isError && (
        <ErrorMessage error={solves.error} onRetry={() => void solves.refetch()} />
      )}
      {remove.isError && <ErrorMessage error={remove.error} />}

      {data && data.items.length === 0 && (
        <EmptyState
          title={hasFilters ? "Ничего не найдено" : "Пока нет решений"}
          hint={
            hasFilters
              ? "Попробуйте изменить или сбросить фильтры."
              : "Добавьте первую задачу или импортируйте историю с Codeforces в настройках."
          }
        />
      )}

      {data && data.items.length > 0 && (
        <>
          <div className="overflow-x-auto rounded-xl border border-line bg-surface">
            <table className="w-full min-w-[40rem] text-left text-sm">
              <thead className="border-b border-line text-[13px] text-muted">
                <tr>
                  <th className="px-4 py-3 font-medium">Дата</th>
                  <th className="px-4 py-3 font-medium">Задача</th>
                  <th className="px-4 py-3 font-medium">Платформа</th>
                  <th className="px-4 py-3 text-right font-medium">Рейтинг</th>
                  <th className="px-4 py-3 font-medium">Теги</th>
                  <th className="px-4 py-3 text-right font-medium">
                    <span className="sr-only">Действия</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((solve) => (
                  <tr
                    key={solve.id}
                    className="group border-t border-line align-top transition-colors first:border-t-0 hover:bg-bg/60"
                  >
                    <td className="whitespace-nowrap px-4 py-3 text-muted">
                      {formatInstant(solve.solved_at, timezone)}
                    </td>
                    <td className="px-4 py-3">
                      {solve.problem.url ? (
                        <a
                          href={solve.problem.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-fg underline decoration-line-strong underline-offset-[3px] hover:decoration-accent"
                        >
                          {solve.problem.title}
                        </a>
                      ) : (
                        <span className="font-medium">{solve.problem.title}</span>
                      )}
                      {solve.notes && (
                        <p className="mt-0.5 max-w-xs text-[13px] text-muted">{solve.notes}</p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-muted">
                      {PLATFORM_LABELS[solve.problem.platform]}
                    </td>
                    <td className="px-4 py-3 text-right">{solve.problem.rating ?? "—"}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {solve.problem.tags.map((tag) => (
                          <Badge key={tag}>{tag}</Badge>
                        ))}
                      </div>
                    </td>
                    <td className="whitespace-nowrap px-4 py-3 text-right text-[13px]">
                      <button
                        type="button"
                        className="mr-3 text-muted transition-colors hover:text-accent"
                        onClick={() => setEditing(solve)}
                      >
                        Изменить
                      </button>
                      <button
                        type="button"
                        className="text-muted transition-colors hover:text-danger"
                        onClick={() => confirmDelete(solve)}
                      >
                        Удалить
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <nav aria-label="Страницы" className="flex items-center justify-between text-sm">
            <span className="text-muted">
              Всего: <span className="font-medium text-fg">{data.total}</span>
            </span>
            <div className="flex items-center gap-2">
              <Button
                variant="secondary"
                disabled={page <= 1}
                onClick={() => update({ page: String(page - 1) })}
              >
                ← Назад
              </Button>
              <span className="min-w-14 text-center text-muted">
                {page} из {pages}
              </span>
              <Button
                variant="secondary"
                disabled={page >= pages}
                onClick={() => update({ page: String(page + 1) })}
              >
                Вперёд →
              </Button>
            </div>
          </nav>
        </>
      )}

      {editing !== null && (
        <SolveFormModal
          solve={editing === "new" ? undefined : editing}
          onClose={() => setEditing(null)}
        />
      )}
    </div>
  );
}
