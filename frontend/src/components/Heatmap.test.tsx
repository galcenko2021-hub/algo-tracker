import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { HeatmapDay } from "../api/types";
import { formatProblemCount, pluralize } from "../lib/format";
import {
  addDays,
  buildGrid,
  cellLabel,
  gridStart,
  intensityLevel,
  weekdayIndex,
} from "../lib/heatmap";
import Heatmap from "./Heatmap";

const END = "2026-10-14"; // a Wednesday

function sample(): HeatmapDay[] {
  return [
    { date: "2026-10-14", count: 3 },
    { date: "2026-10-13", count: 1 },
    { date: "2026-10-12", count: 6 },
    { date: "2026-10-11", count: 5 },
    { date: "2026-10-10", count: 2 },
  ];
}

describe("heatmap helpers", () => {
  it("maps counts to five intensity levels", () => {
    expect([0, 1, 2, 3, 4, 5, 6, 40].map(intensityLevel)).toEqual([0, 1, 2, 2, 3, 3, 4, 4]);
  });

  it("starts weeks on Monday", () => {
    expect(weekdayIndex("2026-10-12")).toBe(0); // Monday
    expect(weekdayIndex("2026-10-18")).toBe(6); // Sunday
    expect(gridStart(END, 53)).toBe(addDays("2026-10-12", -52 * 7));
    expect(weekdayIndex(gridStart(END, 53))).toBe(0);
  });

  it("builds 53 week columns and stops at the end date", () => {
    const cells = buildGrid([], END, 53);
    expect(new Set(cells.map((c) => c.week)).size).toBe(53);
    expect(cells[cells.length - 1].date).toBe(END);
    expect(cells.every((c) => c.date <= END)).toBe(true);
    expect(cells).toHaveLength(52 * 7 + 3); // Mon, Tue, Wed in the last column
  });

  it("formats labels in Russian with correct plurals", () => {
    expect(cellLabel({ date: "2026-10-12", count: 3 })).toBe("12 окт 2026: 3 задачи");
    expect(formatProblemCount(1)).toBe("1 задача");
    expect(formatProblemCount(5)).toBe("5 задач");
    expect(formatProblemCount(11)).toBe("11 задач");
    expect(formatProblemCount(21)).toBe("21 задача");
    expect(formatProblemCount(0)).toBe("нет задач");
    expect(pluralize(22, ["день", "дня", "дней"])).toBe("дня");
  });
});

describe("<Heatmap>", () => {
  it("renders one accessible cell per day with its label and level", () => {
    render(<Heatmap days={sample()} end={END} />);
    const cells = screen.getAllByRole("img");
    expect(cells).toHaveLength(52 * 7 + 3);

    const busy = screen.getByLabelText("14 окт 2026: 3 задачи");
    expect(busy).toHaveAttribute("data-level", "2");
    expect(screen.getByLabelText("13 окт 2026: 1 задача")).toHaveAttribute("data-level", "1");
    expect(screen.getByLabelText("12 окт 2026: 6 задач")).toHaveAttribute("data-level", "4");
    expect(screen.getByLabelText("11 окт 2026: 5 задач")).toHaveAttribute("data-level", "3");
    expect(screen.getByLabelText("9 окт 2026: нет задач")).toHaveAttribute("data-level", "0");
  });

  it("uses all five levels with distinct colours", () => {
    const days = [0, 1, 2, 4, 6].map((count, i) => ({ date: addDays("2026-10-08", i), count }));
    render(<Heatmap days={days} end={END} />);
    const levels = new Set(
      screen
        .getAllByRole("img")
        .map((el) => el.getAttribute("data-level"))
        .filter(Boolean),
    );
    expect([...levels].sort()).toEqual(["0", "1", "2", "3", "4"]);
    const fills = new Set(screen.getAllByRole("img").map((el) => el.getAttribute("fill")));
    expect(fills.size).toBe(5);
  });

  it("shows a tooltip on hover and hides it on leave", () => {
    render(<Heatmap days={sample()} end={END} />);
    const cell = screen.getByLabelText("14 окт 2026: 3 задачи");
    fireEvent.mouseEnter(cell);
    expect(screen.getByRole("tooltip")).toHaveTextContent("14 окт 2026: 3 задачи");
    fireEvent.mouseLeave(cell);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("is keyboard accessible: one tab stop, arrow keys move between days", async () => {
    const user = userEvent.setup();
    render(<Heatmap days={sample()} end={END} />);
    const cells = screen.getAllByRole("img");
    expect(cells.filter((c) => c.getAttribute("tabindex") === "0")).toHaveLength(1);

    await user.tab();
    const start = screen.getByLabelText("14 окт 2026: 3 задачи");
    expect(start).toHaveFocus();
    expect(screen.getByRole("tooltip")).toHaveTextContent("14 окт 2026: 3 задачи");

    await user.keyboard("{ArrowUp}");
    expect(screen.getByLabelText("13 окт 2026: 1 задача")).toHaveFocus();
    await user.keyboard("{ArrowLeft}");
    expect(screen.getByLabelText("6 окт 2026: нет задач")).toHaveFocus();
    await user.keyboard("{ArrowDown}");
    expect(screen.getByLabelText("7 окт 2026: нет задач")).toHaveFocus();
    // the focused cell is the only tab stop now
    expect(
      screen.getAllByRole("img").filter((c) => c.getAttribute("tabindex") === "0"),
    ).toHaveLength(1);
  });

  it("does not move focus past the last day", async () => {
    const user = userEvent.setup();
    render(<Heatmap days={sample()} end={END} />);
    await user.tab();
    await user.keyboard("{ArrowRight}{ArrowDown}");
    expect(screen.getByLabelText("14 окт 2026: 3 задачи")).toHaveFocus();
  });

  it("shortens the grid for smaller periods", () => {
    render(<Heatmap days={[]} end={END} weeks={14} />);
    expect(screen.getAllByRole("img")).toHaveLength(13 * 7 + 3);
  });
});
