import { router } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";

import { useAuth } from "@/features/auth/AuthProvider";
import { strings } from "@/i18n/en";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { radius, touchTarget } from "@/ui/tokens";

/** Discover (placeholder until the Discover client slice). */
export default function DiscoverScreen() {
  const { session } = useAuth();
  const { colors } = useTheme();
  const name = session.status === "signedIn" ? session.me.user.display_name : null;
  const initial = (name ?? "?").slice(0, 1).toUpperCase();

  return (
    <Screen>
      <View style={styles.header}>
        <Text variant="title" accessibilityRole="header">
          {name ? `Hello, ${name}` : strings.tabs.discover}
        </Text>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={strings.profile.title}
          onPress={() => router.push("/profile")}
          style={[styles.avatar, { backgroundColor: colors.surfaceMuted }]}
        >
          <Text variant="label">{initial}</Text>
        </Pressable>
      </View>
      <Text tone="muted">{strings.placeholder}</Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  avatar: {
    width: touchTarget,
    height: touchTarget,
    borderRadius: radius.full,
    alignItems: "center",
    justifyContent: "center",
  },
});
