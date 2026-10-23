import { Pressable, StyleSheet, View } from "react-native";

import { strings } from "@/i18n/en";
import { Icon } from "@/ui/Icon";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { edge, radius, spacing } from "@/ui/tokens";

import { isComingSoon, lessonCount, type Subject, subjectLook } from "./subjects";

type Props = { subjects: Subject[]; selected: string | null; onSelect: (slug: string) => void };

/** Subject cards: two columns of open subjects, then a row per "coming soon" subject. */
export function SubjectGrid({ subjects, selected, onSelect }: Props) {
  const { colors } = useTheme();
  const open = subjects.filter((s) => !isComingSoon(s));
  const soon = subjects.filter(isComingSoon);
  return (
    <View style={styles.stack}>
      <View style={styles.grid} accessibilityRole="radiogroup">
        {open.map((subject) => {
          const index = subjects.indexOf(subject);
          const { color, icon } = subjectLook(subject.slug, index);
          const active = subject.slug === selected;
          const count = lessonCount(subject);
          return (
            <Pressable
              key={subject.slug}
              accessibilityRole="radio"
              accessibilityState={{ checked: active }}
              accessibilityLabel={`${subject.title}. ${subject.description} ${strings.subjects.lessons(count)}`}
              onPress={() => onSelect(subject.slug)}
              style={({ pressed }) => [
                styles.card,
                {
                  backgroundColor: colors.surface,
                  borderColor: active ? color.fill : colors.border,
                  borderBottomWidth: pressed ? 3 : edge + 3,
                  marginTop: pressed ? edge : 0,
                },
              ]}
            >
              {active ? (
                <View style={[styles.check, { backgroundColor: color.fill }]}>
                  <Icon name="checkmark" color="#FFFFFF" size={16} />
                </View>
              ) : null}
              <View style={[styles.art, { backgroundColor: color.fill, borderColor: color.edge }]}>
                <Icon name={icon} color="#FFFFFF" size={34} />
              </View>
              <Text variant="heading">{subject.title}</Text>
              <Text variant="caption" tone="muted" numberOfLines={2}>
                {subject.description}
              </Text>
              <Text variant="caption" tone="muted">
                {strings.subjects.lessons(count)}
              </Text>
            </Pressable>
          );
        })}
      </View>
      {soon.map((subject) => (
        <View
          key={subject.slug}
          accessible
          accessibilityLabel={`${subject.title}, ${strings.subjects.soonLabel}`}
          style={[styles.soon, { borderColor: colors.idleEdge, backgroundColor: colors.surface }]}
        >
          <View style={[styles.soonIcon, { backgroundColor: colors.idle }]}>
            <Icon name="business" color={colors.idleIcon} size={22} />
          </View>
          <View style={styles.flex}>
            <Text variant="heading">{subject.title}</Text>
            <Text variant="caption" tone="muted">
              {subject.description}
            </Text>
          </View>
          <View style={[styles.badge, { backgroundColor: colors.idle }]}>
            <Text variant="caption" tone="muted">
              {strings.subjects.soon.toUpperCase()}
            </Text>
          </View>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  stack: { gap: spacing.md },
  grid: { flexDirection: "row", flexWrap: "wrap", gap: spacing.md },
  card: {
    flexBasis: "46%",
    flexGrow: 1,
    borderWidth: 3,
    borderRadius: radius.lg,
    padding: spacing.md,
    gap: spacing.xs,
  },
  check: {
    position: "absolute",
    top: spacing.sm,
    right: spacing.sm,
    width: 26,
    height: 26,
    borderRadius: radius.full,
    alignItems: "center",
    justifyContent: "center",
  },
  art: {
    width: 60,
    height: 60,
    borderRadius: radius.full,
    borderBottomWidth: edge,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: spacing.xs,
  },
  soon: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    borderWidth: 2,
    borderStyle: "dashed",
    borderRadius: radius.md,
    padding: spacing.md,
  },
  soonIcon: {
    width: 40,
    height: 40,
    borderRadius: radius.full,
    alignItems: "center",
    justifyContent: "center",
  },
  badge: { borderRadius: radius.full, paddingHorizontal: spacing.sm, paddingVertical: 2 },
  flex: { flex: 1 },
});
