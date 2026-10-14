import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/endpoints";
import type { DueCard } from "../api/types";
import { Badge, Card, ErrorMessage, Loading, PageTitle } from "../components/ui";
import { useAnswerCard, useDue } from "../hooks/queries";
import { formatDays, pluralize } from "../lib/format";
import { ANSWERS } from "../lib/reviews";
import { linkClass } from "../lib/styles";

/** A thin coloured top edge tells the four grades apart without loud fills. */
const TONES: Record<(typeof ANSWERS)[number]["interval"], string> = {
  again: "var(--danger)",
  hard: "var(--warn)",
  good: "var(--accent)",
  easy: "var(--ok)",
};

function isTypingTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  return ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName) || target.isContentEditable;
}

export default function ReviewsPage() {
  const due = useDue();
  if (due.isPending) return <Loading />;
  if (due.isError) return <ErrorMessage error={due.error} onRetry={() => void due.refetch()} />;
  return <ReviewSession cards={due.data.cards} />;
}

function ReviewSession({ cards }: { cards: DueCard[] }) {
  const queryClient = useQueryClient();
  const answer = useAnswerCard();
  const upcoming = useQuery({ queryKey: ["upcoming"], queryFn: () => api.upcoming(7) });

  // The queue is frozen when the session starts, so refetches never reshuffle cards mid-session.
  const [queue] = useState(cards);
  const [index, setIndex] = useState(0);

  const card = queue[index];
  const finished = index >= queue.length;

  const submit = useCallback(
    (quality: number) => {
      if (!card || answer.isPending) return;
      answer.mutate(
        { cardId: card.card_id, quality },
        {
          onSuccess: () => {
            setIndex((i) => i + 1);
            void queryClient.invalidateQueries({ queryKey: ["due"] });
          },
        },
      );
    },
    [card, answer, queryClient],
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.ctrlKey || event.metaKey || event.altKey || isTypingTarget(event.target)) return;
      const choice = ANSWERS.find((a) => a.key === event.key);
      if (choice) {
        event.preventDefault();
        submit(choice.quality);
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [submit]);

  if (finished || !card) {
    const reviewed = queue.length;
    const tomorrow = upcoming.data?.[1]?.count ?? 0;
    return (
      <div className="mx-auto flex max-w-lg flex-col gap-6">
        <PageTitle>Повторения</PageTitle>
        <Card className="px-8 py-12 text-center">
          <span
            aria-hidden="true"
            className="mx-auto mb-4 flex h-10 w-10 items-center justify-center rounded-full bg-ok/12 text-ok"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
              <path
                d="M4 9.5l3.2 3L14 5.5"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </span>
          <p className="text-xl font-semibold">Готово на сегодня</p>
          <p className="mt-2 text-sm text-muted">
            {reviewed > 0
              ? `Повторено ${reviewed} ${pluralize(reviewed, ["карточка", "карточки", "карточек"])}.`
              : "Сегодня нет карточек к повторению."}
            {tomorrow > 0 &&
              ` Завтра ждут ${tomorrow} ${pluralize(tomorrow, ["карточка", "карточки", "карточек"])}.`}
          </p>
          <Link className={`mt-6 inline-block text-sm ${linkClass}`} to="/">
            На дашборд
          </Link>
        </Card>
      </div>
    );
  }

  const progress = Math.round((index / queue.length) * 100);

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-5">
      <PageTitle>Повторения</PageTitle>
      <div className="flex items-center gap-4">
        <p className="shrink-0 text-sm text-muted" aria-live="polite">
          Карточка {index + 1} из {queue.length}
        </p>
        <div aria-hidden="true" className="h-1 flex-1 overflow-hidden rounded-full bg-surface-2">
          <div
            className="h-full rounded-full bg-accent/70 transition-[width] duration-300"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
      <Card className="flex flex-col gap-6 p-6 sm:p-8">
        <div>
          <h2 className="text-2xl font-semibold">{card.problem.title}</h2>
          <div className="mt-3 flex flex-wrap items-center gap-1.5">
            {card.problem.rating !== null && <Badge tone="accent">{card.problem.rating}</Badge>}
            {card.problem.tags.map((tag) => (
              <Badge key={tag}>{tag}</Badge>
            ))}
          </div>
          {card.problem.url && (
            <a
              href={card.problem.url}
              target="_blank"
              rel="noopener noreferrer"
              className={`mt-4 inline-block text-sm ${linkClass}`}
            >
              Открыть задачу ↗
            </a>
          )}
        </div>
        <div className="border-l-2 border-line-strong py-0.5 pl-4 text-[15px]">
          <p className="mb-1 text-[13px] text-muted">Ваша заметка</p>
          {card.notes ? (
            <p className="whitespace-pre-wrap">{card.notes}</p>
          ) : (
            <p className="text-muted">
              Заметки нет. Вспомните идею решения и оцените, как это далось.
            </p>
          )}
        </div>
        {answer.isError && <ErrorMessage error={answer.error} />}
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {ANSWERS.map((choice) => (
            <button
              key={choice.key}
              type="button"
              disabled={answer.isPending}
              onClick={() => submit(choice.quality)}
              className="group flex flex-col items-center gap-0.5 rounded-lg border border-line bg-surface px-2 pb-3 pt-3.5 transition-colors hover:border-line-strong hover:bg-bg disabled:opacity-50"
              style={{ boxShadow: `inset 0 2px 0 ${TONES[choice.interval]}` }}
            >
              <span className="text-sm font-medium">{choice.label}</span>
              <span className="text-[13px] text-muted">
                {formatDays(card.next_intervals[choice.interval])}
              </span>
              <kbd className="mt-1.5 rounded border border-line bg-surface-2 px-1.5 font-mono text-[11px] leading-4 text-muted">
                {choice.key}
              </kbd>
            </button>
          ))}
        </div>
      </Card>
      <p className="text-center text-xs text-muted">
        Горячие клавиши: 1 — снова, 2 — трудно, 3 — хорошо, 4 — легко
      </p>
    </div>
  );
}
