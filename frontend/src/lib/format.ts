const MONTHS_SHORT = [
  "янв",
  "фев",
  "мар",
  "апр",
  "мая",
  "июн",
  "июл",
  "авг",
  "сен",
  "окт",
  "ноя",
  "дек",
];

/** "2026-10-12" -> "12 окт 2026" (works on the string, so no time-zone shifts). */
export function formatDate(iso: string): string {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return `${day} ${MONTHS_SHORT[month - 1]} ${year}`;
}

export function monthShort(monthIndex: number): string {
  return MONTHS_SHORT[monthIndex];
}

/** Russian plural form: pluralize(1, ["задача", "задачи", "задач"]) -> "задача". */
export function pluralize(n: number, forms: [string, string, string]): string {
  const abs = Math.abs(n) % 100;
  const last = abs % 10;
  if (abs > 10 && abs < 20) return forms[2];
  if (last > 1 && last < 5) return forms[1];
  if (last === 1) return forms[0];
  return forms[2];
}

export function formatProblemCount(n: number): string {
  return n === 0 ? "нет задач" : `${n} ${pluralize(n, ["задача", "задачи", "задач"])}`;
}

export function formatDays(n: number): string {
  return `${n} ${pluralize(n, ["день", "дня", "дней"])}`;
}

/** The user's current calendar date as YYYY-MM-DD in the given IANA time zone. */
export function todayIn(timeZone: string, now: Date = new Date()): string {
  try {
    return new Intl.DateTimeFormat("en-CA", {
      timeZone,
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).format(now);
  } catch {
    return now.toISOString().slice(0, 10);
  }
}

/** An instant (ISO timestamp) as a local calendar date in the given time zone. */
export function formatInstant(iso: string, timeZone: string): string {
  return formatDate(todayIn(timeZone, new Date(iso)));
}
