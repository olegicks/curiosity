import { useEffect, useState } from "react";
import { Animated, Easing, StyleSheet, View } from "react-native";

import { useReducedMotion } from "@/lib/motion";

export type MascotMood = "happy" | "cheer" | "think";

const INK = "#1D1640";
const BODY = "#6340E0";
const BELLY = "#7F62F0";
const BULB = "#FFC233";
const CHEEK = "#F28CB1";

const loop = (steps: Animated.CompositeAnimation[]) => Animated.loop(Animated.sequence(steps));
const ease = Easing.inOut(Easing.sin);

/** Breathing bob, blinking eyes and a glowing bulb; all still when motion is reduced. */
function useMotion(mood: MascotMood, still: boolean) {
  const [bob] = useState(() => new Animated.Value(0));
  const [blink] = useState(() => new Animated.Value(1));
  const [glow] = useState(() => new Animated.Value(0));
  const [wave] = useState(() => new Animated.Value(0));

  useEffect(() => {
    if (still) return;
    const hop = mood === "cheer";
    const animations = [
      loop([
        Animated.timing(bob, {
          toValue: 1,
          duration: hop ? 420 : 1400,
          easing: ease,
          useNativeDriver: true,
        }),
        Animated.timing(bob, {
          toValue: 0,
          duration: hop ? 420 : 1400,
          easing: ease,
          useNativeDriver: true,
        }),
      ]),
      loop([
        Animated.delay(2800),
        Animated.timing(blink, { toValue: 0.1, duration: 80, useNativeDriver: true }),
        Animated.timing(blink, { toValue: 1, duration: 110, useNativeDriver: true }),
      ]),
      loop([
        Animated.timing(glow, { toValue: 1, duration: 1100, easing: ease, useNativeDriver: true }),
        Animated.timing(glow, { toValue: 0, duration: 1100, easing: ease, useNativeDriver: true }),
      ]),
      loop([
        Animated.timing(wave, { toValue: 1, duration: 300, easing: ease, useNativeDriver: true }),
        Animated.timing(wave, { toValue: 0, duration: 300, easing: ease, useNativeDriver: true }),
      ]),
    ];
    animations.forEach((a) => a.start());
    return () => animations.forEach((a) => a.stop());
  }, [blink, bob, glow, mood, still, wave]);

  return { bob, blink, glow, wave };
}

/**
 * Spark, the guide (D-17 mockups): a round character drawn with plain views, so it
 * needs no image assets. Decorative: meaning always comes from nearby text.
 */
export function Mascot({
  size = 64,
  mood = "happy",
  animated = true,
}: {
  size?: number;
  mood?: MascotMood;
  animated?: boolean;
}) {
  const reduced = useReducedMotion();
  const { bob, blink, glow, wave } = useMotion(mood, reduced || !animated);
  const u = size / 64; // one design unit
  const eye = 15 * u;
  const pupil = 7 * u;
  const pupilShift = mood === "think" ? -3 * u : 1.5 * u;
  const outline = Math.max(2, 3 * u);
  const lift = bob.interpolate({
    inputRange: [0, 1],
    outputRange: [0, (mood === "cheer" ? -7 : -3) * u],
  });
  const shadow = bob.interpolate({ inputRange: [0, 1], outputRange: [1, 0.8] });
  const halo = glow.interpolate({ inputRange: [0, 1], outputRange: [0.15, 0.6] });
  const haloScale = glow.interpolate({ inputRange: [0, 1], outputRange: [1, 1.5] });
  const armSwing = (sign: 1 | -1) =>
    wave.interpolate({
      inputRange: [0, 1],
      outputRange: [`${sign * 50}deg`, `${sign * 70}deg`],
    });

  return (
    <View
      accessible={false}
      importantForAccessibility="no-hide-descendants"
      style={{ width: size, height: size * 1.18 }}
    >
      <Animated.View
        style={[
          styles.shadow,
          {
            left: 14 * u,
            top: 66 * u,
            width: 36 * u,
            height: 6 * u,
            borderRadius: 6 * u,
            transform: [{ scaleX: shadow }],
          },
        ]}
      />
      <Animated.View style={[StyleSheet.absoluteFill, { transform: [{ translateY: lift }] }]}>
        {mood === "cheer" ? (
          <>
            <Animated.View
              style={[
                styles.arm,
                {
                  left: -2 * u,
                  top: 30 * u,
                  width: 18 * u,
                  height: outline,
                  transform: [{ rotate: armSwing(-1) }],
                },
              ]}
            />
            <Animated.View
              style={[
                styles.arm,
                {
                  right: -2 * u,
                  top: 30 * u,
                  width: 18 * u,
                  height: outline,
                  transform: [{ rotate: armSwing(1) }],
                },
              ]}
            />
          </>
        ) : null}
        <View
          style={[styles.antenna, { left: 31 * u, top: 6 * u, width: outline, height: 12 * u }]}
        />
        <Animated.View
          style={[
            styles.halo,
            {
              left: 23 * u,
              top: -3 * u,
              width: 18 * u,
              height: 18 * u,
              opacity: halo,
              transform: [{ scale: haloScale }],
            },
          ]}
        />
        <View
          style={[
            styles.bulb,
            { left: 26 * u, top: 0, width: 12 * u, height: 12 * u, borderWidth: outline * 0.8 },
          ]}
        >
          <View
            style={[styles.shine, { width: 3 * u, height: 3 * u, top: 1.5 * u, left: 2 * u }]}
          />
        </View>
        <View
          style={[
            styles.body,
            {
              left: 6 * u,
              top: 17 * u,
              width: 52 * u,
              height: 48 * u,
              borderRadius: 26 * u,
              borderWidth: outline,
            },
          ]}
        >
          <View
            style={[
              styles.belly,
              { width: 28 * u, height: 14 * u, borderRadius: 14 * u, bottom: 3 * u },
            ]}
          />
          <View
            style={[
              styles.gloss,
              { width: 10 * u, height: 6 * u, borderRadius: 6 * u, top: 5 * u, left: 8 * u },
            ]}
          />
          <Animated.View
            style={[
              styles.eyes,
              {
                marginTop: 12 * u,
                gap: 6 * u,
                transform: [{ scaleY: mood === "cheer" ? 1 : blink }],
              },
            ]}
          >
            {[0, 1].map((i) => (
              <View
                key={i}
                style={[
                  styles.eye,
                  { width: eye, height: mood === "cheer" ? eye * 0.55 : eye, borderRadius: eye },
                ]}
              >
                {mood === "cheer" ? null : (
                  <View
                    style={[
                      styles.pupil,
                      {
                        width: pupil,
                        height: pupil,
                        borderRadius: pupil,
                        transform: [{ translateY: pupilShift }, { translateX: 1.5 * u }],
                      },
                    ]}
                  >
                    <View
                      style={[
                        styles.spark,
                        { width: 2.4 * u, height: 2.4 * u, top: 1 * u, left: 1.2 * u },
                      ]}
                    />
                  </View>
                )}
              </View>
            ))}
          </Animated.View>
          <View style={[styles.face, { marginTop: 3 * u, gap: 18 * u }]}>
            <View style={[styles.cheek, { width: 7 * u, height: 4 * u, borderRadius: 4 * u }]} />
            <View
              style={
                mood === "cheer"
                  ? [
                      styles.openMouth,
                      {
                        width: 16 * u,
                        height: 9 * u,
                        borderBottomLeftRadius: 9 * u,
                        borderBottomRightRadius: 9 * u,
                      },
                    ]
                  : [
                      styles.smile,
                      {
                        width: 14 * u,
                        height: 7 * u,
                        borderBottomWidth: outline,
                        borderBottomLeftRadius: 8 * u,
                        borderBottomRightRadius: 8 * u,
                      },
                    ]
              }
            />
            <View style={[styles.cheek, { width: 7 * u, height: 4 * u, borderRadius: 4 * u }]} />
          </View>
        </View>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  shadow: { position: "absolute", backgroundColor: "rgba(29, 22, 64, 0.18)" },
  arm: { position: "absolute", backgroundColor: INK, borderRadius: 4 },
  antenna: { position: "absolute", backgroundColor: INK, borderRadius: 2 },
  halo: { position: "absolute", backgroundColor: BULB, borderRadius: 999 },
  bulb: { position: "absolute", backgroundColor: BULB, borderColor: INK, borderRadius: 999 },
  shine: { position: "absolute", backgroundColor: "#FFFFFF", borderRadius: 999 },
  body: {
    position: "absolute",
    backgroundColor: BODY,
    borderColor: INK,
    alignItems: "center",
    overflow: "hidden",
  },
  belly: { position: "absolute", backgroundColor: BELLY },
  gloss: { position: "absolute", backgroundColor: "rgba(255, 255, 255, 0.28)" },
  eyes: { flexDirection: "row" },
  eye: { backgroundColor: "#FFFFFF", alignItems: "center", justifyContent: "center" },
  pupil: { backgroundColor: INK },
  spark: { position: "absolute", backgroundColor: "#FFFFFF", borderRadius: 999 },
  face: { flexDirection: "row", alignItems: "center" },
  cheek: { backgroundColor: CHEEK },
  smile: { borderColor: INK },
  openMouth: { backgroundColor: INK },
});
