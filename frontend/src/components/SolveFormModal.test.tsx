import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";
import {
  emptySolveForm,
  solvedAtFromDate,
  toCreatePayload,
  validateSolveForm,
} from "../lib/validation";
import { mockFetch, renderWithProviders } from "../test-utils";
import SolveFormModal from "./SolveFormModal";

describe("validateSolveForm", () => {
  it("requires a title", () => {
    expect(validateSolveForm(emptySolveForm).title).toBe("Укажите название задачи");
    expect(validateSolveForm({ ...emptySolveForm, title: "   " }).title).toBeDefined();
  });

  it("accepts a minimal valid form", () => {
    expect(validateSolveForm({ ...emptySolveForm, title: "Watermelon" })).toEqual({});
  });

  it("rejects bad url, rating, time and long notes", () => {
    const errors = validateSolveForm({
      ...emptySolveForm,
      title: "x",
      url: "javascript:alert(1)",
      rating: "12abc",
      timeSpent: "-5",
      notes: "n".repeat(2001),
    });
    expect(Object.keys(errors).sort()).toEqual(["notes", "rating", "timeSpent", "url"]);
    expect(
      validateSolveForm({ ...emptySolveForm, title: "x", rating: "5001" }).rating,
    ).toBeDefined();
    expect(
      validateSolveForm({ ...emptySolveForm, title: "x", rating: "5000" }).rating,
    ).toBeUndefined();
  });
});

describe("payload", () => {
  it("turns empty strings into nulls and trims", () => {
    const body = toCreatePayload(
      {
        ...emptySolveForm,
        title: "  Two Sum ",
        rating: "800",
        tags: ["dp"],
        solvedDate: "2026-10-14",
      },
      "2026-10-14",
    );
    expect(body).toMatchObject({
      title: "Two Sum",
      external_id: null,
      url: null,
      rating: 800,
      tags: ["dp"],
      solved_at: null,
      notes: null,
    });
  });

  it("sends a past date as noon UTC and today as 'now'", () => {
    expect(solvedAtFromDate("2026-10-01", "2026-10-14")).toBe("2026-10-01T12:00:00Z");
    expect(solvedAtFromDate("2026-10-14", "2026-10-14")).toBeUndefined();
    expect(solvedAtFromDate("", "2026-10-14")).toBeUndefined();
  });
});

describe("<SolveFormModal>", () => {
  it("shows a validation error and does not call the API for an empty title", async () => {
    const user = userEvent.setup();
    const { calls } = mockFetch({ "GET /api/tags": [] });
    const onClose = vi.fn();
    renderWithProviders(<SolveFormModal onClose={onClose} />);

    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    expect(await screen.findByText("Укажите название задачи")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
    expect(onClose).not.toHaveBeenCalled();
  });

  it("submits a valid form with tag chips and closes", async () => {
    const user = userEvent.setup();
    const { calls } = mockFetch({
      "GET /api/tags": [],
      "POST /api/solves": { id: 1 },
      "GET /api/summary": {},
    });
    const onClose = vi.fn();
    renderWithProviders(<SolveFormModal onClose={onClose} />);

    await user.type(screen.getByLabelText(/Название/), "Watermelon");
    await user.type(screen.getByLabelText("Рейтинг"), "800");
    await user.type(screen.getByLabelText("Теги"), "Math{Enter}Greedy,");
    expect(screen.getByRole("button", { name: "Удалить тег math" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Удалить тег greedy" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Сохранить" }));

    await waitFor(() => expect(onClose).toHaveBeenCalled());
    const post = calls.find((c) => c.method === "POST");
    expect(post?.path).toBe("/api/solves");
    expect(post?.body).toMatchObject({
      platform: "codeforces",
      title: "Watermelon",
      rating: 800,
      tags: ["math", "greedy"],
    });
  });

  it("shows the server error and stays open", async () => {
    const user = userEvent.setup();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_input: RequestInfo | URL, init?: RequestInit) => {
        if (init?.method === "POST") {
          return new Response(JSON.stringify({ detail: "Эта задача уже добавлена" }), {
            status: 409,
          });
        }
        return new Response("[]", { status: 200 });
      }),
    );
    const onClose = vi.fn();
    renderWithProviders(<SolveFormModal onClose={onClose} />);
    await user.type(screen.getByLabelText(/Название/), "Dup");
    await user.click(screen.getByRole("button", { name: "Сохранить" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Эта задача уже добавлена");
    expect(onClose).not.toHaveBeenCalled();
  });

  it("closes on Escape", async () => {
    const user = userEvent.setup();
    mockFetch({ "GET /api/tags": [] });
    const onClose = vi.fn();
    renderWithProviders(<SolveFormModal onClose={onClose} />);
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalled();
  });
});
