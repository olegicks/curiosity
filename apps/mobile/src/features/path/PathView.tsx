import { Fragment, type ReactNode, useEffect, useState } from "react";
import { Animated, Easing, Modal, Pressable, StyleSheet, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import type { DiscoverOut } from "@/api/types";
import { startLabel } from "@/features/lessons/library";
import { strings } from "@/i18n/en";
import { useReducedMotion } from "@/lib/motion";
import { Button } from "@/ui/Button";
import { Icon, type IconName } from "@/ui/Icon";
import { Mascot } from "@/ui/Mascot";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { edge, radius, spacing, type UnitColor } from "@/ui/tokens";

import {
  isLearned,
  nodeIcon,
  nodeOffset,
  type PathNode,
  type PathUnit,
  streakA11yLabel,
} from "./path";

export type PathSubject = {
  title: string;
  icon: IconName;
  color: UnitColor;
  decor?: IconName[];
};

type Props = {
  subject: PathSubject | null;
  units: PathUnit[];
  discover: DiscoverOut | undefined;
  onSwitchSubject: () => void;
  onOpenLesson: (slug: string) => void;
  onPlayLesson: (slug: string) => void;
  onStartReview: () => void;
};

const NODE = 76;
const ZIGZAG = 64;

type Picked = { node: PathNode; position: number; total: number };

/** Home (D-16, D-17): the chosen subject's roadmap, one unit per topic. */
export function PathView({
  subject,
  units,
  discover,
  onSwitchSubject,
  onOpenLesson,
  onPlayLesson,
  onStartReview,
}: Props) {
  const { colors } = useTheme();
  const [picked, setPicked] = useState<Picked | null>(null);
  const due = discover?.reviews_due ?? 0;
  const color = subject?.color ?? {
    fill: colors.accent,
    edge: colors.accentEdge,
    tint: colors.accentBg,
  };
  const allDone = units.length > 0 && units.every((u) => u.completed === u.nodes.length);

  return (
    <View style={styles.stack}>
      <View style={styles.header}>
        {subject ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={strings.subjects.switchTo(subject.title)}
            onPress={onSwitchSubject}
            style={[styles.pill, { backgroundColor: colors.surface, borderColor: colors.border }]}
          >
            <View style={[styles.pillIcon, { backgroundColor: color.fill }]}>
              <Icon name={subject.icon} color="#FFFFFF" size={16} />
            </View>
            <Text variant="label">{subject.title}</Text>
            <Icon name="chevron-down" color={colors.textMuted} size={16} />
          </Pressable>
        ) : null}
        <View style={styles.flex} />
        {discover ? <Stats discover={discover} onStartReview={onStartReview} /> : null}
      </View>

      {due > 0 ? <ReviewCard due={due} onStart={onStartReview} /> : null}
      {units.length === 0 ? <Text tone="muted">{strings.path.empty}</Text> : null}

      {units.map((unit) => (
        <View key={unit.slug} style={styles.unit}>
          <UnitHeader unit={unit} color={color} icon={subject?.icon ?? "sparkles"} />
          <View style={styles.nodes}>
            {unit.nodes.map((node, i) => {
              const offset = nodeOffset(i, ZIGZAG);
              const side = offset > 0 ? -1 : offset < 0 ? 1 : i % 8 === 0 ? -1 : 1;
              const decor = subject?.decor ?? [];
              return (
                <Fragment key={node.lesson.slug}>
                  {i > 0 ? (
                    <Trail
                      from={nodeOffset(i - 1, ZIGZAG)}
                      to={offset}
                      lit={node.state !== "upcoming"}
                      color={color}
                    />
                  ) : null}
                  <View style={{ transform: [{ translateX: offset }] }}>
                    {node.state === "current" ? (
                      <View
                        style={[
                          styles.guide,
                          offset > 0 ? { right: NODE + 60 } : { left: NODE + 60 },
                        ]}
                      >
                        <View
                          style={[
                            styles.guideBubble,
                            { backgroundColor: colors.surface, borderColor: colors.border },
                          ]}
                        >
                          <Text variant="caption" numberOfLines={2}>
                            {strings.path.nextUp(node.lesson.title)}
                          </Text>
                        </View>
                        <Mascot size={52} />
                      </View>
                    ) : decor.length > 0 ? (
                      <Decoration
                        icon={decor[(unit.index * 3 + i) % decor.length]!}
                        color={color}
                        side={side}
                        tilt={i % 2 === 0 ? -12 : 10}
                      />
                    ) : null}
                    <NodeButton
                      node={node}
                      color={color}
                      onPress={() => setPicked({ node, position: i + 1, total: unit.nodes.length })}
                    />
                  </View>
                </Fragment>
              );
            })}
            <Trail
              from={nodeOffset(unit.nodes.length - 1, ZIGZAG)}
              to={nodeOffset(unit.nodes.length, ZIGZAG)}
              lit={unit.completed === unit.nodes.length}
              color={color}
            />
            <View style={{ transform: [{ translateX: nodeOffset(unit.nodes.length, ZIGZAG) }] }}>
              <Trophy earned={unit.completed === unit.nodes.length} />
            </View>
          </View>
        </View>
      ))}

      {allDone ? (
        <View style={styles.center}>
          <Mascot size={80} mood="cheer" />
          <Text variant="title">{strings.path.allDoneTitle}</Text>
          <Text tone="muted" style={styles.centerText}>
            {strings.path.allDoneBody}
          </Text>
        </View>
      ) : null}

      <LessonSheet
        picked={picked}
        color={color}
        onClose={() => setPicked(null)}
        onPlay={(slug) => {
          setPicked(null);
          onPlayLesson(slug);
        }}
        onDetails={(slug) => {
          setPicked(null);
          onOpenLesson(slug);
        }}
      />
    </View>
  );
}

function Stats({ discover, onStartReview }: { discover: DiscoverOut; onStartReview: () => void }) {
  const { colors } = useTheme();
  const { streak, xp, reviews_due: due } = discover;
  return (
    <View style={styles.stats}>
      <Stat
        icon="flame"
        color={streak.current > 0 ? colors.streak : colors.idleIcon}
        label={String(streak.current)}
        a11y={streakA11yLabel(discover)}
      />
      <Stat
        icon="flash"
        color={colors.xp}
        label={String(xp.today)}
        a11y={
          xp.today >= xp.goal
            ? strings.discover.goalReached
            : strings.discover.xpToday(xp.today, xp.goal)
        }
      />
      <Stat
        icon="bulb"
        color={due > 0 ? colors.accent : colors.idleIcon}
        label={String(due)}
        a11y={strings.path.dueChip(due)}
        onPress={due > 0 ? onStartReview : undefined}
      />
    </View>
  );
}

function Stat({
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
  return (
    <Pressable
      accessibilityRole={onPress ? "button" : "text"}
      accessibilityLabel={a11y}
      disabled={!onPress}
      onPress={onPress}
      style={styles.stat}
    >
      <Icon name={icon} color={color} size={22} />
      <Text variant="heading" importantForAccessibility="no">
        {label}
      </Text>
    </Pressable>
  );
}

function ReviewCard({ due, onStart }: { due: number; onStart: () => void }) {
  const { colors } = useTheme();
  return (
    <View style={[styles.review, { backgroundColor: colors.surface, borderColor: colors.accent }]}>
      <View style={styles.reviewRow}>
        <View style={[styles.reviewIcon, { backgroundColor: colors.accent }]}>
          <Icon name="bulb" color={colors.onAccent} size={26} />
        </View>
        <View style={styles.flexGap}>
          <Text variant="heading">{strings.path.reviewTitle}</Text>
          <Text>{strings.path.reviewBody(due)}</Text>
        </View>
      </View>
      <Button label={strings.path.reviewCta} onPress={onStart} />
    </View>
  );
}

function UnitHeader({ unit, color, icon }: { unit: PathUnit; color: UnitColor; icon: IconName }) {
  const total = unit.nodes.length;
  const done = unit.completed === total;
  return (
    <View
      accessibilityRole="header"
      accessible
      accessibilityLabel={`${strings.path.unit(unit.index + 1)}: ${unit.title}. ${strings.path.unitProgress(unit.completed, total)}`}
      style={[styles.unitHeader, { backgroundColor: color.fill, borderColor: color.edge }]}
    >
      <View style={styles.unitArt} pointerEvents="none">
        <View style={[styles.unitBlob, { backgroundColor: color.edge }]} />
        <View style={styles.unitArtIcon}>
          <Icon name={icon} color="rgba(255,255,255,0.35)" size={72} />
        </View>
        <View style={[styles.unitDot, { top: 14, right: 104 }]} />
        <View style={[styles.unitDot, styles.unitDotSmall, { top: 44, right: 92 }]} />
      </View>
      <View style={styles.unitTop}>
        <View style={[styles.unitChip, { backgroundColor: color.edge }]}>
          <Text variant="caption" style={styles.onFillCaps}>
            {strings.path.unit(unit.index + 1).toUpperCase()}
          </Text>
        </View>
        {done ? <Icon name="trophy" color="#FFFFFF" size={18} /> : null}
      </View>
      <Text variant="title" style={[styles.onFill, styles.unitTitle]}>
        {unit.title}
      </Text>
      <View style={styles.unitProgressRow}>
        <View style={[styles.unitTrack, { backgroundColor: color.edge }]}>
          <View
            style={[
              styles.unitFill,
              { width: `${total > 0 ? (unit.completed / total) * 100 : 0}%` },
            ]}
          />
        </View>
        <Text variant="caption" style={styles.onFill}>
          {unit.completed}/{total}
        </Text>
      </View>
    </View>
  );
}

/** Dotted trail between two nodes, lit once the learner has reached the next one. */
function Trail({
  from,
  to,
  lit,
  color,
}: {
  from: number;
  to: number;
  lit: boolean;
  color: UnitColor;
}) {
  const { colors } = useTheme();
  return (
    <View style={styles.trail} importantForAccessibility="no-hide-descendants">
      {[0.2, 0.5, 0.8].map((f) => (
        <View
          key={f}
          style={[
            styles.trailDot,
            {
              transform: [{ translateX: from + (to - from) * f }],
              backgroundColor: lit ? color.fill : colors.idleEdge,
            },
          ]}
        />
      ))}
    </View>
  );
}

/** A tilted subject icon beside the path, on the side the zigzag leaves empty. */
function Decoration({
  icon,
  color,
  side,
  tilt,
}: {
  icon: IconName;
  color: UnitColor;
  side: 1 | -1;
  tilt: number;
}) {
  return (
    <View
      pointerEvents="none"
      importantForAccessibility="no-hide-descendants"
      style={[
        styles.decor,
        side < 0 ? { right: NODE + 74 } : { left: NODE + 74 },
        { transform: [{ rotate: `${tilt}deg` }] },
      ]}
    >
      <View style={[styles.decorCircle, { backgroundColor: color.tint, borderColor: color.fill }]}>
        <Icon name={icon} color={color.fill} size={24} />
      </View>
      <View style={[styles.decorSpeck, { backgroundColor: color.fill, top: -4, right: -6 }]} />
      <View
        style={[
          styles.decorSpeck,
          styles.decorSpeckSmall,
          { backgroundColor: color.fill, bottom: 2, left: -8 },
        ]}
      />
    </View>
  );
}

/** Gentle up-and-down bounce for the current node's marker. */
function Bounce({ children }: { children: ReactNode }) {
  const reduced = useReducedMotion();
  const [y] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (reduced) return;
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(y, {
          toValue: -5,
          duration: 500,
          easing: Easing.out(Easing.quad),
          useNativeDriver: true,
        }),
        Animated.timing(y, {
          toValue: 0,
          duration: 500,
          easing: Easing.in(Easing.quad),
          useNativeDriver: true,
        }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [reduced, y]);
  return <Animated.View style={{ transform: [{ translateY: y }] }}>{children}</Animated.View>;
}

/** Three stars under a learned lesson: one per recall stage reached after learning it. */
function MasteryStars({ stage }: { stage: number }) {
  const { colors } = useTheme();
  const filled = Math.max(0, Math.min(3, stage - 1));
  return (
    <View style={styles.stars} importantForAccessibility="no-hide-descendants">
      {[0, 1, 2].map((i) => (
        <Icon
          key={i}
          name={i < filled ? "star" : "star-outline"}
          color={i < filled ? colors.xp : colors.idleIcon}
          size={13}
        />
      ))}
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
  const mastered = node.state === "done" && node.lesson.progress.mastery_stage >= 3;
  const lit = node.state !== "upcoming";
  const face = mastered ? colors.xp : lit ? color.fill : colors.idle;
  const rim = mastered ? "#C98500" : lit ? color.edge : colors.idleEdge;
  const label =
    strings.path.nodeLabel(node.lesson.title, strings.path.states[node.state]) +
    (node.state === "done"
      ? `, ${strings.lessons.mastery(node.lesson.progress.mastery_stage)}`
      : "");

  return (
    <View style={styles.nodeWrap}>
      {current ? (
        <Bounce>
          <View
            style={[styles.bubble, { backgroundColor: colors.surface, borderColor: color.fill }]}
          >
            <Text variant="label" style={{ color: colors.text }}>
              {(node.started ? strings.path.continue : strings.path.start).toUpperCase()}
            </Text>
          </View>
        </Bounce>
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
              borderBottomWidth: pressed ? 2 : edge + 3,
              marginTop: pressed ? edge + 1 : 0,
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
      {node.state === "done" ? <MasteryStars stage={node.lesson.progress.mastery_stage} /> : null}
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

/** Bottom sheet shown when a node is tapped: what the lesson is and how it works. */
function LessonSheet({
  picked,
  color,
  onClose,
  onPlay,
  onDetails,
}: {
  picked: Picked | null;
  color: UnitColor;
  onClose: () => void;
  onPlay: (slug: string) => void;
  onDetails: (slug: string) => void;
}) {
  const { colors } = useTheme();
  const insets = useSafeAreaInsets();
  const lesson = picked?.node.lesson;
  const card = strings.lessonCard;
  const status = !lesson
    ? ""
    : isLearned(lesson.progress)
      ? card.learned
      : lesson.progress.status === "started"
        ? card.inProgress
        : card.earnXp;

  return (
    <Modal visible={picked !== null} transparent animationType="slide" onRequestClose={onClose}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={card.close}
        onPress={onClose}
        style={styles.scrim}
      />
      {lesson && picked ? (
        <View
          accessibilityViewIsModal
          style={[
            styles.sheet,
            { backgroundColor: colors.surface, paddingBottom: spacing.xl + insets.bottom },
          ]}
        >
          <View style={[styles.grabber, { backgroundColor: colors.idleEdge }]} />
          <View style={styles.sheetHead}>
            <View
              style={[styles.sheetIcon, { backgroundColor: color.fill, borderColor: color.edge }]}
            >
              <Icon name={nodeIcon(picked.node)} color="#FFFFFF" size={36} />
            </View>
            <View style={styles.flexGap}>
              <Text variant="caption" tone="muted">
                {card.position(picked.position, picked.total).toUpperCase()}
              </Text>
              <Text variant="title" accessibilityRole="header">
                {lesson.title}
              </Text>
              <Text tone="muted">{lesson.description}</Text>
            </View>
          </View>
          <View style={styles.facts}>
            <Fact
              icon="time-outline"
              color={colors.accent}
              text={card.minutes(lesson.estimated_minutes)}
            />
            <Fact
              icon={isLearned(lesson.progress) ? "checkmark-circle" : "flash"}
              color={isLearned(lesson.progress) ? colors.success : colors.xp}
              text={status}
            />
          </View>
          <View style={[styles.inside, { backgroundColor: colors.surfaceMuted }]}>
            <Text variant="caption" tone="muted">
              {card.inside.toUpperCase()}
            </Text>
            {card.steps.map((step, i) => (
              <View key={step} style={styles.insideRow}>
                <View
                  style={[
                    styles.dot,
                    { backgroundColor: [color.fill, colors.xp, colors.success][i] },
                  ]}
                />
                <Text variant="label" style={styles.flex}>
                  {step}
                </Text>
              </View>
            ))}
          </View>
          <Button label={startLabel(lesson.progress)} onPress={() => onPlay(lesson.slug)} />
          <Button label={card.details} variant="ghost" onPress={() => onDetails(lesson.slug)} />
        </View>
      ) : null}
    </Modal>
  );
}

function Fact({ icon, color, text }: { icon: IconName; color: string; text: string }) {
  const { colors } = useTheme();
  return (
    <View style={[styles.fact, { borderColor: colors.border }]}>
      <Icon name={icon} color={color} size={22} />
      <Text variant="label">{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: spacing.xl },
  header: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  pill: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.xs,
    minHeight: 44,
    borderWidth: 2,
    borderBottomWidth: edge,
    borderRadius: radius.md,
    paddingHorizontal: spacing.sm,
  },
  pillIcon: {
    width: 26,
    height: 26,
    borderRadius: radius.full,
    alignItems: "center",
    justifyContent: "center",
  },
  flex: { flex: 1 },
  flexGap: { flex: 1, gap: spacing.xs },
  stats: { flexDirection: "row", gap: spacing.md },
  stat: { flexDirection: "row", alignItems: "center", gap: 2, minHeight: 44 },
  review: {
    borderWidth: 2,
    borderBottomWidth: edge,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.md,
  },
  reviewRow: { flexDirection: "row", gap: spacing.md, alignItems: "center" },
  reviewIcon: {
    width: 48,
    height: 48,
    borderRadius: radius.full,
    alignItems: "center",
    justifyContent: "center",
  },
  unit: { gap: spacing.xl },
  unitHeader: {
    borderRadius: radius.lg,
    borderBottomWidth: edge + 2,
    padding: spacing.lg,
    gap: spacing.sm,
    overflow: "hidden",
  },
  unitArt: { position: "absolute", top: 0, right: 0, bottom: 0, left: 0 },
  unitBlob: {
    position: "absolute",
    right: -30,
    top: -30,
    width: 140,
    height: 140,
    borderRadius: radius.full,
    opacity: 0.6,
  },
  unitArtIcon: { position: "absolute", right: 10, top: 12, transform: [{ rotate: "12deg" }] },
  unitDot: {
    position: "absolute",
    width: 10,
    height: 10,
    borderRadius: radius.full,
    backgroundColor: "rgba(255,255,255,0.45)",
  },
  unitDotSmall: { width: 6, height: 6 },
  unitTop: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  unitChip: { borderRadius: radius.full, paddingHorizontal: spacing.sm, paddingVertical: 2 },
  unitTitle: { maxWidth: "78%" },
  unitProgressRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  unitTrack: { flex: 1, height: 10, borderRadius: radius.full, overflow: "hidden" },
  unitFill: { height: 10, borderRadius: radius.full, backgroundColor: "#FFFFFF" },
  onFill: { color: "#FFFFFF" },
  onFillCaps: { color: "#FFFFFF", letterSpacing: 1 },
  nodes: { alignItems: "center" },
  trail: { height: 34, width: "100%", alignItems: "center", justifyContent: "space-evenly" },
  trailDot: { width: 10, height: 10, borderRadius: radius.full },
  decor: { position: "absolute", top: 26 },
  decorCircle: {
    width: 50,
    height: 50,
    borderRadius: radius.full,
    borderWidth: 2,
    alignItems: "center",
    justifyContent: "center",
  },
  decorSpeck: {
    position: "absolute",
    width: 8,
    height: 8,
    borderRadius: radius.full,
    opacity: 0.5,
  },
  decorSpeckSmall: { width: 5, height: 5 },
  stars: { flexDirection: "row", gap: 2 },
  nodeWrap: { alignItems: "center", width: 150, gap: spacing.xs },
  nodeHolder: {
    width: NODE + 24,
    height: NODE + 24,
    alignItems: "center",
    justifyContent: "center",
  },
  node: {
    width: NODE,
    height: NODE,
    borderRadius: radius.full,
    alignItems: "center",
    justifyContent: "center",
  },
  pulse: { position: "absolute", width: NODE + 20, height: NODE + 20, borderRadius: radius.full },
  bubble: {
    borderWidth: 2,
    borderBottomWidth: edge,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.md,
    paddingVertical: 2,
  },
  guide: { position: "absolute", top: 20, width: 110, alignItems: "center", gap: spacing.xs },
  guideBubble: {
    borderWidth: 2,
    borderRadius: radius.sm,
    paddingHorizontal: spacing.sm,
    paddingVertical: 4,
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
  scrim: { flex: 1, backgroundColor: "rgba(23, 15, 52, 0.45)" },
  sheet: {
    borderTopLeftRadius: radius.lg + 4,
    borderTopRightRadius: radius.lg + 4,
    paddingHorizontal: spacing.xl,
    paddingTop: spacing.sm,
    gap: spacing.md,
  },
  grabber: { alignSelf: "center", width: 44, height: 5, borderRadius: radius.full },
  sheetHead: { flexDirection: "row", gap: spacing.md, alignItems: "center" },
  sheetIcon: {
    width: 76,
    height: 76,
    borderRadius: radius.lg,
    borderBottomWidth: edge + 2,
    alignItems: "center",
    justifyContent: "center",
  },
  facts: { flexDirection: "row", gap: spacing.sm },
  fact: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: spacing.xs,
    borderWidth: 2,
    borderBottomWidth: edge,
    borderRadius: radius.md,
    paddingVertical: spacing.sm,
  },
  inside: { borderRadius: radius.md, padding: spacing.md, gap: spacing.sm },
  insideRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  dot: { width: 10, height: 10, borderRadius: radius.full },
});
