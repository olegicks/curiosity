import AsyncStorage from "@react-native-async-storage/async-storage";
import { useEffect, useState } from "react";
import { Modal, Pressable, StyleSheet, View } from "react-native";

import { strings } from "@/i18n/en";
import { Mascot, type MascotMood } from "@/ui/Mascot";
import { Text } from "@/ui/Text";
import { useTheme } from "@/ui/theme";
import { edge, radius, spacing, unitColor } from "@/ui/tokens";

const STORAGE_KEY = "tour-done";
const MOODS: MascotMood[] = ["happy", "cheer", "think"];

/** Shows the tour once per device. Storage failures skip it rather than nag. */
export function useTour(): { visible: boolean; finish: () => void } {
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    let active = true;
    AsyncStorage.getItem(STORAGE_KEY)
      .then((done) => {
        if (active && !done) setVisible(true);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);
  return {
    visible,
    finish: () => {
      setVisible(false);
      AsyncStorage.setItem(STORAGE_KEY, "1").catch(() => undefined);
    },
  };
}

/** First-run tour (D-17): what the path is, how XP and streaks work, why recall matters. */
export function Tour({ visible, onDone }: { visible: boolean; onDone: () => void }) {
  const { colors } = useTheme();
  const [step, setStep] = useState(0);
  const steps = strings.tour.steps;
  const current = steps[step]!;
  const last = step === steps.length - 1;

  const finish = () => {
    setStep(0);
    onDone();
  };

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={finish}>
      <View style={styles.scrim}>
        <View
          accessibilityViewIsModal
          accessibilityLabel={strings.tour.step(step + 1, steps.length)}
          style={[styles.card, { backgroundColor: colors.surface, borderColor: colors.border }]}
        >
          <View style={styles.head}>
            <Mascot size={60} mood={MOODS[step]} />
            <View style={styles.flex}>
              <Text variant="title" accessibilityRole="header">
                {current.title}
              </Text>
              <Text>{current.body}</Text>
            </View>
          </View>
          {step === 0 ? (
            <View style={styles.loop}>
              {strings.tour.loop.map((line, i) => (
                <View key={line} style={styles.loopRow}>
                  <View style={[styles.number, { backgroundColor: unitColor(i).fill }]}>
                    <Text variant="label" style={styles.white}>
                      {i + 1}
                    </Text>
                  </View>
                  <Text variant="label" style={styles.flex}>
                    {line}
                  </Text>
                </View>
              ))}
            </View>
          ) : null}
          <View style={styles.footer}>
            <View style={styles.dots} importantForAccessibility="no-hide-descendants">
              {steps.map((s, i) => (
                <View
                  key={s.title}
                  style={[
                    styles.dot,
                    i === step
                      ? { width: 22, backgroundColor: colors.accent }
                      : { backgroundColor: colors.idle },
                  ]}
                />
              ))}
            </View>
            <View style={styles.actions}>
              {!last ? (
                <Pressable accessibilityRole="button" onPress={finish} style={styles.skip}>
                  <Text variant="label" tone="accent">
                    {strings.tour.skip}
                  </Text>
                </Pressable>
              ) : null}
              <Pressable
                accessibilityRole="button"
                onPress={() => (last ? finish() : setStep(step + 1))}
                style={({ pressed }) => [
                  styles.next,
                  {
                    backgroundColor: colors.accent,
                    borderColor: colors.accentEdge,
                    borderBottomWidth: pressed ? 0 : edge,
                    marginTop: pressed ? edge : 0,
                  },
                ]}
              >
                <Text variant="label" style={{ color: colors.onAccent }}>
                  {(last ? strings.tour.done : strings.tour.next).toUpperCase()}
                </Text>
              </Pressable>
            </View>
          </View>
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  scrim: {
    flex: 1,
    backgroundColor: "rgba(23, 15, 52, 0.72)",
    justifyContent: "center",
    padding: spacing.lg,
  },
  card: {
    borderWidth: 2,
    borderBottomWidth: edge + 2,
    borderRadius: radius.lg,
    padding: spacing.lg,
    gap: spacing.md,
  },
  head: { flexDirection: "row", gap: spacing.md, alignItems: "flex-start" },
  flex: { flex: 1, gap: spacing.xs },
  loop: { gap: spacing.sm },
  loopRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  number: {
    width: 28,
    height: 28,
    borderRadius: radius.full,
    alignItems: "center",
    justifyContent: "center",
  },
  white: { color: "#FFFFFF" },
  footer: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  dots: { flexDirection: "row", gap: 6 },
  dot: { width: 8, height: 8, borderRadius: radius.full },
  actions: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  skip: { minHeight: 44, justifyContent: "center", paddingHorizontal: spacing.sm },
  next: {
    minHeight: 44,
    justifyContent: "center",
    borderRadius: radius.md,
    paddingHorizontal: spacing.xl,
  },
});
