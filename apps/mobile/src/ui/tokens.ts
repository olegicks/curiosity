/**
 * Design tokens. Playful direction (D-16, docs/spec/15); accessibility rules of
 * docs/spec/10 still hold: text colours meet WCAG AA (≥ 4.5:1) on `bg` and `surface`.
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
  /** Darker bottom edge of accent buttons and nodes. */
  accentEdge: string;
  accentBg: string;
  onAccent: string;
  success: string;
  successEdge: string;
  danger: string;
  dangerEdge: string;
  ai: string;
  successBg: string;
  dangerBg: string;
  aiBg: string;
  /** Streak flame and XP bolt (icons only, never text). */
  streak: string;
  xp: string;
  /** Upcoming path nodes and pressed-out surfaces. */
  idle: string;
  idleEdge: string;
  idleIcon: string;
};

export const palettes: Record<ColorScheme, Palette> = {
  light: {
    bg: "#F7F6FC",
    surface: "#FFFFFF",
    surfaceMuted: "#EFEDF8",
    border: "#E2DFF0",
    text: "#1E1B2E",
    textMuted: "#5E5A72",
    accent: "#6340E0",
    accentEdge: "#4527B5",
    accentBg: "#EEE9FD",
    onAccent: "#FFFFFF",
    success: "#1A7F45",
    successEdge: "#11592F",
    danger: "#C92A39",
    dangerEdge: "#931D28",
    ai: "#7A4BA8",
    successBg: "#E4F3EA",
    dangerBg: "#FBE7E9",
    aiBg: "#F2EDF6",
    streak: "#F76707",
    xp: "#F5A300",
    idle: "#E5E2F0",
    idleEdge: "#CBC6DE",
    idleIcon: "#8A85A0",
  },
  dark: {
    bg: "#14121C",
    surface: "#1E1B29",
    surfaceMuted: "#2A2638",
    border: "#383349",
    text: "#EEEAF7",
    textMuted: "#ABA5BF",
    accent: "#A893FF",
    accentEdge: "#7559E6",
    accentBg: "#2B2550",
    onAccent: "#14121C",
    success: "#5BD38A",
    successEdge: "#2F9C5B",
    danger: "#FF8A8F",
    dangerEdge: "#D9575E",
    ai: "#C6A2EC",
    successBg: "#1F3328",
    dangerBg: "#3A2226",
    aiBg: "#352D3F",
    streak: "#FF922B",
    xp: "#FFC233",
    idle: "#2F2B3D",
    idleEdge: "#221F2E",
    idleIcon: "#8B85A1",
  },
};

/** One colour per path unit, cycled in curated topic order. White text on `fill` is AA. */
export type UnitColor = { fill: string; edge: string; tint: string };

export const unitColors: UnitColor[] = [
  { fill: "#6340E0", edge: "#4527B5", tint: "#EEE9FD" },
  { fill: "#0F7C6C", edge: "#09584D", tint: "#E6F6F2" },
  { fill: "#C2410C", edge: "#8E2F08", tint: "#FCEDE5" },
  { fill: "#1F5FD1", edge: "#16449A", tint: "#E6EEFB" },
];

export function unitColor(index: number): UnitColor {
  return unitColors[index % unitColors.length] as UnitColor;
}

export const fonts = {
  sans: "Inter_400Regular",
  sansMedium: "Inter_500Medium",
  sansSemibold: "Inter_600SemiBold",
  sansBold: "Inter_700Bold",
  sansHeavy: "Inter_800ExtraBold",
} as const;

export type TextVariant =
  "display" | "title" | "heading" | "reading" | "body" | "label" | "caption";

export const typography: Record<
  TextVariant,
  { fontFamily: string; fontSize: number; lineHeight: number }
> = {
  display: { fontFamily: fonts.sansHeavy, fontSize: 30, lineHeight: 36 },
  title: { fontFamily: fonts.sansBold, fontSize: 24, lineHeight: 30 },
  heading: { fontFamily: fonts.sansBold, fontSize: 18, lineHeight: 24 },
  reading: { fontFamily: fonts.sans, fontSize: 17, lineHeight: 27 },
  body: { fontFamily: fonts.sans, fontSize: 16, lineHeight: 24 },
  label: { fontFamily: fonts.sansBold, fontSize: 14, lineHeight: 20 },
  caption: { fontFamily: fonts.sansMedium, fontSize: 13, lineHeight: 18 },
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
export const radius = { sm: 8, md: 16, lg: 24, full: 999 } as const;
/** Height of the darker bottom edge on chunky buttons, options and nodes. */
export const edge = 4;
export const motion = { fast: 120, base: 200, slow: 320 } as const;
export const touchTarget = 44;
export const readingMaxWidth = 600;
