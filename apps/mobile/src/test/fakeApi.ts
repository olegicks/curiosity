/** Test doubles: an in-memory token store and a scripted fetch. */
import type { TokenStore } from "@/api/client";
import type { Tokens } from "@/api/types";

export function memoryTokenStore(initial: Tokens | null = null) {
  let current = initial;
  const store: TokenStore & { load(): Promise<Tokens | null> } = {
    get: () => current,
    set: async (tokens) => {
      current = tokens;
    },
    load: async () => current,
  };
  return store;
}

export const tokens = (n = 1): Tokens => ({
  access_token: `access-${n}`,
  access_expires_in: 900,
  refresh_token: `refresh-${n}`,
  token_type: "Bearer",
});

export function json(status: number, body: unknown): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

export const errorBody = (code: string, details: unknown[] = []) => ({
  error: { code, message: code, details, request_id: "req-1" },
});

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

/** A fetch that dispatches on "METHOD /path" and records every call. */
export function scriptedFetch(routes: Record<string, Handler>) {
  const calls: { url: string; init: RequestInit }[] = [];
  const fetchImpl = (async (input: RequestInfo | URL, init: RequestInit = {}) => {
    const url = String(input);
    calls.push({ url, init });
    const path = new URL(url).pathname;
    const handler = routes[`${init.method ?? "GET"} ${path}`];
    if (!handler) throw new TypeError(`unexpected request ${init.method} ${path}`);
    return handler(url, init);
  }) as typeof fetch;
  return { fetchImpl, calls };
}

export const me = (overrides: { is_guest?: boolean; onboarding_completed?: boolean } = {}) => ({
  user: {
    id: "u1",
    is_guest: overrides.is_guest ?? true,
    email: null,
    display_name: null,
    created_at: "2026-11-02T12:00:00Z",
  },
  preferences: {
    timezone: "UTC",
    daily_xp_goal: 20 as const,
    interest_topics: [],
    onboarding_completed: overrides.onboarding_completed ?? false,
  },
});
