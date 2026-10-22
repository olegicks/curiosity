import AsyncStorage from "@react-native-async-storage/async-storage";
import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useReducer,
  useRef,
} from "react";

import { ApiClient, type TokenStore } from "@/api/client";
import { createEndpoints, type Endpoints } from "@/api/endpoints";
import { ApiError, NETWORK_ERROR } from "@/api/errors";
import type { AuthOut, MeOut, Tokens } from "@/api/types";
import { strings } from "@/i18n/en";
import { API_URL, APP_VERSION, deviceTimezone, PLATFORM } from "@/lib/config";

import { initialSession, type SessionState, sessionReducer } from "./session";
import { createSecureTokenStore } from "./tokenStore";

type AuthContextValue = {
  session: SessionState;
  api: Endpoints;
  startAsGuest(): Promise<void>;
  login(email: string, password: string): Promise<void>;
  upgrade(email: string, password: string, displayName: string | null): Promise<void>;
  logout(): Promise<void>;
  /** Other sessions are revoked; this device keeps working with fresh tokens. */
  changePassword(currentPassword: string, newPassword: string): Promise<void>;
  /** Hard-deletes the account, then wipes everything stored on the device. */
  deleteAccount(password: string | null): Promise<void>;
  /** Re-read /me (e.g. after onboarding changes preferences). */
  reloadMe(): Promise<void>;
  retry(): void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

type Props = {
  children: ReactNode;
  /** Injected in tests; defaults to SecureStore and the real API. */
  tokenStore?: TokenStore & { load(): Promise<Tokens | null> };
  fetchImpl?: typeof fetch;
};

export function AuthProvider({ children, tokenStore, fetchImpl }: Props) {
  const queryClient = useQueryClient();
  const [session, dispatch] = useReducer(sessionReducer, initialSession);
  const sessionRef = useRef(session);
  useEffect(() => {
    sessionRef.current = session;
  }, [session]);

  const store = useMemo(() => tokenStore ?? createSecureTokenStore(), [tokenStore]);
  const client = useMemo(
    () =>
      new ApiClient({
        baseUrl: API_URL,
        appVersion: APP_VERSION,
        platform: PLATFORM,
        tokenStore: store,
        fetchImpl,
      }),
    [store, fetchImpl],
  );
  useEffect(() => {
    client.setSessionExpiredHandler(() => {
      const current = sessionRef.current;
      const wasGuest = current.status === "signedIn" && current.me.user.is_guest;
      queryClient.clear();
      dispatch({
        type: "signedOut",
        notice: wasGuest ? strings.session.guestExpired : strings.session.expired,
      });
    });
  }, [client, queryClient]);
  const api = useMemo(() => createEndpoints(client), [client]);

  const restore = useCallback(async () => {
    const tokens = await store.load();
    if (!tokens) {
      dispatch({ type: "signedOut" });
      return;
    }
    try {
      dispatch({ type: "signedIn", me: await api.me.get() });
    } catch (error) {
      if (error instanceof ApiError && error.code === NETWORK_ERROR) {
        dispatch({ type: "unavailable" });
      } else if (sessionRef.current.status !== "signedOut") {
        await store.set(null);
        dispatch({ type: "signedOut", notice: strings.session.expired });
      }
    }
  }, [api, store]);

  useEffect(() => {
    void restore();
  }, [restore]);

  const enter = useCallback(
    async (result: AuthOut) => {
      await store.set(result.tokens);
      queryClient.clear();
      dispatch({ type: "signedIn", me: await api.me.get() });
    },
    [api, queryClient, store],
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      session,
      api,
      startAsGuest: async () => enter(await api.auth.createGuest(deviceTimezone())),
      login: async (email, password) => enter(await api.auth.login(email, password)),
      upgrade: async (email, password, displayName) =>
        enter(await api.auth.upgrade(email, password, displayName)),
      logout: async () => {
        const tokens = store.get();
        if (tokens) await api.auth.logout(tokens.refresh_token).catch(() => undefined);
        await store.set(null);
        queryClient.clear();
        dispatch({ type: "signedOut" });
      },
      changePassword: async (currentPassword, newPassword) => {
        const result = await api.me.changePassword(currentPassword, newPassword);
        await store.set(result.tokens);
      },
      deleteAccount: async (password) => {
        await api.me.deleteAccount(password === null ? { confirm: "DELETE" } : { password });
        await store.set(null);
        await AsyncStorage.clear().catch(() => undefined);
        queryClient.clear();
        dispatch({ type: "signedOut" });
      },
      reloadMe: async () => {
        const me: MeOut = await api.me.get();
        dispatch({ type: "meUpdated", me });
      },
      retry: () => {
        dispatch({ type: "retrying" });
        void restore();
      },
    }),
    [api, enter, queryClient, restore, session, store],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside AuthProvider");
  return value;
}
