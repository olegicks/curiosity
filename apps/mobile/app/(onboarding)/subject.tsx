import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { StyleSheet, View } from "react-native";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { SubjectGrid } from "@/features/subjects/SubjectGrid";
import { useSubject } from "@/features/subjects/SubjectProvider";
import { activeSubject } from "@/features/subjects/subjects";
import { strings } from "@/i18n/en";
import { Button } from "@/ui/Button";
import { Mascot } from "@/ui/Mascot";
import { Screen } from "@/ui/Screen";
import { ErrorState, LoadingBlocks } from "@/ui/States";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { edge, radius, spacing } from "@/ui/tokens";

/** Step 1 of onboarding (D-17): pick the subject whose roadmap to start. */
export default function SubjectScreen() {
  const { api } = useAuth();
  const { colors } = useTheme();
  const { stored, choose } = useSubject();
  const subjects = useQuery({ queryKey: ["subjects"], queryFn: api.content.subjects });
  const items = subjects.data?.items ?? [];
  const current = activeSubject(items, stored);

  return (
    <Screen
      footer={
        current ? (
          <Button
            label={strings.subjects.start(current.title)}
            onPress={() => {
              choose(current.slug);
              router.push("/goal");
            }}
          />
        ) : null
      }
    >
      <View style={styles.hello}>
        <Mascot size={72} />
        <View
          style={[styles.bubble, { backgroundColor: colors.surface, borderColor: colors.border }]}
        >
          <Text variant="heading" accessibilityRole="header">
            {strings.subjects.greeting}
          </Text>
        </View>
      </View>
      {subjects.isPending ? <LoadingBlocks count={4} /> : null}
      {subjects.isError ? (
        <ErrorState
          message={errorMessage(subjects.error)}
          onRetry={() => void subjects.refetch()}
        />
      ) : null}
      {items.length > 0 ? (
        <SubjectGrid subjects={items} selected={current?.slug ?? null} onSelect={choose} />
      ) : null}
      <Text tone="muted" style={styles.center}>
        {strings.subjects.hint}
      </Text>
    </Screen>
  );
}

const styles = StyleSheet.create({
  hello: { flexDirection: "row", alignItems: "flex-end", gap: spacing.md },
  bubble: {
    flex: 1,
    borderWidth: 2,
    borderBottomWidth: edge,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  center: { textAlign: "center" },
});
