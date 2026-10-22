import Ionicons from "@expo/vector-icons/Ionicons";
import type { ComponentProps } from "react";

export type IconName = ComponentProps<typeof Ionicons>["name"];

/** Decorative icon. Meaning is always carried by nearby text or an accessibility label. */
export function Icon({ name, size = 22, color }: { name: IconName; size?: number; color: string }) {
  return (
    <Ionicons
      name={name}
      size={size}
      color={color}
      accessible={false}
      importantForAccessibility="no-hide-descendants"
    />
  );
}
