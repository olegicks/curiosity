import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { accuracyLabel, stageCounts } from "@/features/profile/profile";
import { strings } from "@/i18n/en";
import { BackHeader } from "@/ui/BackHeader";
import { Button } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { MasteryDots } from "@/ui/MasteryDots";
import { Screen } from "@/ui/Screen";
import { StatTile } from "@/ui/StatTile";
import { ErrorState, LoadingBlocks } from "@/ui/States";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { radius, spacing, touchTarget } from "@/ui/tokens";

/** Profile: identity, simple stats and achievements. No charts (docs/spec/02 §2.12). */
export default function ProfileScreen() {
  const { session, api } = useAuth();
  const { colors } = useTheme();
  const progress = useQuery({ queryKey: ["progress"], queryFn: api.progress.get });
  const achievements = useQuery({
    queryKey: ["achievements"],
    queryFn: api.progress.achievements,
  });
  if (session.status !== "signedIn") return null;
  const { user } = session.me;

  return (
    <Screen
      refreshing={progress.isRefetching}
      onRefresh={() => {
        void progress.refetch();
        void achievements.refetch();
      }}
    >
      <BackHeader
        title={strings.profile.title}
        trailing={
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={strings.profile.settings}
            onPress={() => router.push("/settings")}
            style={styles.link}
          >
            <Text variant="label" tone="accent">
              {strings.profile.settings}
            </Text>
          </Pressable>
        }
      />
      <View style={styles.identity}>
        <Text variant="heading">{user.display_name ?? strings.profile.guest}</Text>
        {user.email ? <Text tone="muted">{user.email}</Text> : null}
      </View>

      {user.is_guest ? (
        <Card tone="muted">
          <Text variant="heading">{strings.profile.saveProgressTitle}</Text>
          <Text tone="muted">{strings.profile.saveProgressBody}</Text>
          <Button
            label={strings.profile.createAccount}
            onPress={() => router.push("/account/create")}
          />
        </Card>
      ) : null}

      {progress.isPending ? <LoadingBlocks count={3} /> : null}
      {progress.isError ? (
        <ErrorState
          message={errorMessage(progress.error)}
          onRetry={() => void progress.refetch()}
        />
      ) : null}
      {progress.data ? (
        <>
          <View style={styles.tiles}>
            <StatTile label={strings.profile.totalXp} value={String(progress.data.xp.total)} />
            <StatTile
              label={strings.profile.currentStreak}
              value={strings.profile.days(progress.data.streak.current)}
            />
            <StatTile
              label={strings.profile.longestStreak}
              value={strings.profile.days(progress.data.streak.longest)}
            />
          </View>
          <Text tone="muted">
            {strings.profile.freezes(progress.data.streak.freezes_available)}
          </Text>

          <View style={styles.section}>
            <Text variant="heading" accessibilityRole="header">
              {strings.profile.concepts}
            </Text>
            {stageCounts(progress.data).map(({ stage, label, count }) => (
              <View
                key={stage}
                accessible
                accessibilityLabel={`${label}: ${count}`}
                style={styles.stageRow}
              >
                <MasteryDots stage={stage} />
                <Text style={styles.flex}>{label}</Text>
                <Text variant="label">{count}</Text>
              </View>
            ))}
            <Text tone="muted">{accuracyLabel(progress.data)}</Text>
          </View>
        </>
      ) : null}

      {achievements.data ? (
        <View style={styles.section}>
          <View style={styles.sectionHeader}>
            <Text variant="heading" accessibilityRole="header">
              {strings.profile.achievements}
            </Text>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={`${strings.profile.seeAll} ${strings.profile.achievements}`}
              onPress={() => router.push("/achievements")}
              style={styles.link}
            >
              <Text variant="label" tone="accent">
                {strings.profile.seeAll}
              </Text>
            </Pressable>
          </View>
          <View style={styles.badges}>
            {achievements.data.items.map((a) => (
              <View
                key={a.code}
                accessible
                accessibilityLabel={`${a.title}, ${a.earned_at ? "earned" : strings.profile.locked}`}
                style={[
                  styles.badge,
                  {
                    borderColor: a.earned_at ? colors.accent : colors.border,
                    backgroundColor: a.earned_at ? colors.surface : colors.surfaceMuted,
                  },
                ]}
              >
                <Text variant="label" tone={a.earned_at ? "default" : "muted"} numberOfLines={2}>
                  {a.earned_at ? "★ " : ""}
                  {a.title}
                </Text>
              </View>
            ))}
          </View>
        </View>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  identity: { gap: spacing.xs },
  tiles: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  section: { gap: spacing.sm },
  sectionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  stageRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, minHeight: 32 },
  flex: { flex: 1 },
  badges: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  badge: {
    flexBasis: "47%",
    flexGrow: 1,
    minHeight: touchTarget,
    borderWidth: 1,
    borderRadius: radius.md,
    padding: spacing.sm,
    justifyContent: "center",
  },
  link: { minHeight: touchTarget, justifyContent: "center" },
});
