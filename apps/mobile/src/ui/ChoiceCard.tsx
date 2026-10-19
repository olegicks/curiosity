import { Pressable, StyleSheet, View } from "react-native";

import { Text } from "./Text";
import { useTheme } from "./theme";
import { radius, spacing, touchTarget } from "./tokens";

type Props = {
  title: string;
  description?: string;
  selected: boolean;
  onPress: () => void;
  /** "checkbox" for multi-select lists, "radio" for single choice. */
  role?: "checkbox" | "radio";
};

/** A large selectable card. Selection is shown by border, icon and screen-reader state. */
export function ChoiceCard({ title, description, selected, onPress, role = "checkbox" }: Props) {
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole={role}
      accessibilityState={{ checked: selected }}
      accessibilityLabel={description ? `${title}. ${description}` : title}
      onPress={onPress}
      style={({ pressed }) => [
        styles.card,
        {
          backgroundColor: colors.surface,
          borderColor: selected ? colors.accent : colors.border,
          borderWidth: selected ? 2 : 1,
        },
        pressed && { opacity: 0.9 },
      ]}
    >
      <View style={styles.text}>
        <Text variant="heading">{title}</Text>
        {description ? (
          <Text variant="body" tone="muted">
            {description}
          </Text>
        ) : null}
      </View>
      <Text variant="heading" tone={selected ? "accent" : "muted"} importantForAccessibility="no">
        {selected ? "✓" : role === "radio" ? "○" : "□"}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    minHeight: touchTarget + 20,
    borderRadius: radius.md,
    padding: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
  },
  text: { flex: 1, gap: spacing.xs },
});
