/** One typed function per endpoint the app uses so far. Paths match docs/spec/05. */
import type { ApiClient } from "./client";
import type {
  AchievementsOut,
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
  ProgressOut,
  TokensResponse,
  UserResponse,
  ConceptPage,
  ReviewAnswerResponse,
  ReviewSessionResponse,
  ReviewSummary,
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
      updateDisplayName: (displayName: string | null) =>
        client.patch<UserResponse>("/v1/me", { display_name: displayName }),
      changePassword: (currentPassword: string, newPassword: string) =>
        client.post<TokensResponse>("/v1/me/password", {
          current_password: currentPassword,
          new_password: newPassword,
        }),
      /** Full accounts confirm with their password; guests type DELETE. */
      deleteAccount: (confirmation: { password: string } | { confirm: "DELETE" }) =>
        client.delete<void>("/v1/me", confirmation),
      exportData: () => client.get<Record<string, unknown>>("/v1/me/export"),
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
    progress: {
      get: () => client.get<ProgressOut>("/v1/progress"),
      achievements: () => client.get<AchievementsOut>("/v1/achievements"),
    },
    discover: {
      get: () => client.get<DiscoverOut>("/v1/discover"),
    },
    reviews: {
      summary: () => client.get<ReviewSummary>("/v1/reviews/summary"),
      concepts: () => client.get<ConceptPage>("/v1/reviews/concepts?limit=100"),
      startSession: () => client.post<ReviewSessionResponse>("/v1/review-sessions"),
      answer: (sessionId: string, itemId: string, optionIds: string[], guessed: boolean) =>
        client.post<ReviewAnswerResponse>(
          `/v1/review-sessions/${sessionId}/items/${itemId}/answer`,
          { selected_option_ids: optionIds, guessed },
        ),
      endSession: (sessionId: string) =>
        client.post<ReviewSessionResponse>(`/v1/review-sessions/${sessionId}/end`),
    },
  };
}

export type Endpoints = ReturnType<typeof createEndpoints>;
