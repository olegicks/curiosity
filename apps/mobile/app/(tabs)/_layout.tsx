import { Tabs } from "expo-router";

import { strings } from "@/i18n/en";
import { useTheme } from "@/ui/theme";
import { fonts } from "@/ui/tokens";

/** Exactly three tabs (docs/spec/02 §2.1). Profile is reached from the Discover header. */
export default function TabsLayout() {
  const { colors } = useTheme();
  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarStyle: { backgroundColor: colors.surface, borderTopColor: colors.border },
        tabBarLabelStyle: { fontFamily: fonts.sansMedium },
        tabBarIconStyle: { display: "none" }, // icons arrive with the design pass
      }}
    >
      <Tabs.Screen name="index" options={{ title: strings.tabs.discover }} />
      <Tabs.Screen name="learn" options={{ title: strings.tabs.learn }} />
      <Tabs.Screen name="recall" options={{ title: strings.tabs.recall }} />
    </Tabs>
  );
}
