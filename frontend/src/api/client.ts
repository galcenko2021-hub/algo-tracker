// Thin fetch wrapper. The access token lives in memory only; the refresh token is an httpOnly
// cookie managed by the browser, so a page reload silently restores the session via /auth/refresh.

import type { TokenResponse } from "./types";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

let accessToken: string | null = null;
let refreshInFlight: Promise<string | null> | null = null;
let onSessionExpired: (() => void) | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setSessionExpiredHandler(handler: (() => void) | null): void {
  onSessionExpired = handler;
}

type Params = Record<string, string | number | boolean | string[] | null | undefined>;

interface RequestOptions {
  method?: "GET" | "POST" | "PATCH" | "DELETE";
  body?: unknown;
  params?: Params;
  /** Skip the Authorization header and the refresh-and-retry logic (auth endpoints). */
  anonymous?: boolean;
}

export function buildQuery(params?: Params): string {
  if (!params) return "";
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => search.append(key, v));
    else search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

function messageFromDetail(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    const first = detail[0] as { msg?: string; loc?: unknown[] };
    const field = Array.isArray(first.loc) ? String(first.loc[first.loc.length - 1]) : "";
    const text = first.msg ?? "некорректные данные";
    return field && field !== "body" ? `${field}: ${text}` : text;
  }
  if (status >= 500) return "Ошибка сервера, попробуйте позже";
  return "Не удалось выполнить запрос";
}

async function send(
  path: string,
  options: RequestOptions,
  token: string | null,
): Promise<Response> {
  const headers: Record<string, string> = {};
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (token && !options.anonymous) headers["Authorization"] = `Bearer ${token}`;
  try {
    return await fetch(`/api${path}${buildQuery(options.params)}`, {
      method: options.method ?? "GET",
      headers,
      credentials: "include",
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
    });
  } catch {
    throw new ApiError(0, "Нет связи с сервером. Проверьте подключение к сети.");
  }
}

/** Exchange the refresh cookie for a new access token; concurrent callers share one request. */
export function refreshSession(): Promise<string | null> {
  refreshInFlight ??= (async () => {
    try {
      const response = await send("/auth/refresh", { method: "POST", anonymous: true }, null);
      if (!response.ok) return null;
      const data = (await response.json()) as TokenResponse;
      accessToken = data.access_token;
      return accessToken;
    } catch {
      return null;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  let response = await send(path, options, accessToken);
  if (response.status === 401 && !options.anonymous) {
    const fresh = await refreshSession();
    if (fresh) {
      response = await send(path, options, fresh);
    } else {
      accessToken = null;
      onSessionExpired?.();
    }
  }
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = ((await response.json()) as { detail?: unknown }).detail;
    } catch {
      detail = undefined;
    }
    throw new ApiError(response.status, messageFromDetail(detail, response.status));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
