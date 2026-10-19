import type { ExpoConfig } from "expo/config";

// Name and identifiers come from the environment so branding can change later
// (docs/spec/01 §1.1). Bundle ids are placeholders until the first store submission.
const config: ExpoConfig = {
  name: process.env.APP_DISPLAY_NAME ?? "Curiosity",
  slug: "curiosity",
  scheme: "curiosity",
  version: "1.0.0",
  orientation: "portrait",
  icon: "./assets/icon.png",
  userInterfaceStyle: "automatic",
  ios: {
    supportsTablet: false, // phones only in the MVP (D-10)
    bundleIdentifier: process.env.IOS_BUNDLE_ID ?? "app.curiosity.dev",
  },
  android: {
    package: process.env.ANDROID_PACKAGE ?? "app.curiosity.dev",
    adaptiveIcon: {
      backgroundColor: "#FAF7F2",
      foregroundImage: "./assets/android-icon-foreground.png",
      backgroundImage: "./assets/android-icon-background.png",
      monochromeImage: "./assets/android-icon-monochrome.png",
    },
    predictiveBackGestureEnabled: false,
  },
  plugins: [
    "expo-router",
    "expo-secure-store",
    "expo-font",
    "expo-localization",
    [
      "expo-splash-screen",
      {
        image: "./assets/splash-icon.png",
        imageWidth: 160,
        backgroundColor: "#FAF7F2",
        dark: { backgroundColor: "#14130F" },
      },
    ],
  ],
  experiments: { typedRoutes: true },
};

export default config;
