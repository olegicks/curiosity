/**
 * Where to go right after onboarding (FR-ONB-4: the first recommended lesson's intro).
 * Onboarding records the target; the app layout opens it once, after the route
 * guard has switched to the app group.
 */
let pending: string | null = null;

export function setLandingLesson(slug: string | null): void {
  pending = slug;
}

export function takeLandingLesson(): string | null {
  const slug = pending;
  pending = null;
  return slug;
}
