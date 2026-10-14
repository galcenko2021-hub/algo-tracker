import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/endpoints";
import type { DueCard } from "../api/types";
import { Badge, Card, ErrorMessage, Loading, PageTitle } from "../components/ui";
import { useAnswerCard, useDue } from "../hooks/queries";
import { formatDays, pluralize } from "../lib/format";
import { ANSWERS } from "../lib/reviews";

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
      <div className="mx-auto max-w-lg text-center">
        <PageTitle>Повторения</PageTitle>
        <Card className="py-10">
          <p className="font-mono text-2xl text-ok">Готово на сегодня</p>
          <p className="mt-2 text-sm text-muted">
            {reviewed > 0
              ? `Повторено ${reviewed} ${pluralize(reviewed, ["карточка", "карточки", "карточек"])}.`
              : "Сегодня нет карточек к повторению."}
            {tomorrow > 0 &&
              ` Завтра ждут ${tomorrow} ${pluralize(tomorrow, ["карточка", "карточки", "карточек"])}.`}
          </p>
          <Link className="mt-5 inline-block text-accent underline" to="/">
            На дашборд
          </Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageTitle>Повторения</PageTitle>
      <p className="mb-3 font-mono text-sm text-muted" aria-live="polite">
        Карточка {index + 1} из {queue.length}
      </p>
      <Card className="flex flex-col gap-4">
        <div>
          <h2 className="font-mono text-xl">{card.problem.title}</h2>
          <div className="mt-2 flex flex-wrap items-center gap-2">
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
              className="mt-3 inline-block text-sm text-accent underline"
            >
              Открыть задачу ↗
            </a>
          )}
        </div>
        <div className="rounded-md border border-line bg-bg p-3 text-sm">
          <p className="mb-1 text-xs uppercase text-muted">Ваша заметка</p>
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
              className="flex flex-col items-center gap-1 rounded-md border border-line bg-surface-2 px-2 py-3 transition hover:border-accent disabled:opacity-50"
            >
              <span className="text-sm font-medium">{choice.label}</span>
              <span className="font-mono text-xs text-muted">
                {formatDays(card.next_intervals[choice.interval])}
              </span>
              <kbd className="rounded border border-line px-1.5 font-mono text-xs text-muted">
                {choice.key}
              </kbd>
            </button>
          ))}
        </div>
      </Card>
      <p className="mt-3 text-center text-xs text-muted">
        Горячие клавиши: 1 — снова, 2 — трудно, 3 — хорошо, 4 — легко
      </p>
    </div>
  );
}
