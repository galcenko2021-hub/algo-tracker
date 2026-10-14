import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";
import type { User } from "./api/types";
import { AuthContext, type AuthContextValue, type AuthStatus } from "./lib/auth-context";

export const testUser: User = {
  id: 1,
  email: "me@example.com",
  cf_handle: "tourist",
  timezone: "Europe/Moscow",
  created_at: "2026-01-01T00:00:00Z",
};

export function authValue(
  status: AuthStatus = "authenticated",
  overrides: Partial<AuthContextValue> = {},
): AuthContextValue {
  return {
    status,
    user: status === "authenticated" ? testUser : null,
    login: vi.fn(),
    register: vi.fn(),
    logout: vi.fn(),
    refreshUser: vi.fn(),
    ...overrides,
  };
}

interface Options {
  route?: string;
  auth?: AuthContextValue;
}

export function renderWithProviders(ui: ReactElement, { route = "/", auth }: Options = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthContext.Provider value={auth ?? authValue()}>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  );
}

type Handler = unknown | ((request: { url: string; body: unknown }) => unknown);

/**
 * Replaces global fetch. Keys look like "GET /api/reviews/due"; the query string is ignored.
 * A function value receives the parsed JSON body. Unknown routes fail the test loudly.
 */
export function mockFetch(routes: Record<string, Handler>) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://localhost");
    const method = init?.method ?? "GET";
    const key = `${method} ${url.pathname}`;
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method, path: url.pathname, body });
    if (!(key in routes)) throw new Error(`Unexpected request: ${key}`);
    const handler = routes[key];
    const payload = typeof handler === "function" ? handler({ url: url.href, body }) : handler;
    if (payload === undefined) return new Response(null, { status: 204 });
    return new Response(JSON.stringify(payload), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls, fetchMock };
}
