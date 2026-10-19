/**
 * Design tokens (docs/spec/10-design-system.md §10.2).
 * Text colours meet WCAG AA (≥ 4.5:1) on `bg` and `surface` in both themes.
 */

export type ColorScheme = "light" | "dark";

export type Palette = {
  bg: string;
  surface: string;
  surfaceMuted: string;
  border: string;
  text: string;
  textMuted: string;
  accent: string;
  onAccent: string;
  success: string;
  danger: string;
  ai: string;
  successBg: string;
  dangerBg: string;
  aiBg: string;
};

export const palettes: Record<ColorScheme, Palette> = {
  light: {
    bg: "#FAF7F2",
    surface: "#FFFFFF",
    surfaceMuted: "#F1ECE3",
    border: "#E3DDD2",
    text: "#1F1D1A",
    textMuted: "#5F5A52",
    accent: "#3346A8",
    onAccent: "#FFFFFF",
    success: "#24704A",
    danger: "#B23A2A",
    ai: "#7A4BA8",
    successBg: "#E9F1EC",
    dangerBg: "#F7EBE9",
    aiBg: "#F2EDF6",
  },
  dark: {
    bg: "#14130F",
    surface: "#1E1C18",
    surfaceMuted: "#2A2721",
    border: "#38342C",
    text: "#EDE9E1",
    textMuted: "#A8A196",
    accent: "#9AA8F2",
    onAccent: "#14130F",
    success: "#6CC596",
    danger: "#F08A78",
    ai: "#C6A2EC",
    successBg: "#2A3A30",
    dangerBg: "#3D2A25",
    aiBg: "#352D3F",
  },
};

export const fonts = {
  serif: "SourceSerif4_400Regular",
  serifSemibold: "SourceSerif4_600SemiBold",
  sans: "Inter_400Regular",
  sansMedium: "Inter_500Medium",
  sansSemibold: "Inter_600SemiBold",
} as const;

export type TextVariant =
  "display" | "title" | "heading" | "reading" | "body" | "label" | "caption";

export const typography: Record<
  TextVariant,
  { fontFamily: string; fontSize: number; lineHeight: number }
> = {
  display: { fontFamily: fonts.serifSemibold, fontSize: 30, lineHeight: 36 },
  title: { fontFamily: fonts.serifSemibold, fontSize: 24, lineHeight: 30 },
  heading: { fontFamily: fonts.sansSemibold, fontSize: 18, lineHeight: 24 },
  reading: { fontFamily: fonts.serif, fontSize: 18, lineHeight: 28 },
  body: { fontFamily: fonts.sans, fontSize: 16, lineHeight: 24 },
  label: { fontFamily: fonts.sansMedium, fontSize: 14, lineHeight: 20 },
  caption: { fontFamily: fonts.sans, fontSize: 13, lineHeight: 18 },
};

/** Reading and body text must scale to ≥ 200%; chrome is capped so layouts hold. */
export const maxFontScale: Record<TextVariant, number | undefined> = {
  display: undefined,
  title: undefined,
  heading: 2,
  reading: undefined,
  body: undefined,
  label: 1.5,
  caption: 1.5,
};

export const spacing = { xs: 4, sm: 8, md: 12, lg: 16, xl: 24, "2xl": 32, "3xl": 48 } as const;
export const radius = { sm: 6, md: 12, lg: 20, full: 999 } as const;
export const motion = { fast: 120, base: 200, slow: 320 } as const;
export const touchTarget = 44;
export const readingMaxWidth = 600;
