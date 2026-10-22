import { type Href, router } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";

import { strings } from "@/i18n/en";
import { BackHeader } from "@/ui/BackHeader";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { radius, spacing, touchTarget } from "@/ui/tokens";

const SECTIONS: { key: keyof typeof strings.settings.sections; href: Href }[] = [
  { key: "account", href: "/settings/account" },
  { key: "learning", href: "/settings/learning" },
  { key: "appearance", href: "/settings/appearance" },
  { key: "privacy", href: "/settings/privacy" },
  { key: "about", href: "/settings/about" },
];

/** Settings (docs/spec/02 §2.13). */
export default function SettingsScreen() {
  const { colors } = useTheme();
  return (
    <Screen>
      <BackHeader title={strings.settings.title} />
      <View style={[styles.list, { borderColor: colors.border, backgroundColor: colors.surface }]}>
        {SECTIONS.map(({ key, href }, i) => (
          <Pressable
            key={key}
            accessibilityRole="button"
            accessibilityLabel={strings.settings.sections[key]}
            onPress={() => router.push(href)}
            style={({ pressed }) => [
              styles.row,
              i > 0 && { borderTopWidth: 1, borderTopColor: colors.border },
              pressed && { opacity: 0.8 },
            ]}
          >
            <Text variant="body">{strings.settings.sections[key]}</Text>
            <Text variant="heading" tone="muted" importantForAccessibility="no">
              ›
            </Text>
          </Pressable>
        ))}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  list: { borderWidth: 1, borderRadius: radius.md, overflow: "hidden" },
  row: {
    minHeight: touchTarget + 8,
    paddingHorizontal: spacing.lg,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
});
