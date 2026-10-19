import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { useState } from "react";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import {
  INTEREST_CARDS,
  type InterestKey,
  topicsForSelection,
} from "@/features/onboarding/interests";
import { strings } from "@/i18n/en";
import { Banner } from "@/ui/Banner";
import { Button } from "@/ui/Button";
import { ChoiceCard } from "@/ui/ChoiceCard";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

/** Step 1 of onboarding (FR-ONB-2): optional, skippable. */
export default function InterestsScreen() {
  const { api } = useAuth();
  const [selected, setSelected] = useState<Set<InterestKey>>(new Set());
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const subjects = useQuery({ queryKey: ["subjects"], queryFn: api.content.subjects });

  const toggle = (key: InterestKey) =>
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const next = () => router.push("/goal");

  const save = async () => {
    const published = new Set(
      (subjects.data?.items ?? []).flatMap((s) => s.topics.map((t) => t.slug)),
    );
    const topics = topicsForSelection(selected, published);
    if (topics.length === 0) return next();
    setBusy(true);
    setError(null);
    try {
      await api.me.updatePreferences({ interest_topics: topics });
      next();
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Screen
      footer={
        <>
          <Button
            label={strings.onboarding.continue}
            onPress={save}
            loading={busy}
            disabled={selected.size === 0 || subjects.isPending}
          />
          <Button label={strings.onboarding.skip} variant="ghost" onPress={next} />
        </>
      }
    >
      <Text variant="title" accessibilityRole="header">
        {strings.onboarding.interestsTitle}
      </Text>
      <Text tone="muted">{strings.onboarding.interestsBody}</Text>
      {error ? <Banner message={error} tone="error" /> : null}
      {INTEREST_CARDS.map(({ key }) => (
        <ChoiceCard
          key={key}
          title={strings.onboarding.interests[key].title}
          description={strings.onboarding.interests[key].description}
          selected={selected.has(key)}
          onPress={() => toggle(key)}
        />
      ))}
    </Screen>
  );
}
