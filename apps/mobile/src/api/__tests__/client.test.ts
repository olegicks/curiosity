import { ApiClient } from "@/api/client";
import { ApiError, NETWORK_ERROR } from "@/api/errors";
import { errorBody, json, memoryTokenStore, scriptedFetch, tokens } from "@/test/fakeApi";

function makeClient(routes: Parameters<typeof scriptedFetch>[0], initialTokens = tokens(1)) {
  const store = memoryTokenStore(initialTokens);
  const { fetchImpl, calls } = scriptedFetch(routes);
  const onSessionExpired = jest.fn();
  const client = new ApiClient({
    baseUrl: "https://api.test",
    appVersion: "1.2.3",
    platform: "ios",
    tokenStore: store,
    onSessionExpired,
    fetchImpl,
  });
  return { client, store, calls, onSessionExpired };
}

const headersOf = (init: RequestInit) => init.headers as Record<string, string>;

test("sends auth, version and platform headers", async () => {
  const { client, calls } = makeClient({ "GET /v1/me": () => json(200, { ok: true }) });
  await expect(client.get("/v1/me")).resolves.toEqual({ ok: true });
  const headers = headersOf(calls[0]!.init);
  expect(headers.Authorization).toBe("Bearer access-1");
  expect(headers["X-App-Version"]).toBe("1.2.3");
  expect(headers["X-Platform"]).toBe("ios");
});

test("public requests omit the bearer token", async () => {
  const { client, calls } = makeClient({ "POST /v1/auth/login": () => json(200, {}) });
  await client.post("/v1/auth/login", { email: "a", password: "b" }, { auth: false });
  expect(headersOf(calls[0]!.init).Authorization).toBeUndefined();
  expect(calls[0]!.init.body).toBe(JSON.stringify({ email: "a", password: "b" }));
});

test("refreshes once on 401 UNAUTHENTICATED and retries", async () => {
  let meCalls = 0;
  const { client, store, calls } = makeClient({
    "GET /v1/me": (_url, init) => {
      meCalls += 1;
      const auth = headersOf(init).Authorization;
      return auth === "Bearer access-2"
        ? json(200, { ok: true })
        : json(401, errorBody("UNAUTHENTICATED"));
    },
    "POST /v1/auth/refresh": () => json(200, { tokens: tokens(2) }),
  });
  await expect(client.get("/v1/me")).resolves.toEqual({ ok: true });
  expect(meCalls).toBe(2);
  expect(store.get()?.access_token).toBe("access-2");
  const refresh = calls.find((c) => c.url.endsWith("/v1/auth/refresh"))!;
  expect(refresh.init.body).toBe(JSON.stringify({ refresh_token: "refresh-1" }));
  expect(headersOf(refresh.init).Authorization).toBeUndefined();
});

test("concurrent 401s share a single refresh", async () => {
  let refreshes = 0;
  const { client } = makeClient({
    "GET /v1/me": (_url, init) =>
      headersOf(init).Authorization === "Bearer access-2"
        ? json(200, {})
        : json(401, errorBody("UNAUTHENTICATED")),
    "POST /v1/auth/refresh": async () => {
      refreshes += 1;
      await new Promise((resolve) => setTimeout(resolve, 5));
      return json(200, { tokens: tokens(2) });
    },
  });
  await Promise.all([client.get("/v1/me"), client.get("/v1/me"), client.get("/v1/me")]);
  expect(refreshes).toBe(1);
});

test("a rejected refresh clears the session and reports expiry", async () => {
  const { client, store, onSessionExpired } = makeClient({
    "GET /v1/me": () => json(401, errorBody("UNAUTHENTICATED")),
    "POST /v1/auth/refresh": () => json(401, errorBody("REFRESH_TOKEN_REUSED")),
  });
  await expect(client.get("/v1/me")).rejects.toMatchObject({ code: "UNAUTHENTICATED" });
  expect(store.get()).toBeNull();
  expect(onSessionExpired).toHaveBeenCalledTimes(1);
});

test("other 401s are returned as-is without refreshing", async () => {
  const { client, calls } = makeClient({
    "POST /v1/auth/login": () => json(401, errorBody("INVALID_CREDENTIALS")),
  });
  await expect(client.post("/v1/auth/login", {}, { auth: false })).rejects.toMatchObject({
    status: 401,
    code: "INVALID_CREDENTIALS",
  });
  expect(calls).toHaveLength(1);
});

test("error envelopes become ApiError with details and request id", async () => {
  const { client } = makeClient({
    "PATCH /v1/me/preferences": () =>
      json(422, errorBody("INVALID_TIMEZONE", [{ field: "timezone" }])),
  });
  const error = await client.patch("/v1/me/preferences", {}).catch((e: unknown) => e);
  expect(error).toBeInstanceOf(ApiError);
  expect(error).toMatchObject({
    status: 422,
    code: "INVALID_TIMEZONE",
    details: [{ field: "timezone" }],
    requestId: "req-1",
  });
});

test("network failures are reported as NETWORK_ERROR", async () => {
  const { client } = makeClient({
    "GET /v1/me": () => {
      throw new TypeError("Network request failed");
    },
  });
  await expect(client.get("/v1/me")).rejects.toMatchObject({ code: NETWORK_ERROR, status: 0 });
});

test("204 responses resolve to undefined", async () => {
  const { client } = makeClient({ "POST /v1/auth/logout": () => json(204, null) });
  await expect(client.post("/v1/auth/logout", { refresh_token: "r" })).resolves.toBeUndefined();
});
