import { strings } from "@/i18n/en";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

/** Learn library (placeholder until the lesson client slice). */
export default function LearnScreen() {
  return (
    <Screen>
      <Text variant="title" accessibilityRole="header">
        {strings.tabs.learn}
      </Text>
      <Text tone="muted">{strings.placeholder}</Text>
    </Screen>
  );
}
