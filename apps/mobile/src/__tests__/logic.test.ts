import { ApiError, errorMessage, NETWORK_ERROR } from "@/api/errors";
import { homeFor, initialSession, routeFor, sessionReducer } from "@/features/auth/session";
import { topicsForSelection } from "@/features/onboarding/interests";
import { strings } from "@/i18n/en";
import { me } from "@/test/fakeApi";
import { resolveScheme } from "@/ui/theme";
import { palettes, unitColors } from "@/ui/tokens";

describe("errorMessage", () => {
  test("maps known codes to friendly copy and never shows raw messages", () => {
    expect(errorMessage(new ApiError(401, "INVALID_CREDENTIALS", "raw"))).toBe(
      strings.errors.invalidCredentials,
    );
    expect(errorMessage(new ApiError(0, NETWORK_ERROR, "raw"))).toBe(strings.errors.offline);
    expect(errorMessage(new ApiError(500, "INTERNAL_ERROR", "stack trace"))).toBe(
      strings.errors.generic,
    );
    expect(errorMessage(new Error("boom"))).toBe(strings.errors.generic);
  });

  test("explains weak passwords by issue", () => {
    const tooCommon = new ApiError(422, "WEAK_PASSWORD", "x", [{ issue: "too_common" }]);
    expect(errorMessage(tooCommon)).toBe(strings.errors.passwordTooCommon);
    expect(errorMessage(new ApiError(422, "WEAK_PASSWORD", "x", []))).toBe(
      strings.errors.weakPassword,
    );
  });
});

describe("session", () => {
  test("routes follow the session state", () => {
    expect(routeFor(initialSession)).toBe("loading");
    const out = sessionReducer(initialSession, { type: "signedOut" });
    expect(routeFor(out)).toBe("auth");
    const guest = sessionReducer(out, { type: "signedIn", me: me() });
    expect(routeFor(guest)).toBe("onboarding");
    const done = sessionReducer(guest, {
      type: "meUpdated",
      me: me({ onboarding_completed: true }),
    });
    expect(routeFor(done)).toBe("app");
    expect(routeFor(sessionReducer(done, { type: "unavailable" }))).toBe("unavailable");
  });

  test("each group has a start screen for unreachable paths", () => {
    expect(homeFor("auth")).toBe("/welcome");
    expect(homeFor("onboarding")).toBe("/interests");
    expect(homeFor("app")).toBe("/");
    expect(homeFor("loading")).toBeNull();
  });

  test("meUpdated is ignored when signed out", () => {
    const out = sessionReducer(initialSession, { type: "signedOut", notice: "bye" });
    expect(sessionReducer(out, { type: "meUpdated", me: me() })).toBe(out);
  });
});

describe("interests", () => {
  test("map cards to published topics only", () => {
    const published = new Set(["judgment", "social"]);
    expect(topicsForSelection(new Set(["thinking", "decisions", "people"]), published)).toEqual([
      "judgment",
      "social",
    ]);
    expect(topicsForSelection(new Set(), published)).toEqual([]);
  });
});

describe("theme", () => {
  test("resolves system preference", () => {
    expect(resolveScheme("system", "dark")).toBe("dark");
    expect(resolveScheme("system", null)).toBe("light");
    expect(resolveScheme("light", "dark")).toBe("light");
  });

  // WCAG 2.x relative luminance contrast
  const luminance = (hex: string) => {
    const [r, g, b] = [1, 3, 5].map((i) => {
      const c = parseInt(hex.slice(i, i + 2), 16) / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    }) as [number, number, number];
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const contrast = (a: string, b: string) => {
    const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x) as [number, number];
    return (hi + 0.05) / (lo + 0.05);
  };

  test.each(["light", "dark"] as const)("%s text colours meet AA on backgrounds", (scheme) => {
    const p = palettes[scheme];
    for (const background of [p.bg, p.surface]) {
      for (const fg of [p.text, p.textMuted, p.accent, p.success, p.danger, p.ai]) {
        expect(contrast(fg, background)).toBeGreaterThanOrEqual(4.5);
      }
    }
    expect(contrast(p.onAccent, p.accent)).toBeGreaterThanOrEqual(4.5);
    for (const tint of [p.successBg, p.dangerBg, p.aiBg, p.accentBg]) {
      expect(contrast(p.text, tint)).toBeGreaterThanOrEqual(4.5);
    }
  });

  test("white labels on unit and button fills meet AA", () => {
    const fills = [
      ...unitColors.map((u) => u.fill),
      palettes.light.accent,
      palettes.light.success,
      palettes.light.danger,
    ];
    for (const fill of fills) expect(contrast("#FFFFFF", fill)).toBeGreaterThanOrEqual(4.5);
    for (const u of unitColors) expect(contrast(u.fill, u.tint)).toBeGreaterThanOrEqual(4.5);
  });
});
