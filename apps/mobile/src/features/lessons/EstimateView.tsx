import { useState } from "react";
import { type LayoutChangeEvent, type GestureResponderEvent, StyleSheet, View } from "react-native";

import { errorMessage } from "@/api/errors";
import type { AnswerResult, QuestionOut } from "@/api/types";
import { strings } from "@/i18n/en";
import { haptics } from "@/lib/haptics";
import { Banner } from "@/ui/Banner";
import { Button } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { Icon } from "@/ui/Icon";
import { Mascot } from "@/ui/Mascot";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { radius, spacing } from "@/ui/tokens";

import { a11yStep, formatNumber, fraction, snap, startValue, valueAt } from "./estimate";

type Props = {
  question: QuestionOut;
  result: AnswerResult | undefined;
  /** Sends the value; the server grades it. */
  onSubmit: (value: number) => Promise<AnswerResult>;
};

const THUMB = 36;

/** Estimate challenge (D-18): drag to a number, then the server reveals the real one. */
export function EstimateView({ question, result, onSubmit }: Props) {
  const { colors } = useTheme();
  const config = question.estimate!;
  const [value, setValue] = useState(() => result?.estimate?.value ?? startValue(config));
  const [touched, setTouched] = useState(false);
  const [width, setWidth] = useState(0);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const locked = checking || result !== undefined;
  const unit = config.unit;
  const shown = result?.estimate?.value ?? value;

  const move = (e: GestureResponderEvent) => {
    if (locked) return;
    const next = valueAt(e.nativeEvent.locationX, width, config);
    if (next !== value) {
      setValue(next);
      if (Math.round(fraction(next, config) * 20) !== Math.round(fraction(value, config) * 20)) {
        haptics.select();
      }
    }
    setTouched(true);
  };

  const nudge = (direction: 1 | -1) => {
    if (locked) return;
    setValue((v) => snap(v + direction * a11yStep(config), config));
    setTouched(true);
  };

  const check = async () => {
    setChecking(true);
    setError(null);
    try {
      const answer = await onSubmit(value);
      haptics.result(answer.is_correct);
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setChecking(false);
    }
  };

  const at = (v: number) => `${fraction(v, config) * 100}%` as const;
  const real = result?.estimate;

  return (
    <View style={styles.stack}>
      <View style={[styles.badge, { borderColor: colors.xp }]}>
        <Icon name="locate" color={colors.xp} size={18} />
        <Text variant="label" tone="muted">
          {strings.lessons.badges.estimate.toUpperCase()}
        </Text>
      </View>
      <View style={styles.row}>
        <Mascot size={52} mood="think" />
        <Text variant="title" accessibilityRole="header" style={styles.flex}>
          {question.prompt}
        </Text>
      </View>

      <View style={styles.sliderArea}>
        <View
          onLayout={(e: LayoutChangeEvent) => setWidth(e.nativeEvent.layout.width)}
          onStartShouldSetResponder={() => !locked}
          onMoveShouldSetResponder={() => !locked}
          onResponderGrant={move}
          onResponderMove={move}
          onResponderTerminationRequest={() => false}
          accessible
          accessibilityRole="adjustable"
          accessibilityLabel={strings.lessons.estimate.label(unit)}
          accessibilityValue={{
            min: config.min,
            max: config.max,
            now: shown,
            text: `${formatNumber(shown)} ${unit}`,
          }}
          accessibilityActions={[{ name: "increment" }, { name: "decrement" }]}
          onAccessibilityAction={(e) => nudge(e.nativeEvent.actionName === "increment" ? 1 : -1)}
          style={styles.touch}
        >
          <View pointerEvents="none" style={[styles.track, { backgroundColor: colors.idle }]}>
            {real ? (
              <View
                style={[
                  styles.band,
                  {
                    backgroundColor: colors.successBg,
                    borderColor: colors.success,
                    left: at(real.answer - real.tolerance),
                    width: `${(fraction(real.answer + real.tolerance, config) - fraction(real.answer - real.tolerance, config)) * 100}%`,
                  },
                ]}
              />
            ) : null}
            <View style={[styles.fill, { width: at(shown), backgroundColor: colors.accent }]} />
          </View>
          {config.anchor != null ? (
            <Marker
              left={at(config.anchor)}
              color={colors.danger}
              label={strings.lessons.estimate.anchor(formatNumber(config.anchor))}
            />
          ) : null}
          {real ? (
            <Marker
              left={at(real.answer)}
              color={colors.success}
              label={strings.lessons.estimate.real(formatNumber(real.answer))}
              below
            />
          ) : null}
          <View
            pointerEvents="none"
            style={[
              styles.thumb,
              { left: at(shown), backgroundColor: colors.surface, borderColor: colors.accent },
            ]}
          />
        </View>
        <View style={styles.ends}>
          <Text variant="caption" tone="muted">
            {formatNumber(config.min)} {unit}
          </Text>
          <Text variant="caption" tone="muted">
            {formatNumber(config.max)} {unit}
          </Text>
        </View>
        <Text variant="display" tone="accent" style={styles.center}>
          {formatNumber(shown)} {unit}
        </Text>
        {!touched && !result ? (
          <Text variant="caption" tone="muted" style={styles.center}>
            {strings.lessons.estimate.drag}
          </Text>
        ) : null}
      </View>

      {error ? <Banner message={error} tone="error" /> : null}
      {result && real ? (
        <View accessibilityLiveRegion="polite">
          <Card tone={result.is_correct ? "success" : "danger"}>
            <View style={styles.row}>
              <View
                style={[
                  styles.verdictIcon,
                  { backgroundColor: result.is_correct ? colors.success : colors.danger },
                ]}
              >
                <Icon
                  name={result.is_correct ? "checkmark" : "close"}
                  color={colors.onAccent}
                  size={26}
                />
              </View>
              <Text
                variant="heading"
                tone={result.is_correct ? "success" : "danger"}
                style={styles.flex}
              >
                {result.is_correct ? strings.lessons.estimate.close : strings.lessons.estimate.far}
              </Text>
            </View>
            <Text variant="label">
              {strings.lessons.estimate.result(
                `${formatNumber(real.value)} ${unit}`,
                `${formatNumber(real.answer)} ${unit}`,
              )}
            </Text>
            <Text>{result.explanation}</Text>
          </Card>
        </View>
      ) : (
        <Button
          label={strings.lessons.check}
          onPress={check}
          loading={checking}
          disabled={!touched}
        />
      )}
    </View>
  );
}

function Marker({
  left,
  color,
  label,
  below = false,
}: {
  left: `${number}%`;
  color: string;
  label: string;
  below?: boolean;
}) {
  return (
    <View pointerEvents="none" style={[styles.marker, { left }]}>
      <Text
        variant="caption"
        numberOfLines={1}
        style={[styles.markerLabel, { color }, below ? styles.markerBelow : styles.markerAbove]}
      >
        {label}
      </Text>
      <View style={[styles.markerLine, { backgroundColor: color }]} />
    </View>
  );
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
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  flex: { flex: 1 },
  sliderArea: { gap: spacing.sm, paddingTop: spacing.xl, paddingBottom: spacing.md },
  touch: { height: 56, justifyContent: "center", marginHorizontal: THUMB / 2 },
  track: { height: 12, borderRadius: radius.full, overflow: "hidden" },
  fill: { height: 12, borderRadius: radius.full },
  band: { position: "absolute", top: 0, bottom: 0, borderWidth: 1 },
  thumb: {
    position: "absolute",
    top: 10,
    width: THUMB,
    height: THUMB,
    marginLeft: -THUMB / 2,
    borderRadius: radius.full,
    borderWidth: 5,
  },
  marker: {
    position: "absolute",
    top: 4,
    bottom: 4,
    width: 4,
    marginLeft: -2,
    alignItems: "center",
  },
  markerLine: { flex: 1, width: 4, borderRadius: 2 },
  markerLabel: {
    position: "absolute",
    width: 110,
    textAlign: "center",
    fontFamily: "Inter_700Bold",
  },
  markerAbove: { top: -22 },
  markerBelow: { bottom: -22 },
  ends: { flexDirection: "row", justifyContent: "space-between", marginTop: spacing.md },
  center: { textAlign: "center" },
  verdictIcon: {
    width: 40,
    height: 40,
    borderRadius: radius.full,
    alignItems: "center",
    justifyContent: "center",
  },
});
