import { router } from "expo-router";
import { useState } from "react";
import { StyleSheet, View } from "react-native";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { strings } from "@/i18n/en";
import { Banner } from "@/ui/Banner";
import { Button } from "@/ui/Button";
import { Icon, type IconName } from "@/ui/Icon";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { edge, radius, spacing, unitColor } from "@/ui/tokens";

const STEP_ICONS: IconName[] = ["book", "help-circle", "bulb"];

export default function WelcomeScreen() {
  const { session, startAsGuest } = useAuth();
  const { colors } = useTheme();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const notice = session.status === "signedOut" ? session.notice : null;

  const start = async () => {
    setBusy(true);
    setError(null);
    try {
      await startAsGuest(); // the route guard moves on to onboarding
    } catch (e) {
      setError(errorMessage(e));
      setBusy(false);
    }
  };

  return (
    <Screen
      footer={
        <>
          <Button label={strings.welcome.start} onPress={start} loading={busy} />
          <Button
            label={strings.welcome.haveAccount}
            variant="ghost"
            onPress={() => router.push("/login")}
            disabled={busy}
          />
          <Text variant="caption" tone="muted" style={styles.legal}>
            {strings.welcome.legal}
          </Text>
        </>
      }
    >
      <View style={styles.hero}>
        <View
          style={[styles.logo, { backgroundColor: colors.accent, borderColor: colors.accentEdge }]}
        >
          <Icon name="sparkles" color={colors.onAccent} size={56} />
        </View>
        <Text variant="display" accessibilityRole="header" style={styles.center}>
          {strings.appName}
        </Text>
        <Text variant="reading" tone="muted" style={styles.center}>
          {strings.welcome.tagline}
        </Text>
      </View>
      <View style={styles.steps}>
        {strings.welcome.steps.map((step, i) => {
          const color = unitColor(i);
          return (
            <View
              key={step.title}
              accessible
              accessibilityLabel={`${i + 1}. ${step.title}. ${step.body}`}
              style={[styles.step, { backgroundColor: colors.surface, borderColor: colors.border }]}
            >
              <View style={[styles.stepIcon, { backgroundColor: color.fill }]}>
                <Icon name={STEP_ICONS[i]!} color="#FFFFFF" size={24} />
              </View>
              <View style={styles.flex}>
                <Text variant="heading">{step.title}</Text>
                <Text tone="muted">{step.body}</Text>
              </View>
            </View>
          );
        })}
      </View>
      {notice ? <Banner message={notice} /> : null}
      {error ? <Banner message={error} tone="error" /> : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { gap: spacing.md, paddingTop: spacing.xl, alignItems: "center" },
  logo: {
    width: 112,
    height: 112,
    borderRadius: radius.lg,
    borderBottomWidth: edge + 2,
    alignItems: "center",
    justifyContent: "center",
    transform: [{ rotate: "-6deg" }],
  },
  center: { textAlign: "center" },
  steps: { gap: spacing.sm },
  step: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderWidth: 2,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  stepIcon: {
    width: 44,
    height: 44,
    borderRadius: radius.full,
    alignItems: "center",
    justifyContent: "center",
  },
  flex: { flex: 1 },
  legal: { textAlign: "center" },
});
