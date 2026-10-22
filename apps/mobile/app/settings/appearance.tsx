import { strings } from "@/i18n/en";
import { BackHeader } from "@/ui/BackHeader";
import { ChoiceCard } from "@/ui/ChoiceCard";
import { Screen } from "@/ui/Screen";
import { type ThemePreference, useTheme } from "@/ui/theme";

const OPTIONS: ThemePreference[] = ["system", "light", "dark"];

/** Theme choice; stored on this device only. */
export default function AppearanceSettingsScreen() {
  const { preference, setPreference } = useTheme();
  return (
    <Screen>
      <BackHeader title={strings.settings.sections.appearance} />
      {OPTIONS.map((option) => (
        <ChoiceCard
          key={option}
          role="radio"
          title={strings.settings.appearance[option]}
          selected={preference === option}
          onPress={() => setPreference(option)}
        />
      ))}
    </Screen>
  );
}
