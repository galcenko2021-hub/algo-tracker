import type { Topic } from "../api/types";

export type SortKey =
  "tag" | "solved" | "avg_rating" | "last_solved_at" | "avg_review_quality" | "weakness";

export function sortTopics(topics: Topic[], key: SortKey, direction: "asc" | "desc"): Topic[] {
  const sign = direction === "asc" ? 1 : -1;
  return [...topics].sort((a, b) => {
    const left = a[key];
    const right = b[key];
    if (left === right) return a.tag.localeCompare(b.tag);
    if (left === null) return 1; // missing values always go last
    if (right === null) return -1;
    return (left < right ? -1 : 1) * sign;
  });
}
