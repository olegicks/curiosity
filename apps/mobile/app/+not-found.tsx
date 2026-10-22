import { Redirect } from "expo-router";

import { useAuth } from "@/features/auth/AuthProvider";
import { homeFor, routeFor } from "@/features/auth/session";

/**
 * Paths outside the current group's guard resolve here, e.g. Expo Go opening "/" while
 * signed out (the tabs are protected and the auth group has no index). Send the user to
 * the start of the group they are allowed to see.
 */
export default function NotFound() {
  const { session } = useAuth();
  const home = homeFor(routeFor(session));
  return home ? <Redirect href={home} /> : null;
}
