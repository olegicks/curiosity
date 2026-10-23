import { useQuery } from "@tanstack/react-query";
import { Tabs } from "expo-router";

import { useAuth } from "@/features/auth/AuthProvider";
import { dueCountLabel } from "@/features/reviews/recall";
import { strings } from "@/i18n/en";
import { Icon } from "@/ui/Icon";
import { useTheme } from "@/ui/theme";
import { fonts } from "@/ui/tokens";

/** Three tabs: Path, Recall, Profile (D-16, docs/spec/02 §2.1). */
export default function TabsLayout() {
  const { colors } = useTheme();
  const { api } = useAuth();
  const reviews = useQuery({ queryKey: ["reviews", "summary"], queryFn: api.reviews.summary });
  const due = reviews.data?.due_count ?? 0;

  return (
    <Tabs
      screenOptions={{
        headerShown: false,
        tabBarActiveTintColor: colors.accent,
        tabBarInactiveTintColor: colors.textMuted,
        tabBarStyle: {
          backgroundColor: colors.surface,
          borderTopColor: colors.border,
          borderTopWidth: 2,
        },
        tabBarLabelStyle: { fontFamily: fonts.sansBold },
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: strings.tabs.path,
          tabBarIcon: ({ color }) => <Icon name="map" color={String(color)} size={26} />,
        }}
      />
      <Tabs.Screen
        name="recall"
        options={{
          title: strings.tabs.recall,
          tabBarIcon: ({ color }) => <Icon name="bulb" color={String(color)} size={26} />,
          tabBarBadge: due > 0 ? dueCountLabel(due) : undefined,
          tabBarAccessibilityLabel:
            due > 0
              ? `${strings.tabs.recall}, ${strings.recall.dueCount(dueCountLabel(due))}`
              : undefined,
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: strings.tabs.profile,
          tabBarIcon: ({ color }) => <Icon name="person-circle" color={String(color)} size={26} />,
        }}
      />
    </Tabs>
  );
}
