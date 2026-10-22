import { router } from "expo-router";
import type { ReactNode } from "react";
import { Pressable, StyleSheet, View } from "react-native";

import { strings } from "@/i18n/en";

import { Text } from "./Text";
import { spacing, touchTarget } from "./tokens";

/** Back link + page title for pushed screens, with an optional trailing action. */
export function BackHeader({ title, trailing }: { title: string; trailing?: ReactNode }) {
  return (
    <View style={styles.wrap}>
      <View style={styles.row}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={strings.settings.back}
          onPress={() => router.back()}
          style={styles.back}
        >
          <Text variant="label" tone="accent">
            ‹ {strings.settings.back}
          </Text>
        </Pressable>
        {trailing}
      </View>
      <Text variant="title" accessibilityRole="header">
        {title}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: spacing.sm },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  back: { minHeight: touchTarget, justifyContent: "center" },
});
