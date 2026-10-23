import { useEffect, useState } from "react";
import { Animated, StyleSheet, View } from "react-native";

import type { CompletionResponse } from "@/api/types";
import { strings } from "@/i18n/en";
import { useReducedMotion } from "@/lib/motion";
import { Button } from "@/ui/Button";
import { Card } from "@/ui/Card";
import { Confetti } from "@/ui/Confetti";
import { Icon, type IconName } from "@/ui/Icon";
import { Mascot } from "@/ui/Mascot";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { edge, radius, spacing } from "@/ui/tokens";

import { xpLabel } from "./library";
import { weekStrip } from "./reward";

type Props = {
  completion: CompletionResponse;
  takeaways: string[];
  onRate: (rating: "clear" | "unclear") => Promise<void>;
};

const MAX_ACHIEVEMENTS_SHOWN = 2;

/** Celebration after a lesson (docs/spec/02 FR-LRN-6, D-16). Actions live in the player footer. */
export function CompletionView({ completion, takeaways, onRate }: Props) {
  const { colors } = useTheme();
  const reduced = useReducedMotion();
  const pop = useState(() => new Animated.Value(0))[0];
  const [rated, setRated] = useState(false);
  const { attempt, xp_awarded, achievements_unlocked, first_review_on, streak } = completion;
  const xp = xp_awarded.reduce((sum, award) => sum + award.amount, 0);
  const accuracy =
    attempt.question_count > 0
      ? Math.round((attempt.correct_first_try / attempt.question_count) * 100)
      : 100;

  useEffect(() => {
    if (reduced) {
      pop.setValue(1);
      return;
    }
    Animated.spring(pop, { toValue: 1, friction: 5, tension: 80, useNativeDriver: true }).start();
  }, [pop, reduced]);

  const rate = async (rating: "clear" | "unclear") => {
    setRated(true);
    await onRate(rating).catch(() => setRated(false));
  };

  return (
    <View style={styles.stack}>
      <View style={styles.hero}>
        <Animated.View
          style={[styles.trophy, { backgroundColor: colors.accentBg, transform: [{ scale: pop }] }]}
        >
          <Mascot size={96} mood="cheer" />
        </Animated.View>
        <Text variant="display" accessibilityRole="header" style={styles.center}>
          {strings.lessons.completeTitle}
        </Text>
        <Text tone="muted" style={styles.center}>
          {strings.lessons.score(attempt.correct_first_try, attempt.question_count)}
        </Text>
      </View>

      <View style={styles.tiles}>
        <Tile icon="flash" color={colors.xp} label={strings.lessons.statXp} value={`+${xp}`} />
        <Tile
          icon="locate"
          color={colors.success}
          label={strings.lessons.statAccuracy}
          value={`${accuracy}%`}
        />
        <Tile
          icon="flame"
          color={colors.streak}
          label={strings.lessons.statStreak}
          value={strings.lessons.days(streak.current)}
        />
      </View>

      <View style={[styles.week, { borderColor: colors.border, backgroundColor: colors.surface }]}>
        <View style={styles.awardRow}>
          <Text variant="label">{strings.lessons.thisWeek}</Text>
          {completion.xp.today >= completion.xp.goal ? (
            <Text variant="label" tone="success">
              {strings.discover.goalReached}
            </Text>
          ) : null}
        </View>
        <View style={styles.days}>
          {weekStrip(new Date(), streak.current).map((day) => (
            <View
              key={day.label}
              accessible
              accessibilityLabel={`${day.label}, ${day.done ? strings.lessons.dayDone : strings.lessons.dayOpen}`}
              style={styles.day}
            >
              <View
                style={[
                  styles.dayDot,
                  {
                    backgroundColor: day.done ? colors.streak : colors.idle,
                    borderColor: day.today ? colors.text : "transparent",
                  },
                ]}
              >
                {day.done ? (
                  <Icon name={day.today ? "flame" : "checkmark"} color="#FFFFFF" size={16} />
                ) : null}
              </View>
              <Text variant="caption" tone={day.today ? "default" : "muted"}>
                {day.today ? strings.lessons.today : day.label}
              </Text>
            </View>
          ))}
        </View>
      </View>

      {xp_awarded.length === 0 ? (
        <Text tone="muted" style={styles.center}>
          {strings.lessons.noXpRevisit}
        </Text>
      ) : (
        <View accessible accessibilityLabel={strings.lessons.xpEarned} style={styles.awards}>
          {xp_awarded.map((award) => (
            <View key={award.reason} style={styles.awardRow}>
              <Text tone="muted">{xpLabel(award.reason)}</Text>
              <Text variant="label">+{award.amount} XP</Text>
            </View>
          ))}
        </View>
      )}

      {achievements_unlocked.slice(0, MAX_ACHIEVEMENTS_SHOWN).map((a) => (
        <Card key={a.code} tone="success">
          <View style={styles.row}>
            <Icon name="ribbon" color={colors.success} size={28} />
            <View style={styles.flex}>
              <Text variant="label" tone="success">
                {strings.lessons.unlocked.toUpperCase()}
              </Text>
              <Text variant="heading">{a.title}</Text>
              <Text tone="muted">{a.description}</Text>
            </View>
          </View>
        </Card>
      ))}

      {takeaways.length > 0 ? (
        <Card>
          <Text variant="label" tone="muted">
            {strings.lessons.keyPoints.toUpperCase()}
          </Text>
          {takeaways.map((point, i) => (
            <View key={i} style={styles.row}>
              <Icon name="checkmark-circle" color={colors.success} />
              <Text style={styles.flex}>{point}</Text>
            </View>
          ))}
        </Card>
      ) : null}

      {first_review_on ? (
        <Card tone="accent">
          <View style={styles.row}>
            <Icon name="bulb" color={colors.accent} size={28} />
            <Text style={styles.flex}>{strings.lessons.firstReview}</Text>
          </View>
        </Card>
      ) : null}

      <View style={styles.rating}>
        <Text variant="label" style={styles.center}>
          {rated ? strings.lessons.thanks : strings.lessons.wasClear}
        </Text>
        {!rated ? (
          <View style={styles.ratingButtons}>
            <View style={styles.flex}>
              <Button
                label={strings.lessons.clear}
                variant="secondary"
                onPress={() => rate("clear")}
              />
            </View>
            <View style={styles.flex}>
              <Button
                label={strings.lessons.unclear}
                variant="secondary"
                onPress={() => rate("unclear")}
              />
            </View>
          </View>
        ) : null}
      </View>
      <Confetti />
    </View>
  );
}

function Tile({
  icon,
  color,
  label,
  value,
}: {
  icon: IconName;
  color: string;
  label: string;
  value: string;
}) {
  const { colors } = useTheme();
  return (
    <View
      accessible
      accessibilityLabel={`${label}: ${value}`}
      style={[styles.tile, { borderColor: color, backgroundColor: colors.surface }]}
    >
      <Text variant="caption" tone="muted" style={styles.center}>
        {label.toUpperCase()}
      </Text>
      <View style={styles.tileBody}>
        <Icon name={icon} color={color} size={22} />
        <Text variant="heading">{value}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: spacing.lg },
  hero: { alignItems: "center", gap: spacing.sm, paddingTop: spacing.md },
  trophy: {
    width: 150,
    height: 150,
    borderRadius: radius.full,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.sm,
  },
  center: { textAlign: "center" },
  tiles: { flexDirection: "row", gap: spacing.sm },
  tile: {
    flex: 1,
    borderWidth: 2,
    borderBottomWidth: edge,
    borderRadius: radius.md,
    paddingTop: spacing.sm,
  },
  tileBody: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    paddingBottom: spacing.md,
    paddingTop: spacing.xs,
  },
  week: {
    borderWidth: 2,
    borderBottomWidth: edge,
    borderRadius: radius.md,
    padding: spacing.md,
    gap: spacing.sm,
  },
  days: { flexDirection: "row", justifyContent: "space-between" },
  day: { alignItems: "center", gap: 4 },
  dayDot: {
    width: 32,
    height: 32,
    borderRadius: radius.full,
    borderWidth: 3,
    alignItems: "center",
    justifyContent: "center",
  },
  awards: { gap: spacing.xs },
  awardRow: { flexDirection: "row", justifyContent: "space-between" },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  flex: { flex: 1 },
  rating: { gap: spacing.sm },
  ratingButtons: { flexDirection: "row", gap: spacing.sm },
});
