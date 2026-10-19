import { useQuery } from "@tanstack/react-query";
import { router, Tabs } from "expo-router";
import { useEffect } from "react";

import { useAuth } from "@/features/auth/AuthProvider";
import { takeLandingLesson } from "@/features/onboarding/landing";
import { dueCountLabel } from "@/features/reviews/recall";
import { strings } from "@/i18n/en";
import { useTheme } from "@/ui/theme";
import { fonts } from "@/ui/tokens";

/** Exactly three tabs (docs/spec/02 §2.1). Profile is reached from the Discover header. */
export default function TabsLayout() {
  const { colors } = useTheme();
  const { api } = useAuth();
  const reviews = useQuery({ queryKey: ["reviews", "summary"], queryFn: api.reviews.summary });
  const due = reviews.data?.due_count ?? 0;

  useEffect(() => {
    const slug = takeLandingLesson();
    if (slug) router.push({ pathname: "/lesson/[slug]", params: { slug } });
  }, []);

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
      <Tabs.Screen
        name="recall"
        options={{
          title: strings.tabs.recall,
          tabBarBadge: due > 0 ? dueCountLabel(due) : undefined,
          tabBarAccessibilityLabel:
            due > 0
              ? `${strings.tabs.recall}, ${strings.recall.dueCount(dueCountLabel(due))}`
              : undefined,
        }}
      />
    </Tabs>
  );
}
