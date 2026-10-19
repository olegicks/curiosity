import { strings } from "@/i18n/en";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

/** Recall (placeholder until the review client slice). */
export default function RecallScreen() {
  return (
    <Screen>
      <Text variant="title" accessibilityRole="header">
        {strings.tabs.recall}
      </Text>
      <Text tone="muted">{strings.placeholder}</Text>
    </Screen>
  );
}
