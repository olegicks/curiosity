import { strings } from "@/i18n/en";
import { APP_VERSION } from "@/lib/config";
import { BackHeader } from "@/ui/BackHeader";
import { Card } from "@/ui/Card";
import { Screen } from "@/ui/Screen";
import { Text } from "@/ui/Text";

export default function AboutScreen() {
  const about = strings.settings.about;
  return (
    <Screen>
      <BackHeader title={strings.settings.sections.about} />
      <Text tone="muted">
        {strings.appName} · {about.version(APP_VERSION)}
      </Text>
      {[
        [about.sourcesTitle, about.sourcesBody],
        [about.disclaimerTitle, about.disclaimerBody],
        [about.licensesTitle, about.licensesBody],
      ].map(([title, body]) => (
        <Card key={title}>
          <Text variant="heading">{title}</Text>
          <Text>{body}</Text>
        </Card>
      ))}
    </Screen>
  );
}
