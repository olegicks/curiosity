import { Image, StyleSheet, View } from "react-native";

import type { LessonContent, Step } from "@/api/types";
import { strings } from "@/i18n/en";
import { API_URL } from "@/lib/config";
import { Card } from "@/ui/Card";
import { Markdown } from "@/ui/Markdown";
import { Text } from "@/ui/Text";
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

/** Renders one non-question lesson step (docs/spec/02 §2.8 step table). */
export function StepView({ step, content }: { step: ContentStep; content: LessonContent }) {
  switch (step.type) {
    case "hook":
      return (
        <View style={styles.stack}>
          <Text variant="display" accessibilityRole="header">
            {step.body.trim()}
          </Text>
          {step.image ? <LessonImage image={step.image} /> : null}
        </View>
      );
    case "explanation":
      return (
        <View style={styles.stack}>
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
      return (
        <Card tone="muted">
          <Text variant="label" tone="muted">
            {strings.lessons.example} ·{" "}
            {step.kind === "research" ? strings.lessons.fromResearch : strings.lessons.illustrative}
          </Text>
          {step.title ? <Text variant="heading">{step.title}</Text> : null}
          <Markdown source={step.body} />
          {source ? (
            <Text variant="caption" tone="muted">
              {source.citation}
            </Text>
          ) : null}
        </Card>
      );
    }
    case "misconception":
      return (
        <Card>
          <Text variant="label" tone="muted">
            {strings.lessons.misconception}
          </Text>
          <Text variant="heading">{step.myth}</Text>
          <Markdown source={step.correction} />
        </Card>
      );
    case "evidence":
      return (
        <Card>
          <Text variant="label" tone="muted">
            {strings.lessons.evidence} ·{" "}
            {step.status === "debated" ? strings.lessons.debated : strings.lessons.established}
          </Text>
          <Markdown source={step.body} />
        </Card>
      );
    case "summary":
      return (
        <View style={styles.stack}>
          <Text variant="title" accessibilityRole="header">
            {strings.lessons.keyPoints}
          </Text>
          <Markdown source={step.points.map((p) => `- ${p}`).join("\n")} />
        </View>
      );
  }
}

const styles = StyleSheet.create({
  stack: { gap: spacing.lg },
  figure: { gap: spacing.xs },
  image: { width: "100%", aspectRatio: 4 / 3, borderRadius: radius.md },
});
