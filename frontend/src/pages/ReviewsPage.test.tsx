import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { DueCard } from "../api/types";
import { mockFetch, renderWithProviders } from "../test-utils";
import ReviewsPage from "./ReviewsPage";

function card(id: number, title: string, notes: string | null = null): DueCard {
  return {
    card_id: id,
    problem: {
      id,
      platform: "codeforces",
      external_id: `${id}A`,
      title,
      url: `https://codeforces.com/problemset/problem/${id}/A`,
      rating: 1200,
      tags: ["dp"],
    },
    notes,
    due_date: "2026-10-14",
    interval_days: 6,
    repetitions: 2,
    lapses: 0,
    ease: 2.5,
    next_intervals: { again: 1, hard: 15, good: 15, easy: 16 },
  };
}

const answer = {
  card_id: 1,
  interval_days: 6,
  due_date: "2026-10-20",
  ease: 2.5,
  repetitions: 2,
  lapses: 0,
};

function setup(cards: DueCard[]) {
  return mockFetch({
    "GET /api/reviews/due": { count: cards.length, cards },
    "GET /api/reviews/upcoming": [
      { date: "2026-10-14", count: 0 },
      { date: "2026-10-15", count: 3 },
    ],
    "POST /api/reviews/1/answer": answer,
    "POST /api/reviews/2/answer": answer,
  });
}

describe("<ReviewsPage>", () => {
  it("shows the card, its note, link and the interval on every button", async () => {
    setup([card(1, "Palindromic Numbers", "use a stack"), card(2, "Second")]);
    renderWithProviders(<ReviewsPage />);

    expect(await screen.findByRole("heading", { name: "Palindromic Numbers" })).toBeInTheDocument();
    expect(screen.getByText("use a stack")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Открыть задачу/ })).toHaveAttribute(
      "href",
      "https://codeforces.com/problemset/problem/1/A",
    );
    expect(screen.getByText("Карточка 1 из 2")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Снова/ })).toHaveTextContent("1 день");
    expect(screen.getByRole("button", { name: /Трудно/ })).toHaveTextContent("15 дней");
    expect(screen.getByRole("button", { name: /Легко/ })).toHaveTextContent("16 дней");
  });

  it("answers with hotkeys 1-4 mapped to qualities 1, 3, 4, 5 and advances", async () => {
    const user = userEvent.setup();
    const { calls } = setup([card(1, "First"), card(2, "Second")]);
    renderWithProviders(<ReviewsPage />);
    await screen.findByRole("heading", { name: "First" });

    await user.keyboard("3");
    expect(await screen.findByRole("heading", { name: "Second" })).toBeInTheDocument();
    expect(screen.getByText("Карточка 2 из 2")).toBeInTheDocument();

    await user.keyboard("4");
    expect(await screen.findByText("Готово на сегодня")).toBeInTheDocument();

    const posts = calls.filter((c) => c.method === "POST");
    expect(posts.map((p) => [p.path, p.body])).toEqual([
      ["/api/reviews/1/answer", { quality: 4 }],
      ["/api/reviews/2/answer", { quality: 5 }],
    ]);
  });

  it.each([
    ["1", 1],
    ["2", 3],
    ["3", 4],
    ["4", 5],
  ])("hotkey %s sends quality %i", async (key, quality) => {
    const user = userEvent.setup();
    const { calls } = setup([card(1, "Only")]);
    renderWithProviders(<ReviewsPage />);
    await screen.findByRole("heading", { name: "Only" });
    await user.keyboard(key);
    await waitFor(() => expect(calls.some((c) => c.method === "POST")).toBe(true));
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ quality });
  });

  it("answers by clicking a button too", async () => {
    const user = userEvent.setup();
    const { calls } = setup([card(1, "Only")]);
    renderWithProviders(<ReviewsPage />);
    await screen.findByRole("heading", { name: "Only" });
    await user.click(screen.getByRole("button", { name: /Хорошо/ }));
    expect(await screen.findByText("Готово на сегодня")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")?.body).toEqual({ quality: 4 });
  });

  it("ignores hotkeys and modifier combos that are not answers", async () => {
    const user = userEvent.setup();
    const { calls } = setup([card(1, "Only")]);
    renderWithProviders(<ReviewsPage />);
    await screen.findByRole("heading", { name: "Only" });
    await user.keyboard("5");
    await user.keyboard("{Control>}1{/Control}");
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
  });

  it("shows the finished screen when nothing is due", async () => {
    setup([]);
    renderWithProviders(<ReviewsPage />);
    expect(await screen.findByText("Готово на сегодня")).toBeInTheDocument();
    expect(screen.getByText(/Сегодня нет карточек к повторению/)).toBeInTheDocument();
  });

  it("keeps the card and shows an error when the answer fails", async () => {
    const user = userEvent.setup();
    mockFetch({
      "GET /api/reviews/due": { count: 1, cards: [card(1, "Only")] },
      "GET /api/reviews/upcoming": [],
    });
    renderWithProviders(<ReviewsPage />);
    await screen.findByRole("heading", { name: "Only" });
    await user.keyboard("3");
    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Only" })).toBeInTheDocument();
  });
});
