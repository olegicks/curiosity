/** One typed function per endpoint the app uses so far. Paths match docs/spec/05. */
import type { ApiClient } from "./client";
import type {
  AnswerResponse,
  AttemptResponse,
  AuthOut,
  CompletionResponse,
  DiscoverOut,
  LessonDetailOut,
  LessonPage,
  MeOut,
  Preferences,
  PreferencesPatch,
  SubjectsOut,
} from "./types";

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
      lessons: () => client.get<LessonPage>("/v1/lessons?limit=100"),
      lesson: (slug: string) =>
        client.get<LessonDetailOut>(`/v1/lessons/${encodeURIComponent(slug)}`),
    },
    attempts: {
      start: (slug: string, restart = false) =>
        client.post<AttemptResponse>(`/v1/lessons/${encodeURIComponent(slug)}/attempts`, {
          restart,
        }),
      answer: (attemptId: string, questionId: string, optionIds: string[]) =>
        client.post<AnswerResponse>(`/v1/attempts/${attemptId}/answers`, {
          question_id: questionId,
          selected_option_ids: optionIds,
        }),
      complete: (attemptId: string) =>
        client.post<CompletionResponse>(`/v1/attempts/${attemptId}/complete`),
      rate: (attemptId: string, rating: "clear" | "unclear") =>
        client.post<void>(`/v1/attempts/${attemptId}/rating`, { rating }),
    },
    discover: {
      get: () => client.get<DiscoverOut>("/v1/discover"),
    },
  };
}

export type Endpoints = ReturnType<typeof createEndpoints>;
