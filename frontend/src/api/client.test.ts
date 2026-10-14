import { vi } from "vitest";
import { ApiError, buildQuery, getAccessToken, request, setAccessToken } from "./client";

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status });
}

afterEach(() => {
  setAccessToken(null);
  vi.unstubAllGlobals();
});

describe("buildQuery", () => {
  it("skips empty values and repeats array params", () => {
    expect(buildQuery({ q: "dp", page: 2, empty: "", none: undefined, tag: ["a", "b"] })).toBe(
      "?q=dp&page=2&tag=a&tag=b",
    );
    expect(buildQuery({})).toBe("");
  });
});

describe("request", () => {
  it("sends the bearer token and parses JSON", async () => {
    setAccessToken("tok");
    const fetchMock = vi.fn(async () => json(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(request("/me")).resolves.toEqual({ ok: true });
    const init = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect((init.headers as Record<string, string>).Authorization).toBe("Bearer tok");
    expect(init.credentials).toBe("include");
  });

  it("refreshes the access token once on 401 and retries", async () => {
    setAccessToken("expired");
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/auth/refresh"))
        return json(200, { access_token: "fresh", token_type: "bearer" });
      const auth = (init?.headers as Record<string, string>).Authorization;
      return auth === "Bearer fresh"
        ? json(200, { id: 1 })
        : json(401, { detail: "Требуется авторизация" });
    });
    vi.stubGlobal("fetch", fetchMock);
    await expect(request("/me")).resolves.toEqual({ id: 1 });
    expect(getAccessToken()).toBe("fresh");
    expect(fetchMock).toHaveBeenCalledTimes(3);
  });

  it("gives up and notifies when refresh fails", async () => {
    setAccessToken("expired");
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json(401, { detail: "Требуется авторизация" })),
    );
    await expect(request("/me")).rejects.toMatchObject({ status: 401 });
    expect(getAccessToken()).toBeNull();
  });

  it("does not try to refresh for anonymous (auth) requests", async () => {
    const fetchMock = vi.fn(async () => json(401, { detail: "Неверный email или пароль" }));
    vi.stubGlobal("fetch", fetchMock);
    await expect(
      request("/auth/login", { method: "POST", body: {}, anonymous: true }),
    ).rejects.toThrow("Неверный email или пароль");
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("turns FastAPI validation errors into a readable message", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json(422, {
          detail: [{ loc: ["body", "password"], msg: "String should have at least 8 characters" }],
        }),
      ),
    );
    await expect(request("/auth/register", { anonymous: true })).rejects.toThrow(
      "password: String should have at least 8 characters",
    );
  });

  it("reports network failures and server errors in Russian", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))),
    );
    await expect(request("/me", { anonymous: true })).rejects.toMatchObject({ status: 0 });
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response("oops", { status: 500 })),
    );
    const error = await request("/me", { anonymous: true }).catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toBe("Ошибка сервера, попробуйте позже");
  });

  it("returns undefined for 204 responses", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => new Response(null, { status: 204 })),
    );
    await expect(
      request("/solves/1", { method: "DELETE", anonymous: true }),
    ).resolves.toBeUndefined();
  });
});
