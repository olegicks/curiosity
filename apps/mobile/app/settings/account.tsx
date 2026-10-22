import { router } from "expo-router";
import { useState } from "react";
import { Alert } from "react-native";

import { errorMessage } from "@/api/errors";
import { useAuth } from "@/features/auth/AuthProvider";
import { strings } from "@/i18n/en";
import { BackHeader } from "@/ui/BackHeader";
import { Banner } from "@/ui/Banner";
import { Button } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";
import { TextField } from "@/ui/TextField";

/** Account settings: identity, password and logout. */
export default function AccountSettingsScreen() {
  const { session, api, reloadMe, logout } = useAuth();
  const user = session.status === "signedIn" ? session.me.user : null;
  const [name, setName] = useState(user?.display_name ?? "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ text: string; tone: "info" | "error" } | null>(null);
  if (!user) return null;

  const saveName = async () => {
    setBusy(true);
    setMessage(null);
    try {
      await api.me.updateDisplayName(name.trim() || null);
      await reloadMe();
      setMessage({ text: strings.settings.saved, tone: "info" });
    } catch (e) {
      setMessage({ text: errorMessage(e), tone: "error" });
    } finally {
      setBusy(false);
    }
  };

  const confirmLogout = () => {
    if (!user.is_guest) {
      void logout();
      return;
    }
    Alert.alert(strings.profile.logout, strings.profile.guestLogoutWarning, [
      { text: strings.profile.createAccount, onPress: () => router.push("/account/create") },
      { text: strings.profile.logoutAnyway, style: "destructive", onPress: () => void logout() },
    ]);
  };

  return (
    <Screen
      footer={
        <Button label={strings.profile.logout} variant="destructive" onPress={confirmLogout} />
      }
    >
      <BackHeader title={strings.settings.sections.account} />
      {message ? <Banner message={message.text} tone={message.tone} /> : null}
      {user.is_guest ? (
        <Card tone="muted">
          <Text>{strings.settings.account.guestBody}</Text>
          <Button
            label={strings.profile.createAccount}
            onPress={() => router.push("/account/create")}
          />
        </Card>
      ) : (
        <>
          <TextField
            label={strings.settings.account.email}
            value={user.email ?? ""}
            editable={false}
          />
          <Button
            label={strings.settings.account.changePassword}
            variant="secondary"
            onPress={() => router.push("/settings/password")}
          />
        </>
      )}
      <TextField
        label={strings.settings.account.displayName}
        value={name}
        onChangeText={setName}
        maxLength={40}
        autoComplete="name"
      />
      <Text variant="caption" tone="muted">
        {strings.settings.account.displayNameHint}
      </Text>
      <Button
        label={strings.settings.save}
        variant="secondary"
        onPress={saveName}
        loading={busy}
        disabled={name.trim() === (user.display_name ?? "")}
      />
    </Screen>
  );
}
