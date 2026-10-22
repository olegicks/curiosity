import { Image, StyleSheet, View } from "react-native";

import type { LessonContent, Step } from "@/api/types";
import { strings } from "@/i18n/en";
import { API_URL } from "@/lib/config";
import { Card } from "@/ui/Card";
import { Icon, type IconName } from "@/ui/Icon";
import { Markdown } from "@/ui/Markdown";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { radius, spacing } from "@/ui/tokens";

type ContentStep = Exclude<Step, { type: "question" }>;

type ImageOut = { url: string; alt: string; caption?: string | null };

function LessonImage({ image }: { image: ImageOut }) {
  const uri = image.url.startsWith("http") ? image.url : `${API_URL}${image.url}`;
  return (
    <View style={styles.figure}>
      <Image
        source={{ uri }}
        accessible
        accessibilityLabel={image.alt}
        style={styles.image}
        resizeMode="contain"
      />
      {image.caption ? (
        <Text variant="caption" tone="muted">
          {image.caption}
        </Text>
      ) : null}
    </View>
  );
}

/** A coloured pill naming the kind of step, so learners always know what they're looking at. */
function Badge({ icon, label, color }: { icon: IconName; label: string; color: string }) {
  return (
    <View style={[styles.badge, { borderColor: color }]}>
      <Icon name={icon} color={color} size={18} />
      <Text variant="label" style={{ color }}>
        {label.toUpperCase()}
      </Text>
    </View>
  );
}

/** Renders one non-question lesson step (docs/spec/02 §2.8 step table). */
export function StepView({ step, content }: { step: ContentStep; content: LessonContent }) {
  const { colors } = useTheme();
  const badges = strings.lessons.badges;
  switch (step.type) {
    case "hook":
      return (
        <View style={styles.stack}>
          <Badge icon="help-circle" label={badges.hook} color={colors.accent} />
          <Text variant="display" accessibilityRole="header">
            {step.body.trim()}
          </Text>
          {step.image ? <LessonImage image={step.image} /> : null}
        </View>
      );
    case "explanation":
      return (
        <View style={styles.stack}>
          <Badge icon="bulb" label={badges.explanation} color={colors.accent} />
          {step.title ? (
            <Text variant="title" accessibilityRole="header">
              {step.title}
            </Text>
          ) : null}
          <Markdown source={step.body} />
          {step.image ? <LessonImage image={step.image} /> : null}
        </View>
      );
    case "example": {
      const source = content.sources.find((s) => s.key === step.source_key);
      const research = step.kind === "research";
      return (
        <View style={styles.stack}>
          <Badge
            icon={research ? "flask" : "chatbubbles"}
            label={research ? badges.research : badges.illustrative}
            color={colors.accent}
          />
          <Card tone="accent">
            {step.title ? <Text variant="heading">{step.title}</Text> : null}
            <Markdown source={step.body} />
            {source ? (
              <Text variant="caption" tone="muted">
                {source.citation}
              </Text>
            ) : null}
          </Card>
        </View>
      );
    }
    case "misconception":
      return (
        <View style={styles.stack}>
          <Badge icon="alert-circle" label={badges.misconception} color={colors.danger} />
          <Card tone="danger">
            <View style={styles.row}>
              <Icon name="close-circle" color={colors.danger} />
              <Text variant="label" tone="danger">
                {strings.lessons.myth.toUpperCase()}
              </Text>
            </View>
            <Text variant="heading">{step.myth}</Text>
          </Card>
          <Card tone="success">
            <View style={styles.row}>
              <Icon name="checkmark-circle" color={colors.success} />
              <Text variant="label" tone="success">
                {strings.lessons.fact.toUpperCase()}
              </Text>
            </View>
            <Markdown source={step.correction} />
          </Card>
        </View>
      );
    case "evidence":
      return (
        <View style={styles.stack}>
          <Badge icon="library" label={badges.evidence} color={colors.accent} />
          <Card>
            <Text variant="label" tone="muted">
              {step.status === "debated" ? strings.lessons.debated : strings.lessons.established}
            </Text>
            <Markdown source={step.body} />
          </Card>
        </View>
      );
    case "summary":
      return (
        <View style={styles.stack}>
          <Badge icon="list" label={badges.summary} color={colors.success} />
          <Text variant="title" accessibilityRole="header">
            {strings.lessons.keyPoints}
          </Text>
          {step.points.map((point, i) => (
            <View
              key={i}
              style={[
                styles.point,
                { backgroundColor: colors.surface, borderColor: colors.border },
              ]}
            >
              <View style={[styles.pointIcon, { backgroundColor: colors.success }]}>
                <Icon name="checkmark" color={colors.onAccent} size={18} />
              </View>
              <Text variant="reading" style={styles.flex}>
                {point}
              </Text>
            </View>
          ))}
        </View>
      );
  }
}

const styles = StyleSheet.create({
  stack: { gap: spacing.lg },
  badge: {
    alignSelf: "flex-start",
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    borderWidth: 2,
    borderRadius: radius.full,
    paddingHorizontal: spacing.md,
    paddingVertical: 4,
  },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.xs },
  point: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderWidth: 2,
    borderRadius: radius.md,
    padding: spacing.md,
  },
  pointIcon: {
    width: 30,
    height: 30,
    borderRadius: radius.full,
    alignItems: "center",
    justifyContent: "center",
  },
  flex: { flex: 1 },
  figure: { gap: spacing.xs },
  image: { width: "100%", aspectRatio: 4 / 3, borderRadius: radius.md },
});
