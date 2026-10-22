import { File, Paths } from "expo-file-system";
import * as Sharing from "expo-sharing";

import { toDay } from "@/features/reviews/recall";

export function exportFileName(now: Date): string {
  return `curiosity-export-${toDay(now)}.json`;
}

/**
 * Write the export to the cache directory and open the OS share sheet.
 * Returns false when sharing isn't available on the device.
 */
export async function shareExport(data: unknown, now: Date): Promise<boolean> {
  if (!(await Sharing.isAvailableAsync())) return false;
  const file = new File(Paths.cache, exportFileName(now));
  file.create({ overwrite: true });
  await file.write(JSON.stringify(data, null, 2));
  await Sharing.shareAsync(file.uri, { mimeType: "application/json", UTI: "public.json" });
  return true;
}
