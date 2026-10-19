import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { Pressable, Text } from "react-native";

import { AuthProvider, useAuth } from "@/features/auth/AuthProvider";
import { routeFor } from "@/features/auth/session";
import { strings } from "@/i18n/en";
import { errorBody, json, me, memoryTokenStore, scriptedFetch, tokens } from "@/test/fakeApi";

function Probe() {
  const auth = useAuth();
  const notice = auth.session.status === "signedOut" ? auth.session.notice : null;
  return (
    <>
      <Text testID="route">{routeFor(auth.session)}</Text>
      <Text testID="notice">{notice ?? ""}</Text>
      <Pressable testID="guest" onPress={() => void auth.startAsGuest()} />
      <Pressable testID="logout" onPress={() => void auth.logout()} />
    </>
  );
}

function renderWith(store: ReturnType<typeof memoryTokenStore>, fetchImpl: typeof fetch) {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider tokenStore={store} fetchImpl={fetchImpl}>
        <Probe />
      </AuthProvider>
    </QueryClientProvider>,
  );
}

const route = () => screen.getByTestId("route").props.children as string;

test("without saved tokens the user starts signed out", async () => {
  const { fetchImpl, calls } = scriptedFetch({});
  await renderWith(memoryTokenStore(), fetchImpl);
  await waitFor(() => expect(route()).toBe("auth"));
  expect(calls).toHaveLength(0);
});

test("starting as a guest stores tokens and opens onboarding", async () => {
  const store = memoryTokenStore();
  const { fetchImpl, calls } = scriptedFetch({
    "POST /v1/auth/guest": () => json(201, { user: me().user, tokens: tokens(1) }),
    "GET /v1/me": () => json(200, me()),
  });
  await renderWith(store, fetchImpl);
  await waitFor(() => expect(route()).toBe("auth"));
  await fireEvent.press(screen.getByTestId("guest"));
  await waitFor(() => expect(route()).toBe("onboarding"));
  expect(store.get()?.access_token).toBe("access-1");
  const guest = calls.find((c) => c.url.endsWith("/v1/auth/guest"))!;
  expect(JSON.parse(String(guest.init.body))).toHaveProperty("timezone");
});

test("a saved session is restored", async () => {
  const { fetchImpl } = scriptedFetch({
    "GET /v1/me": () => json(200, me({ onboarding_completed: true })),
  });
  await renderWith(memoryTokenStore(tokens(1)), fetchImpl);
  await waitFor(() => expect(route()).toBe("app"));
});

test("an expired session that cannot refresh returns to welcome with a notice", async () => {
  const store = memoryTokenStore(tokens(1));
  const { fetchImpl } = scriptedFetch({
    "GET /v1/me": () => json(401, errorBody("UNAUTHENTICATED")),
    "POST /v1/auth/refresh": () => json(401, errorBody("INVALID_REFRESH_TOKEN")),
  });
  await renderWith(store, fetchImpl);
  await waitFor(() => expect(route()).toBe("auth"));
  expect(screen.getByTestId("notice").props.children).toBe(strings.session.expired);
  expect(store.get()).toBeNull();
});

test("an unreachable API keeps the saved session and offers retry", async () => {
  const store = memoryTokenStore(tokens(1));
  const { fetchImpl } = scriptedFetch({
    "GET /v1/me": () => {
      throw new TypeError("Network request failed");
    },
  });
  await renderWith(store, fetchImpl);
  await waitFor(() => expect(route()).toBe("unavailable"));
  expect(store.get()).not.toBeNull();
});

test("logout revokes the refresh token and clears the session", async () => {
  const store = memoryTokenStore(tokens(1));
  const { fetchImpl, calls } = scriptedFetch({
    "GET /v1/me": () => json(200, me({ onboarding_completed: true })),
    "POST /v1/auth/logout": () => json(204, null),
  });
  await renderWith(store, fetchImpl);
  await waitFor(() => expect(route()).toBe("app"));
  await fireEvent.press(screen.getByTestId("logout"));
  await waitFor(() => expect(route()).toBe("auth"));
  expect(store.get()).toBeNull();
  const logout = calls.find((c) => c.url.endsWith("/v1/auth/logout"))!;
  expect(JSON.parse(String(logout.init.body))).toEqual({ refresh_token: "refresh-1" });
});
