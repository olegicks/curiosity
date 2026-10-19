import { router } from "expo-router";
import { useState } from "react";
import { StyleSheet, View } from "react-native";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { strings } from "@/i18n/en";
import { Banner } from "@/ui/Banner";
import { Button } from "@/ui/Button";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { spacing } from "@/ui/tokens";

export default function WelcomeScreen() {
  const { session, startAsGuest } = useAuth();
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
        <Text variant="display" accessibilityRole="header">
          {strings.appName}
        </Text>
        <Text variant="reading" tone="muted">
          {strings.welcome.tagline}
        </Text>
      </View>
      {notice ? <Banner message={notice} /> : null}
      {error ? <Banner message={error} tone="error" /> : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  hero: { gap: spacing.md, paddingTop: spacing["3xl"] },
  legal: { textAlign: "center" },
});
