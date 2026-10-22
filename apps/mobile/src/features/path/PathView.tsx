import { useEffect, useState } from "react";
import { Animated, Easing, Pressable, StyleSheet, View } from "react-native";

import type { DiscoverOut } from "@/api/types";
import { strings } from "@/i18n/en";
import { useReducedMotion } from "@/lib/motion";
import { Button } from "@/ui/Button";
import { Icon, type IconName } from "@/ui/Icon";
import { ProgressBar } from "@/ui/ProgressBar";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { edge, radius, spacing, type UnitColor, unitColor } from "@/ui/tokens";

import { nodeIcon, nodeOffset, type PathNode, type PathUnit, streakA11yLabel } from "./path";

type Props = {
  units: PathUnit[];
  discover: DiscoverOut | undefined;
  onOpenLesson: (slug: string) => void;
  onStartReview: () => void;
};

const NODE = 76;
const ZIGZAG = 64;

/** Home: stats, a recall prompt when due, then the path of units and lesson nodes. */
export function PathView({ units, discover, onOpenLesson, onStartReview }: Props) {
  const due = discover?.reviews_due ?? 0;
  const allDone = units.length > 0 && units.every((u) => u.completed === u.nodes.length);
  return (
    <View style={styles.stack}>
      {discover ? <StatsBar discover={discover} onStartReview={onStartReview} /> : null}
      {due > 0 ? <ReviewCard due={due} onStart={onStartReview} /> : null}
      {units.length === 0 ? <Text tone="muted">{strings.path.empty}</Text> : null}
      {units.map((unit) => (
        <View key={unit.slug} style={styles.unit}>
          <UnitHeader unit={unit} />
          <View style={styles.nodes}>
            {unit.nodes.map((node, i) => (
              <View
                key={node.lesson.slug}
                style={{ transform: [{ translateX: nodeOffset(i, ZIGZAG) }] }}
              >
                <NodeButton
                  node={node}
                  color={unitColor(unit.index)}
                  onPress={() => onOpenLesson(node.lesson.slug)}
                />
              </View>
            ))}
            <View style={{ transform: [{ translateX: nodeOffset(unit.nodes.length, ZIGZAG) }] }}>
              <Trophy earned={unit.completed === unit.nodes.length} />
            </View>
          </View>
        </View>
      ))}
      {allDone ? (
        <View style={styles.center}>
          <Text variant="title">{strings.path.allDoneTitle}</Text>
          <Text tone="muted" style={styles.centerText}>
            {strings.path.allDoneBody}
          </Text>
        </View>
      ) : null}
    </View>
  );
}

function Chip({
  icon,
  color,
  label,
  a11y,
  onPress,
}: {
  icon: IconName;
  color: string;
  label: string;
  a11y: string;
  onPress?: () => void;
}) {
  const { colors } = useTheme();
  return (
    <Pressable
      accessibilityRole={onPress ? "button" : "text"}
      accessibilityLabel={a11y}
      disabled={!onPress}
      onPress={onPress}
      style={[styles.chip, { backgroundColor: colors.surface, borderColor: colors.border }]}
    >
      <Icon name={icon} color={color} size={20} />
      <Text variant="label" importantForAccessibility="no">
        {label}
      </Text>
    </Pressable>
  );
}

function StatsBar({
  discover,
  onStartReview,
}: {
  discover: DiscoverOut;
  onStartReview: () => void;
}) {
  const { colors } = useTheme();
  const { streak, xp, reviews_due: due } = discover;
  return (
    <View style={styles.stats}>
      <Chip
        icon="flame"
        color={streak.current > 0 ? colors.streak : colors.idleIcon}
        label={String(streak.current)}
        a11y={streakA11yLabel(discover)}
      />
      <Chip
        icon="flash"
        color={colors.xp}
        label={`${xp.today}/${xp.goal}`}
        a11y={
          xp.today >= xp.goal
            ? strings.discover.goalReached
            : strings.discover.xpToday(xp.today, xp.goal)
        }
      />
      <Chip
        icon="bulb"
        color={due > 0 ? colors.accent : colors.idleIcon}
        label={String(due)}
        a11y={strings.path.dueChip(due)}
        onPress={due > 0 ? onStartReview : undefined}
      />
    </View>
  );
}

function ReviewCard({ due, onStart }: { due: number; onStart: () => void }) {
  const { colors } = useTheme();
  return (
    <View style={[styles.review, { backgroundColor: colors.accentBg, borderColor: colors.accent }]}>
      <View style={styles.reviewRow}>
        <View style={[styles.reviewIcon, { backgroundColor: colors.accent }]}>
          <Icon name="bulb" color={colors.onAccent} size={26} />
        </View>
        <View style={styles.flex}>
          <Text variant="heading">{strings.path.reviewTitle}</Text>
          <Text>{strings.path.reviewBody(due)}</Text>
        </View>
      </View>
      <Button label={strings.path.reviewCta} onPress={onStart} />
    </View>
  );
}

function UnitHeader({ unit }: { unit: PathUnit }) {
  const color = unitColor(unit.index);
  const total = unit.nodes.length;
  return (
    <View
      accessibilityRole="header"
      accessible
      accessibilityLabel={`${strings.path.unit(unit.index + 1)}: ${unit.title}. ${strings.path.unitProgress(unit.completed, total)}`}
      style={[styles.unitHeader, { backgroundColor: color.fill, borderColor: color.edge }]}
    >
      <Text variant="caption" style={styles.onFillMuted}>
        {strings.path.unit(unit.index + 1).toUpperCase()}
      </Text>
      <Text variant="heading" style={styles.onFill}>
        {unit.title}
      </Text>
      <View style={styles.unitProgress}>
        <ProgressBar value={unit.completed} max={total} label="" color="#FFFFFF" />
        <Text variant="caption" style={styles.onFill}>
          {unit.completed}/{total}
        </Text>
      </View>
    </View>
  );
}

function NodeButton({
  node,
  color,
  onPress,
}: {
  node: PathNode;
  color: UnitColor;
  onPress: () => void;
}) {
  const { colors } = useTheme();
  const current = node.state === "current";
  const lit = node.state !== "upcoming";
  const face = lit ? color.fill : colors.idle;
  const rim = lit ? color.edge : colors.idleEdge;
  const label = strings.path.nodeLabel(node.lesson.title, strings.path.states[node.state]);

  return (
    <View style={styles.nodeWrap}>
      {current ? (
        <View style={[styles.bubble, { backgroundColor: colors.surface, borderColor: color.fill }]}>
          <Text variant="label" style={{ color: color.fill }}>
            {(node.started ? strings.path.continue : strings.path.start).toUpperCase()}
          </Text>
        </View>
      ) : null}
      <View style={styles.nodeHolder}>
        {current ? <Pulse color={color.tint} /> : null}
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={label}
          onPress={onPress}
          style={({ pressed }) => [
            styles.node,
            {
              backgroundColor: face,
              borderColor: rim,
              borderBottomWidth: pressed ? 2 : edge + 2,
              marginTop: pressed ? edge : 0,
            },
          ]}
        >
          <Icon name={nodeIcon(node)} color={lit ? "#FFFFFF" : colors.idleIcon} size={34} />
        </Pressable>
      </View>
      <Text
        variant="caption"
        tone={lit ? "default" : "muted"}
        numberOfLines={2}
        style={styles.nodeTitle}
        importantForAccessibility="no"
      >
        {node.lesson.title}
      </Text>
    </View>
  );
}

/** A soft ring that breathes around the current node. Static when motion is reduced. */
function Pulse({ color }: { color: string }) {
  const reduced = useReducedMotion();
  const scale = useState(() => new Animated.Value(1))[0];
  useEffect(() => {
    if (reduced) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(scale, {
          toValue: 1.18,
          duration: 900,
          easing: Easing.out(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(scale, {
          toValue: 1,
          duration: 900,
          easing: Easing.in(Easing.quad),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [reduced, scale]);
  return (
    <Animated.View
      pointerEvents="none"
      style={[styles.pulse, { backgroundColor: color, transform: [{ scale }] }]}
    />
  );
}

function Trophy({ earned }: { earned: boolean }) {
  const { colors } = useTheme();
  return (
    <View
      accessible
      accessibilityLabel={`${strings.path.unitTrophy}, ${earned ? strings.path.trophyEarned : strings.path.trophyLocked}`}
      style={[
        styles.trophy,
        {
          backgroundColor: earned ? colors.xp : colors.idle,
          borderColor: earned ? "#C98500" : colors.idleEdge,
        },
      ]}
    >
      <Icon name="trophy" color={earned ? "#FFFFFF" : colors.idleIcon} size={30} />
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: spacing.xl },
  stats: { flexDirection: "row", justifyContent: "space-between", gap: spacing.sm },
  chip: {
    flex: 1,
    minHeight: 44,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    borderWidth: 2,
    borderRadius: radius.md,
  },
  review: { borderWidth: 2, borderRadius: radius.lg, padding: spacing.lg, gap: spacing.md },
  reviewRow: { flexDirection: "row", gap: spacing.md, alignItems: "center" },
  reviewIcon: {
    width: 48,
    height: 48,
    borderRadius: radius.full,
    alignItems: "center",
    justifyContent: "center",
  },
  flex: { flex: 1, gap: spacing.xs },
  unit: { gap: spacing.xl },
  unitHeader: {
    borderRadius: radius.lg,
    borderBottomWidth: edge + 2,
    padding: spacing.lg,
    gap: spacing.xs,
  },
  unitProgress: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: 4 },
  onFill: { color: "#FFFFFF" },
  onFillMuted: { color: "#FFFFFF", opacity: 0.85, letterSpacing: 1 },
  nodes: { alignItems: "center", gap: spacing.lg },
  nodeWrap: { alignItems: "center", width: 150, gap: spacing.xs },
  nodeHolder: {
    width: NODE + 24,
    height: NODE + edge + 24,
    alignItems: "center",
    justifyContent: "center",
  },
  node: {
    width: NODE,
    height: NODE + edge,
    borderRadius: radius.full,
    alignItems: "center",
    justifyContent: "center",
  },
  pulse: {
    position: "absolute",
    width: NODE + 20,
    height: NODE + 20,
    borderRadius: radius.full,
  },
  bubble: {
    borderWidth: 2,
    borderBottomWidth: edge,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 2,
  },
  nodeTitle: { textAlign: "center" },
  trophy: {
    width: NODE,
    height: NODE,
    borderRadius: radius.full,
    borderBottomWidth: edge + 2,
    alignItems: "center",
    justifyContent: "center",
  },
  center: { alignItems: "center", gap: spacing.sm, paddingVertical: spacing.xl },
  centerText: { textAlign: "center" },
});
