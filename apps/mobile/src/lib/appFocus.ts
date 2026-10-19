import { focusManager } from "@tanstack/react-query";
import { useEffect } from "react";
import { AppState, type AppStateStatus } from "react-native";

/**
 * Tell TanStack Query when the app is foregrounded, so stale queries (Discover,
 * reviews due) refetch on return, including after midnight (FR-DISC-2).
 */
export function useAppStateFocus(): void {
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (status: AppStateStatus) => {
      focusManager.setFocused(status === "active");
    });
    return () => subscription.remove();
  }, []);
}
