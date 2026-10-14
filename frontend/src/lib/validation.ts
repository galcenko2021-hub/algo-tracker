import type { Platform, Solve, SolveCreate, SolvePatch } from "../api/types";

export function validateCredentials(email: string, password: string, isRegister: boolean) {
  const errors: { email?: string; password?: string } = {};
  if (!/^\S+@\S+\.\S+$/.test(email.trim())) errors.email = "Введите корректный email";
  if (isRegister && password.length < 8) errors.password = "Пароль — минимум 8 символов";
  if (!isRegister && password.length === 0) errors.password = "Введите пароль";
  return errors;
}

export interface SolveFormValues {
  platform: Platform;
  externalId: string;
  title: string;
  url: string;
  rating: string;
  tags: string[];
  /** YYYY-MM-DD, empty = now */
  solvedDate: string;
  timeSpent: string;
  notes: string;
}

export type SolveFormErrors = Partial<Record<keyof SolveFormValues, string>>;

export const emptySolveForm: SolveFormValues = {
  platform: "codeforces",
  externalId: "",
  title: "",
  url: "",
  rating: "",
  tags: [],
  solvedDate: "",
  timeSpent: "",
  notes: "",
};

export const PLATFORM_LABELS: Record<Platform, string> = {
  codeforces: "Codeforces",
  leetcode: "LeetCode",
  yandex: "Яндекс",
  other: "Другое",
};

function isInteger(text: string): boolean {
  return /^\d+$/.test(text.trim());
}

export function validateSolveForm(values: SolveFormValues): SolveFormErrors {
  const errors: SolveFormErrors = {};
  if (values.title.trim().length === 0) errors.title = "Укажите название задачи";
  else if (values.title.length > 500) errors.title = "Название длиннее 500 символов";
  if (values.url.trim() && !/^https?:\/\/\S+$/i.test(values.url.trim())) {
    errors.url = "Ссылка должна начинаться с http:// или https://";
  }
  if (values.rating.trim()) {
    if (!isInteger(values.rating) || Number(values.rating) > 5000) {
      errors.rating = "Рейтинг — целое число от 0 до 5000";
    }
  }
  if (values.timeSpent.trim() && !isInteger(values.timeSpent)) {
    errors.timeSpent = "Время — целое число минут";
  }
  if (values.notes.length > 2000) errors.notes = "Заметка длиннее 2000 символов";
  if (values.externalId.length > 255) errors.externalId = "Идентификатор слишком длинный";
  return errors;
}

/**
 * The date picker only has a day. Today (or empty) means "now" so the server stamps the exact
 * time; any other day is stored at noon UTC, which falls on the same calendar day in nearly
 * every time zone.
 */
export function solvedAtFromDate(date: string, today: string): string | undefined {
  if (!date || date === today) return undefined;
  return `${date}T12:00:00Z`;
}

const orNull = (text: string): string | null => (text.trim() ? text.trim() : null);
const numOrNull = (text: string): number | null => (text.trim() ? Number(text) : null);

export function toCreatePayload(values: SolveFormValues, today: string): SolveCreate {
  return {
    platform: values.platform,
    external_id: orNull(values.externalId),
    title: values.title.trim(),
    url: orNull(values.url),
    rating: numOrNull(values.rating),
    tags: values.tags,
    solved_at: solvedAtFromDate(values.solvedDate, today) ?? null,
    time_spent_min: numOrNull(values.timeSpent),
    notes: orNull(values.notes),
  };
}

export function toPatchPayload(values: SolveFormValues): SolvePatch {
  return {
    title: values.title.trim(),
    url: orNull(values.url),
    rating: numOrNull(values.rating),
    tags: values.tags,
    time_spent_min: numOrNull(values.timeSpent),
    notes: orNull(values.notes),
  };
}

export function valuesFromSolve(solve: Solve, timeZoneDate: string): SolveFormValues {
  return {
    platform: solve.problem.platform,
    externalId: solve.problem.external_id,
    title: solve.problem.title,
    url: solve.problem.url ?? "",
    rating: solve.problem.rating?.toString() ?? "",
    tags: solve.problem.tags,
    solvedDate: timeZoneDate,
    timeSpent: solve.time_spent_min?.toString() ?? "",
    notes: solve.notes ?? "",
  };
}
