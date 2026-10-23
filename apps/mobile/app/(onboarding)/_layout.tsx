import { Stack } from "expo-router";

export const unstable_settings = { initialRouteName: "subject" };

export default function Layout() {
  return <Stack screenOptions={{ headerShown: false }} />;
}
