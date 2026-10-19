import { Text as RNText, type TextProps as RNTextProps } from "react-native";

import { useTheme } from "./theme";
import { maxFontScale, type TextVariant, typography } from "./tokens";

export type TextProps = RNTextProps & {
  variant?: TextVariant;
  tone?: "default" | "muted" | "accent" | "success" | "danger";
};

export function Text({ variant = "body", tone = "default", style, ...rest }: TextProps) {
  const { colors } = useTheme();
  const color = {
    default: colors.text,
    muted: colors.textMuted,
    accent: colors.accent,
    success: colors.success,
    danger: colors.danger,
  }[tone];
  return (
    <RNText
      maxFontSizeMultiplier={maxFontScale[variant]}
      style={[typography[variant], { color }, style]}
      {...rest}
    />
  );
}
