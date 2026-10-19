import { strings } from "@/i18n/en";

import type { ErrorEnvelope } from "./types";

/** Client-side codes for failures that never reached the API. */
export const NETWORK_ERROR = "NETWORK_ERROR";
export const UNEXPECTED_RESPONSE = "UNEXPECTED_RESPONSE";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>[];
  readonly requestId: string | null;

  constructor(
    status: number,
    code: string,
    message: string,
    details: Record<string, unknown>[] = [],
    requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
  }

  static fromEnvelope(status: number, body: unknown): ApiError {
    if (isEnvelope(body)) {
      const { code, message, details, request_id } = body.error;
      return new ApiError(status, code, message, details, request_id);
    }
    return new ApiError(status, UNEXPECTED_RESPONSE, `HTTP ${status}`);
  }
}

function isEnvelope(body: unknown): body is ErrorEnvelope {
  if (typeof body !== "object" || body === null || !("error" in body)) return false;
  const error = (body as { error: unknown }).error;
  return typeof error === "object" && error !== null && "code" in error;
}

const WEAK_PASSWORD_ISSUES: Record<string, string> = {
  too_short: strings.errors.passwordTooShort,
  too_long: strings.errors.passwordTooLong,
  too_common: strings.errors.passwordTooCommon,
  same_as_email: strings.errors.passwordSameAsEmail,
};

/** User-facing copy for an error. Raw server messages are never shown (FR-GLB-3). */
export function errorMessage(error: unknown): string {
  if (!(error instanceof ApiError)) return strings.errors.generic;
  if (error.code === "WEAK_PASSWORD") {
    const issue = error.details[0]?.issue;
    return (
      (typeof issue === "string" && WEAK_PASSWORD_ISSUES[issue]) || strings.errors.weakPassword
    );
  }
  const known: Record<string, string> = {
    [NETWORK_ERROR]: strings.errors.offline,
    INVALID_CREDENTIALS: strings.errors.invalidCredentials,
    EMAIL_TAKEN: strings.errors.emailTaken,
    RATE_LIMITED: strings.errors.rateLimited,
    UPGRADE_REQUIRED: strings.errors.upgradeRequired,
    VALIDATION_ERROR: strings.errors.validation,
    SERVICE_UNAVAILABLE: strings.errors.unavailable,
  };
  return known[error.code] ?? strings.errors.generic;
}
