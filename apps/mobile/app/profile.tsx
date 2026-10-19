import { router } from "expo-router";
import { Alert } from "react-native";

import { useAuth } from "@/features/auth/AuthProvider";
import { strings } from "@/i18n/en";
import { Button } from "@/ui/Button";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

/** Minimal profile: account state and logout. Stats arrive with the progress slice. */
export default function ProfileScreen() {
  const { session, logout } = useAuth();
  if (session.status !== "signedIn") return null;
  const { user } = session.me;

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
        <>
          {user.is_guest ? (
            <Button
              label={strings.profile.createAccount}
              onPress={() => router.push("/account/create")}
            />
          ) : null}
          <Button label={strings.profile.logout} variant="destructive" onPress={confirmLogout} />
        </>
      }
    >
      <Text variant="title" accessibilityRole="header">
        {strings.profile.title}
      </Text>
      <Text variant="heading">{user.display_name ?? strings.profile.guest}</Text>
      {user.email ? <Text tone="muted">{user.email}</Text> : null}
    </Screen>
  );
}
