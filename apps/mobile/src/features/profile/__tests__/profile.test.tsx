import AsyncStorage from "@react-native-async-storage/async-storage";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react-native";
import { Pressable, Text } from "react-native";

import type { ProgressOut } from "@/api/types";
import { AuthProvider, useAuth } from "@/features/auth/AuthProvider";
import { routeFor } from "@/features/auth/session";
import { exportFileName } from "@/features/profile/exportData";
import { accuracyLabel, earnedDate, stageCounts } from "@/features/profile/profile";
import { strings } from "@/i18n/en";
import { errorBody, json, me, memoryTokenStore, scriptedFetch, tokens } from "@/test/fakeApi";

const progress = (byStage: Record<string, number>, correct: number, total: number) =>
  ({
    lessons: { total: 27, started: 6, completed: 5, by_stage: byStage },
    by_topic: [],
    xp: { total: 140, today: 15, goal: 20 },
    streak: { current: 3, longest: 5, freezes_available: 1, done_today: false, at_risk: false },
    recall_accuracy: { correct, total },
    reviews: { due_count: 0, next_due_on: null },
  }) as ProgressOut;

describe("profile helpers", () => {
  test("stage counts in order with names", () => {
    expect(stageCounts(progress({ "1": 2, "2": 2, "3": 1 }, 0, 0))).toEqual([
      { stage: 1, label: "Learned", count: 2 },
      { stage: 2, label: "Recalled", count: 2 },
      { stage: 3, label: "Understood", count: 1 },
      { stage: 4, label: "Retained", count: 0 },
    ]);
  });

  test("recall accuracy wording", () => {
    expect(accuracyLabel(progress({}, 8, 10))).toBe("8 of last 10 recalls correct");
    expect(accuracyLabel(progress({}, 0, 0))).toBe(strings.profile.noAccuracy);
  });

  test("dates and export file names", () => {
    expect(earnedDate("2026-11-02T12:00:00Z")).toMatch(/^\d+ Nov 2026$/);
    expect(exportFileName(new Date(2026, 10, 2))).toBe("curiosity-export-2026-11-02.json");
  });
});

function Probe({ password }: { password: string | null }) {
  const auth = useAuth();
  return (
    <>
      <Text testID="route">{routeFor(auth.session)}</Text>
      <Pressable
        testID="change"
        onPress={() => void auth.changePassword("old pass phrase", "new pass phrase")}
      />
      <Pressable
        testID="delete"
        onPress={() => void auth.deleteAccount(password).catch(() => undefined)}
      />
    </>
  );
}

async function renderWith(routes: Parameters<typeof scriptedFetch>[0], password: string | null) {
  const store = memoryTokenStore(tokens(1));
  const { fetchImpl, calls } = scriptedFetch({
    "GET /v1/me": () => json(200, me({ is_guest: password === null, onboarding_completed: true })),
    ...routes,
  });
  await render(
    <QueryClientProvider client={new QueryClient()}>
      <AuthProvider tokenStore={store} fetchImpl={fetchImpl}>
        <Probe password={password} />
      </AuthProvider>
    </QueryClientProvider>,
  );
  await waitFor(() => expect(screen.getByTestId("route").props.children).toBe("app"));
  return { store, calls };
}

test("changing the password keeps this device signed in with fresh tokens", async () => {
  const { store, calls } = await renderWith(
    { "POST /v1/me/password": () => json(200, { tokens: tokens(2) }) },
    "secret",
  );
  await fireEvent.press(screen.getByTestId("change"));
  await waitFor(() => expect(store.get()?.access_token).toBe("access-2"));
  const call = calls.find((c) => c.url.endsWith("/v1/me/password"))!;
  expect(JSON.parse(String(call.init.body))).toEqual({
    current_password: "old pass phrase",
    new_password: "new pass phrase",
  });
  expect(screen.getByTestId("route").props.children).toBe("app");
});

test("a guest deletes with DELETE and the device is wiped", async () => {
  await AsyncStorage.setItem("theme-preference", "dark");
  const { store, calls } = await renderWith({ "DELETE /v1/me": () => json(204, null) }, null);
  await fireEvent.press(screen.getByTestId("delete"));
  await waitFor(() => expect(screen.getByTestId("route").props.children).toBe("auth"));
  const call = calls.find((c) => c.init.method === "DELETE")!;
  expect(JSON.parse(String(call.init.body))).toEqual({ confirm: "DELETE" });
  expect(store.get()).toBeNull();
  expect(await AsyncStorage.getItem("theme-preference")).toBeNull();
});

test("a full account deletes with its password; a wrong one keeps the session", async () => {
  const { store, calls } = await renderWith(
    { "DELETE /v1/me": () => json(401, errorBody("INVALID_CREDENTIALS")) },
    "wrong",
  );
  await fireEvent.press(screen.getByTestId("delete"));
  await waitFor(() => expect(calls.some((c) => c.init.method === "DELETE")).toBe(true));
  const call = calls.find((c) => c.init.method === "DELETE")!;
  expect(JSON.parse(String(call.init.body))).toEqual({ password: "wrong" });
  expect(store.get()).not.toBeNull();
  expect(screen.getByTestId("route").props.children).toBe("app");
});
