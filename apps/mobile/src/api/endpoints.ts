/** One typed function per endpoint the app uses so far. Paths match docs/spec/05. */
import type { ApiClient } from "./client";
import type { AuthOut, MeOut, Preferences, PreferencesPatch, SubjectsOut } from "./types";

export function createEndpoints(client: ApiClient) {
  return {
    auth: {
      createGuest: (timezone: string | null) =>
        client.post<AuthOut>("/v1/auth/guest", { timezone }, { auth: false }),
      login: (email: string, password: string) =>
        client.post<AuthOut>("/v1/auth/login", { email, password }, { auth: false }),
      upgrade: (email: string, password: string, displayName: string | null) =>
        client.post<AuthOut>("/v1/auth/upgrade", {
          email,
          password,
          display_name: displayName,
        }),
      logout: (refreshToken: string) =>
        client.post<void>("/v1/auth/logout", { refresh_token: refreshToken }),
    },
    me: {
      get: () => client.get<MeOut>("/v1/me"),
      updatePreferences: (patch: PreferencesPatch) =>
        client.patch<Preferences>("/v1/me/preferences", patch),
    },
    content: {
      subjects: () => client.get<SubjectsOut>("/v1/subjects"),
    },
  };
}

export type Endpoints = ReturnType<typeof createEndpoints>;
