import { useQuery } from "@tanstack/react-query";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { earnedDate } from "@/features/profile/profile";
import { strings } from "@/i18n/en";
import { BackHeader } from "@/ui/BackHeader";
import { Card } from "@/ui/Card";
import { Screen } from "@/ui/Screen";
import { ErrorState, LoadingBlocks } from "@/ui/States";
import { Text } from "@/ui/Text";

/** All milestone achievements, earned first (docs/spec/07 §7.6). */
export default function AchievementsScreen() {
  const { api } = useAuth();
  const achievements = useQuery({
    queryKey: ["achievements"],
    queryFn: api.progress.achievements,
  });
  const items = [...(achievements.data?.items ?? [])].sort(
    (a, b) => Number(Boolean(b.earned_at)) - Number(Boolean(a.earned_at)),
  );

  return (
    <Screen>
      <BackHeader title={strings.profile.achievements} />
      {achievements.isPending ? <LoadingBlocks count={4} /> : null}
      {achievements.isError ? (
        <ErrorState
          message={errorMessage(achievements.error)}
          onRetry={() => void achievements.refetch()}
        />
      ) : null}
      {items.map((a) => (
        <Card key={a.code} tone={a.earned_at ? "success" : "muted"}>
          <Text variant="heading">
            {a.earned_at ? "★ " : ""}
            {a.title}
          </Text>
          <Text>{a.description}</Text>
          <Text variant="caption" tone="muted">
            {a.earned_at ? strings.profile.earned(earnedDate(a.earned_at)) : strings.profile.locked}
          </Text>
        </Card>
      ))}
    </Screen>
  );
}
