import type { HeatmapDay } from "../api/types";
import { formatDate, formatProblemCount } from "./format";

export const DAY_MS = 86_400_000;

export type Period = "year" | "half" | "quarter";

export const PERIOD_WEEKS: Record<Period, number> = { year: 53, half: 27, quarter: 14 };

export const PERIOD_LABELS: Record<Period, string> = {
  year: "Год",
  half: "6 месяцев",
  quarter: "3 месяца",
};

export interface Cell {
  date: string; // YYYY-MM-DD
  count: number;
  level: 0 | 1 | 2 | 3 | 4;
  week: number; // column
  weekday: number; // row, Monday = 0
}

function toUtc(iso: string): number {
  const [y, m, d] = iso.split("-").map(Number);
  return Date.UTC(y, m - 1, d);
}

function fromUtc(ms: number): string {
  return new Date(ms).toISOString().slice(0, 10);
}

/** Monday = 0 ... Sunday = 6. */
export function weekdayIndex(iso: string): number {
  return (new Date(toUtc(iso)).getUTCDay() + 6) % 7;
}

export function addDays(iso: string, days: number): string {
  return fromUtc(toUtc(iso) + days * DAY_MS);
}

/** Fixed intensity steps: 0, 1, 2-3, 4-5, 6+ solves per day. */
export function intensityLevel(count: number): 0 | 1 | 2 | 3 | 4 {
  if (count <= 0) return 0;
  if (count === 1) return 1;
  if (count <= 3) return 2;
  if (count <= 5) return 3;
  return 4;
}

/** First day (a Monday) of the grid that ends with the week containing `end`. */
export function gridStart(end: string, weeks: number): string {
  const lastMonday = addDays(end, -weekdayIndex(end));
  return addDays(lastMonday, -(weeks - 1) * 7);
}

/**
 * Lay days out as GitHub does: columns are weeks starting on Monday, rows are weekdays.
 * Days after `end` (the rest of the current week) are not rendered.
 */
export function buildGrid(days: HeatmapDay[], end: string, weeks: number): Cell[] {
  const counts = new Map(days.map((d) => [d.date, d.count]));
  const start = gridStart(end, weeks);
  const cells: Cell[] = [];
  for (let week = 0; week < weeks; week++) {
    for (let weekday = 0; weekday < 7; weekday++) {
      const date = addDays(start, week * 7 + weekday);
      if (date > end) continue;
      const count = counts.get(date) ?? 0;
      cells.push({ date, count, level: intensityLevel(count), week, weekday });
    }
  }
  return cells;
}

/** Column index and label for every month's first visible week. */
export function monthLabels(cells: Cell[]): { week: number; month: number }[] {
  const labels: { week: number; month: number }[] = [];
  let last = -1;
  for (const cell of cells) {
    if (cell.weekday !== 0) continue;
    const month = Number(cell.date.slice(5, 7)) - 1;
    if (month !== last) {
      labels.push({ week: cell.week, month });
      last = month;
    }
  }
  return labels;
}

/** Accessible label and tooltip text, e.g. "12 окт 2026: 3 задачи". */
export function cellLabel(cell: Pick<Cell, "date" | "count">): string {
  return `${formatDate(cell.date)}: ${formatProblemCount(cell.count)}`;
}
