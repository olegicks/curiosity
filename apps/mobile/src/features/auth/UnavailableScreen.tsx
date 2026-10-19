import { strings } from "@/i18n/en";
import { Button } from "@/ui/Button";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

import { useAuth } from "./AuthProvider";

/** Shown when a saved session exists but the API can't be reached at launch. */
export function UnavailableScreen() {
  const { retry } = useAuth();
  return (
    <Screen footer={<Button label="Try again" onPress={retry} />}>
      <Text variant="title" accessibilityRole="header">
        {strings.appName}
      </Text>
      <Text>{strings.errors.offline}</Text>
    </Screen>
  );
}
