import { StyleSheet, View } from "react-native";

export type MascotMood = "happy" | "cheer" | "think";

const INK = "#1D1640";
const BODY = "#6340E0";
const BULB = "#FFC233";
const CHEEK = "#F28CB1";

/**
 * Spark, the guide (D-17 mockups): a round character drawn with plain views, so it
 * needs no image assets. Decorative: meaning always comes from nearby text.
 */
export function Mascot({ size = 64, mood = "happy" }: { size?: number; mood?: MascotMood }) {
  const u = size / 64; // one design unit
  const eye = 15 * u;
  const pupil = 7 * u;
  const pupilShift = mood === "think" ? -3 * u : 1.5 * u;
  const outline = Math.max(2, 3 * u);

  return (
    <View
      accessible={false}
      importantForAccessibility="no-hide-descendants"
      style={{ width: size, height: size * 1.1 }}
    >
      {mood === "cheer" ? (
        <>
          <View
            style={[
              styles.arm,
              {
                left: -2 * u,
                top: 30 * u,
                width: 18 * u,
                height: outline,
                transform: [{ rotate: "-50deg" }],
              },
            ]}
          />
          <View
            style={[
              styles.arm,
              {
                right: -2 * u,
                top: 30 * u,
                width: 18 * u,
                height: outline,
                transform: [{ rotate: "50deg" }],
              },
            ]}
          />
        </>
      ) : null}
      <View
        style={[styles.antenna, { left: 31 * u, top: 6 * u, width: outline, height: 12 * u }]}
      />
      <View
        style={[
          styles.bulb,
          { left: 26 * u, top: 0, width: 12 * u, height: 12 * u, borderWidth: outline * 0.8 },
        ]}
      />
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
        <View style={[styles.eyes, { marginTop: 12 * u, gap: 6 * u }]}>
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
                />
              )}
            </View>
          ))}
        </View>
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
    </View>
  );
}

const styles = StyleSheet.create({
  arm: { position: "absolute", backgroundColor: INK, borderRadius: 4 },
  antenna: { position: "absolute", backgroundColor: INK, borderRadius: 2 },
  bulb: { position: "absolute", backgroundColor: BULB, borderColor: INK, borderRadius: 999 },
  body: { position: "absolute", backgroundColor: BODY, borderColor: INK, alignItems: "center" },
  eyes: { flexDirection: "row" },
  eye: { backgroundColor: "#FFFFFF", alignItems: "center", justifyContent: "center" },
  pupil: { backgroundColor: INK },
  face: { flexDirection: "row", alignItems: "center" },
  cheek: { backgroundColor: CHEEK },
  smile: { borderColor: INK },
  openMouth: { backgroundColor: INK },
});
