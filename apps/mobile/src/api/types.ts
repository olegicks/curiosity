/** Friendly aliases for the generated OpenAPI types (src/api/schema.d.ts). */
import type { components } from "./schema";

type Schemas = components["schemas"];

export type Tokens = Schemas["TokensOut"];
export type AuthOut = Schemas["AuthOut"];
export type UserOut = Schemas["UserOut"];
export type MeOut = Schemas["MeOut"];
export type Preferences = Schemas["PreferencesOut"];
export type PreferencesPatch = Schemas["PreferencesPatchIn"];
export type SubjectsOut = Schemas["SubjectsOut"];
export type TokensResponse = Schemas["TokensResponse"];

/** The uniform error envelope (docs/spec/05 §5.1). */
export type ErrorEnvelope = {
  error: {
    code: string;
    message: string;
    details: Record<string, unknown>[];
    request_id: string | null;
  };
};

export type LessonSummary = Schemas["LessonSummary"];
export type LessonPage = Schemas["LessonPage"];
export type LessonDetailOut = Schemas["LessonDetailOut"];
export type LessonContent = Schemas["LessonContent"];
export type Step = LessonContent["steps"][number];
export type QuestionOut = Schemas["QuestionOut"];
export type SourceOut = Schemas["SourceOut"];
export type ProgressBrief = Schemas["ProgressBrief"];
export type AttemptResponse = Schemas["AttemptResponse"];
export type AnswerResult = Schemas["AnswerResult"];
export type AnswerResponse = Schemas["AnswerResponse"];
export type CompletionResponse = Schemas["CompletionResponse"];
export type XpAward = Schemas["XpAwardOut"];
export type Achievement = Schemas["AchievementOut"];
export type DiscoverOut = Schemas["DiscoverOut"];

export type ReviewSummary = Schemas["ReviewSummaryOut"];
export type ConceptPage = Schemas["ConceptPage"];
export type Concept = Schemas["ConceptOut"];
export type ReviewSessionResponse = Schemas["SessionResponse"];
export type ReviewSession = Schemas["SessionOut"];
export type ReviewItem = Schemas["SessionItemOut"];
export type ReviewAnswerResult = Schemas["ReviewAnswerResult"];
export type ReviewAnswerResponse = Schemas["ReviewAnswerResponse"];
export type ReviewSessionSummary = Schemas["SessionSummaryOut"];
