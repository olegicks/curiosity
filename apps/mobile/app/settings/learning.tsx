import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { StyleSheet, View } from "react-native";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import {
  DAILY_GOALS,
  type DailyGoal,
  INTEREST_CARDS,
  type InterestKey,
  topicsForSelection,
} from "@/features/onboarding/interests";
import { strings } from "@/i18n/en";
import { BackHeader } from "@/ui/BackHeader";
import { Banner } from "@/ui/Banner";
import { Button } from "@/ui/Button";
import { ChoiceCard } from "@/ui/ChoiceCard";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { spacing } from "@/ui/tokens";

/** Daily goal and interests (same choices as onboarding). */
export default function LearningSettingsScreen() {
  const { session, api, reloadMe } = useAuth();
  const queryClient = useQueryClient();
  const prefs = session.status === "signedIn" ? session.me.preferences : null;
  const subjects = useQuery({ queryKey: ["subjects"], queryFn: api.content.subjects });
  const [goal, setGoal] = useState<DailyGoal>(prefs?.daily_xp_goal ?? 20);
  const [interests, setInterests] = useState<Set<InterestKey>>(
    () =>
      new Set(
        INTEREST_CARDS.filter((c) => prefs?.interest_topics.includes(c.topic)).map((c) => c.key),
      ),
  );
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; tone: "info" | "error" } | null>(null);

  const toggle = (key: InterestKey) =>
    setInterests((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const save = async () => {
    const published = new Set(
      (subjects.data?.items ?? []).flatMap((s) => s.topics.map((t) => t.slug)),
    );
    setBusy(true);
    setMessage(null);
    try {
      await api.me.updatePreferences({
        daily_xp_goal: goal,
        interest_topics: topicsForSelection(interests, published),
      });
      await reloadMe();
      for (const key of ["discover", "progress"]) {
        void queryClient.invalidateQueries({ queryKey: [key] });
      }
      setMessage({ text: strings.settings.saved, tone: "info" });
    } catch (e) {
      setMessage({ text: errorMessage(e), tone: "error" });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen
      footer={
        <Button
          label={strings.settings.save}
          onPress={save}
          loading={busy}
          disabled={subjects.isPending}
        />
      }
    >
      <BackHeader title={strings.settings.sections.learning} />
      {message ? <Banner message={message.text} tone={message.tone} /> : null}
      <View style={styles.group}>
        <Text variant="heading" accessibilityRole="header">
          {strings.settings.learning.goal}
        </Text>
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
      </View>
      <View style={styles.group}>
        <Text variant="heading" accessibilityRole="header">
          {strings.settings.learning.interests}
        </Text>
        <Text tone="muted">{strings.settings.learning.interestsHint}</Text>
        {INTEREST_CARDS.map(({ key }) => (
          <ChoiceCard
            key={key}
            title={strings.onboarding.interests[key].title}
            description={strings.onboarding.interests[key].description}
            selected={interests.has(key)}
            onPress={() => toggle(key)}
          />
        ))}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({ group: { gap: spacing.sm } });
