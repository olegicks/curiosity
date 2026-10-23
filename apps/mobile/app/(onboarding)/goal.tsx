import { useState } from "react";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { DAILY_GOALS, type DailyGoal } from "@/features/onboarding/interests";
import { strings } from "@/i18n/en";
import { Banner } from "@/ui/Banner";
import { Button } from "@/ui/Button";
import { ChoiceCard } from "@/ui/ChoiceCard";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

/** Step 2 of onboarding (FR-ONB-3). Finishing or skipping marks onboarding complete. */
export default function GoalScreen() {
  const { api, session, reloadMe } = useAuth();
  const current = session.status === "signedIn" ? session.me.preferences.daily_xp_goal : 20;
  const [goal, setGoal] = useState<DailyGoal>(current);
  const [busy, setBusy] = useState<"continue" | "skip" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const finish = async (withGoal: boolean) => {
    setBusy(withGoal ? "continue" : "skip");
    setError(null);
    try {
      await api.me.updatePreferences(
        withGoal
          ? { daily_xp_goal: goal, onboarding_completed: true }
          : { onboarding_completed: true },
      );
      // The route guard then opens the path, where the first-run tour starts (D-17).
      await reloadMe();
    } catch (e) {
      setError(errorMessage(e));
      setBusy(null);
    }
  };

  return (
    <Screen
      footer={
        <>
          <Button
            label={strings.onboarding.continue}
            onPress={() => finish(true)}
            loading={busy === "continue"}
            disabled={busy !== null}
          />
          <Button
            label={strings.onboarding.skip}
            variant="ghost"
            onPress={() => finish(false)}
            disabled={busy !== null}
          />
        </>
      }
    >
      <Text variant="title" accessibilityRole="header">
        {strings.onboarding.goalTitle}
      </Text>
      <Text tone="muted">{strings.onboarding.goalBody}</Text>
      {error ? <Banner message={error} tone="error" /> : null}
      {DAILY_GOALS.map((value) => (
        <ChoiceCard
          key={value}
          role="radio"
          title={strings.onboarding.goals[value].title}
          description={strings.onboarding.goals[value].description}
          selected={goal === value}
          onPress={() => setGoal(value)}
        />
      ))}
    </Screen>
  );
}
