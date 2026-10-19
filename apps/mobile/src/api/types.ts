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
