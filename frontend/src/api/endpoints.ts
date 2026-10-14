import { request } from "./client";
import type {
  AnswerResponse,
  DueResponse,
  HeatmapDay,
  ImportResult,
  Recommendations,
  Solve,
  SolveCreate,
  SolveFilters,
  SolvePage,
  SolvePatch,
  Summary,
  Topic,
  TokenResponse,
  UpcomingDay,
  User,
} from "./types";

export const api = {
  register: (email: string, password: string) =>
    request<User>("/auth/register", { method: "POST", body: { email, password }, anonymous: true }),
  login: (email: string, password: string) =>
    request<TokenResponse>("/auth/login", {
      method: "POST",
      body: { email, password },
      anonymous: true,
    }),
  logout: () => request<void>("/auth/logout", { method: "POST", anonymous: true }),

  me: () => request<User>("/me"),
  updateMe: (patch: { cf_handle?: string | null; timezone?: string }) =>
    request<User>("/me", { method: "PATCH", body: patch }),

  solves: (filters: SolveFilters) => request<SolvePage>("/solves", { params: { ...filters } }),
  createSolve: (body: SolveCreate) => request<Solve>("/solves", { method: "POST", body }),
  updateSolve: (id: number, body: SolvePatch) =>
    request<Solve>(`/solves/${id}`, { method: "PATCH", body }),
  deleteSolve: (id: number) => request<void>(`/solves/${id}`, { method: "DELETE" }),
  tags: (q: string) => request<string[]>("/tags", { params: { q } }),

  summary: () => request<Summary>("/stats/summary"),
  heatmap: (from: string, to: string) =>
    request<HeatmapDay[]>("/stats/heatmap", { params: { from, to } }),
  topics: () => request<Topic[]>("/stats/topics"),

  due: () => request<DueResponse>("/reviews/due"),
  answer: (cardId: number, quality: number) =>
    request<AnswerResponse>(`/reviews/${cardId}/answer`, { method: "POST", body: { quality } }),
  upcoming: (days = 14) => request<UpcomingDay[]>("/reviews/upcoming", { params: { days } }),

  importCodeforces: (handle?: string) =>
    request<ImportResult>("/import/codeforces", {
      method: "POST",
      body: handle ? { handle } : {},
    }),

  recommendations: (limit = 5) =>
    request<Recommendations>("/recommendations", { params: { limit } }),
};
