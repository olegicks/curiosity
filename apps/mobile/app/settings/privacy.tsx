import { useState } from "react";
import { Alert, StyleSheet, View } from "react-native";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { shareExport } from "@/features/profile/exportData";
import { strings } from "@/i18n/en";
import { BackHeader } from "@/ui/BackHeader";
import { Banner } from "@/ui/Banner";
import { Button } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { TextField } from "@/ui/TextField";
import { spacing } from "@/ui/tokens";

/** Data export and account deletion (docs/spec/09 §9.6, journey J7). */
export default function PrivacySettingsScreen() {
  const { session, api, deleteAccount } = useAuth();
  const isGuest = session.status === "signedIn" && session.me.user.is_guest;
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [password, setPassword] = useState("");
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<string | null>(null);
  const confirmed = isGuest ? typed.trim() === "DELETE" : password.length > 0;

  const exportData = async () => {
    setExporting(true);
    setError(null);
    try {
      const shared = await shareExport(await api.me.exportData(), new Date());
      if (!shared) setError(strings.settings.privacy.exportUnavailable);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setExporting(false);
    }
  };

  const remove = () => {
    Alert.alert(strings.settings.privacy.confirmTitle, strings.settings.privacy.confirmBody, [
      { text: strings.settings.privacy.cancel, style: "cancel" },
      {
        text: strings.settings.privacy.confirmDelete,
        style: "destructive",
        onPress: () => {
          setDeleting(true);
          setError(null);
          // On success the session ends and the route guard returns to Welcome.
          deleteAccount(isGuest ? null : password).catch((e: unknown) => {
            setError(errorMessage(e));
            setDeleting(false);
          });
        },
      },
    ]);
  };

  return (
    <Screen>
      <BackHeader title={strings.settings.sections.privacy} />
      {error ? <Banner message={error} tone="error" /> : null}
      <Card>
        <Text variant="heading">{strings.settings.privacy.exportTitle}</Text>
        <Text tone="muted">{strings.settings.privacy.exportBody}</Text>
        <Button
          label={strings.settings.privacy.exportCta}
          variant="secondary"
          onPress={exportData}
          loading={exporting}
        />
      </Card>
      <Card tone="danger">
        <Text variant="heading">{strings.settings.privacy.deleteTitle}</Text>
        <Text>{strings.settings.privacy.deleteBody}</Text>
        <Text variant="caption" tone="muted">
          {strings.settings.privacy.deleteKept}
        </Text>
        <View style={styles.field}>
          {isGuest ? (
            <TextField
              label={strings.settings.privacy.typeDelete}
              value={typed}
              onChangeText={setTyped}
              autoCapitalize="characters"
              autoCorrect={false}
            />
          ) : (
            <TextField
              label={strings.settings.privacy.passwordLabel}
              value={password}
              onChangeText={setPassword}
              secureTextEntry
              autoComplete="current-password"
            />
          )}
        </View>
        <Button
          label={strings.settings.privacy.deleteCta}
          variant="destructive"
          onPress={remove}
          loading={deleting}
          disabled={!confirmed}
        />
      </Card>
    </Screen>
  );
}

const styles = StyleSheet.create({ field: { marginVertical: spacing.sm } });
