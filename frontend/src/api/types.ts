// Response and request shapes of the algo-tracker REST API (see /api/docs).

export type Platform = "codeforces" | "leetcode" | "yandex" | "other";
export type SolveSource = "manual" | "codeforces";

export interface User {
  id: number;
  email: string;
  cf_handle: string | null;
  timezone: string;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface Problem {
  id: number;
  platform: Platform;
  external_id: string;
  title: string;
  url: string | null;
  rating: number | null;
  tags: string[];
}

export interface Solve {
  id: number;
  solved_at: string;
  source: SolveSource;
  time_spent_min: number | null;
  notes: string | null;
  problem: Problem;
}

export interface SolvePage {
  items: Solve[];
  total: number;
  page: number;
  page_size: number;
}

export interface SolveCreate {
  platform: Platform;
  external_id?: string | null;
  title: string;
  url?: string | null;
  rating?: number | null;
  tags: string[];
  solved_at?: string | null;
  time_spent_min?: number | null;
  notes?: string | null;
}

export interface SolvePatch {
  solved_at?: string;
  time_spent_min?: number | null;
  notes?: string | null;
  title?: string;
  url?: string | null;
  rating?: number | null;
  tags?: string[];
}

export interface SolveFilters {
  from?: string;
  to?: string;
  tag?: string[];
  platform?: Platform | "";
  q?: string;
  page?: number;
  page_size?: number;
}

export interface Summary {
  total: number;
  last_7_days: number;
  last_30_days: number;
  current_streak: number;
  longest_streak: number;
}

export interface HeatmapDay {
  date: string; // YYYY-MM-DD, the user's local date
  count: number;
}

export interface Topic {
  tag: string;
  solved: number;
  share: number;
  avg_rating: number | null;
  last_solved_at: string | null;
  avg_review_quality: number | null;
  weakness: number;
}

export interface NextIntervals {
  again: number;
  hard: number;
  good: number;
  easy: number;
}

export interface DueCard {
  card_id: number;
  problem: Problem;
  notes: string | null;
  due_date: string;
  interval_days: number;
  repetitions: number;
  lapses: number;
  ease: number;
  next_intervals: NextIntervals;
}

export interface DueResponse {
  count: number;
  cards: DueCard[];
}

export interface AnswerResponse {
  card_id: number;
  interval_days: number;
  due_date: string;
  ease: number;
  repetitions: number;
  lapses: number;
}

export interface UpcomingDay {
  date: string;
  count: number;
}

export interface ImportResult {
  imported: number;
  skipped: number;
  attempts_recorded: number;
}

export interface RecommendedProblem {
  external_id: string;
  title: string;
  url: string;
  rating: number | null;
  tags: string[];
  solved_count: number;
}

export interface RecommendationItem {
  problem: RecommendedProblem;
  score: number;
  reason: string;
  predicted_solve_prob: number | null;
}

export interface Recommendations {
  method: "ml" | "heuristic";
  fallback_reason: string | null;
  level: number;
  items: RecommendationItem[];
}
