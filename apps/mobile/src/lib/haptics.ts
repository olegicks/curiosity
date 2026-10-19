import * as Haptics from "expo-haptics";

/** Haptics are a nicety: failures (unsupported device, tests) are ignored. */
function safely(run: () => Promise<void> | void): void {
  try {
    void Promise.resolve(run()).catch(() => undefined);
  } catch {
    // ignore
  }
}

export const haptics = {
  select: () => safely(() => Haptics.selectionAsync()),
  result: (correct: boolean) =>
    safely(() =>
      Haptics.notificationAsync(
        correct
          ? Haptics.NotificationFeedbackType.Success
          : Haptics.NotificationFeedbackType.Warning,
      ),
    ),
};
