import { QueryClient } from "@tanstack/react-query";
import { ApiError } from "../api/client";

/** Retry network and server errors twice; client errors (4xx) will not fix themselves. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= 2) return false;
  if (error instanceof ApiError) return error.status === 0 || error.status >= 500;
  return true;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: shouldRetry, refetchOnWindowFocus: false, staleTime: 15_000 },
    },
  });
}
