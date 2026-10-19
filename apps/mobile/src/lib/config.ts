import Constants from "expo-constants";
import { getCalendars } from "expo-localization";
import { Platform } from "react-native";

/** API base URL, inlined at build time from EXPO_PUBLIC_API_URL (non-secret). */
export const API_URL = (process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000").replace(
  /\/$/,
  "",
);

export const APP_VERSION = Constants.expoConfig?.version ?? "1.0.0";

export const PLATFORM = Platform.OS;

/** The device's IANA timezone, used for streaks and due dates. */
export function deviceTimezone(): string | null {
  try {
    return getCalendars()[0]?.timeZone ?? Intl.DateTimeFormat().resolvedOptions().timeZone ?? null;
  } catch {
    return null;
  }
}
