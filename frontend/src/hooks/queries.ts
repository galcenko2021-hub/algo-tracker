import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/endpoints";
import type { SolveCreate, SolveFilters, SolvePatch } from "../api/types";

export const queryKeys = {
  summary: ["summary"] as const,
  heatmap: (from: string, to: string) => ["heatmap", from, to] as const,
  topics: ["topics"] as const,
  solves: (filters: SolveFilters) => ["solves", filters] as const,
  tags: (q: string) => ["tags", q] as const,
  due: ["due"] as const,
  upcoming: ["upcoming"] as const,
  recommendations: (limit: number) => ["recommendations", limit] as const,
};

export const useSummary = () => useQuery({ queryKey: queryKeys.summary, queryFn: api.summary });

export const useHeatmap = (from: string, to: string) =>
  useQuery({ queryKey: queryKeys.heatmap(from, to), queryFn: () => api.heatmap(from, to) });

export const useTopics = () => useQuery({ queryKey: queryKeys.topics, queryFn: api.topics });

export const useSolves = (filters: SolveFilters) =>
  useQuery({
    queryKey: queryKeys.solves(filters),
    queryFn: () => api.solves(filters),
    placeholderData: keepPreviousData,
  });

export const useTagSuggestions = (q: string) =>
  useQuery({ queryKey: queryKeys.tags(q), queryFn: () => api.tags(q), staleTime: 30_000 });

export const useDue = () => useQuery({ queryKey: queryKeys.due, queryFn: api.due });

export const useRecommendations = (limit = 5) =>
  useQuery({
    queryKey: queryKeys.recommendations(limit),
    queryFn: () => api.recommendations(limit),
    staleTime: 60_000,
  });

/** Everything derived from solves and reviews goes stale after any change to them. */
function useInvalidateAll() {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(
      ["summary", "heatmap", "topics", "solves", "tags", "due", "upcoming", "recommendations"].map(
        (key) => queryClient.invalidateQueries({ queryKey: [key] }),
      ),
    );
}

export function useCreateSolve() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (body: SolveCreate) => api.createSolve(body),
    onSuccess: invalidate,
  });
}

export function useUpdateSolve() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: ({ id, body }: { id: number; body: SolvePatch }) => api.updateSolve(id, body),
    onSuccess: invalidate,
  });
}

export function useDeleteSolve() {
  const invalidate = useInvalidateAll();
  return useMutation({ mutationFn: (id: number) => api.deleteSolve(id), onSuccess: invalidate });
}

export function useAnswerCard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ cardId, quality }: { cardId: number; quality: number }) =>
      api.answer(cardId, quality),
    onSuccess: () =>
      Promise.all(
        ["upcoming", "topics"].map((key) => queryClient.invalidateQueries({ queryKey: [key] })),
      ),
  });
}

export function useImportCodeforces() {
  const invalidate = useInvalidateAll();
  return useMutation({
    mutationFn: (handle?: string) => api.importCodeforces(handle),
    onSuccess: invalidate,
  });
}
