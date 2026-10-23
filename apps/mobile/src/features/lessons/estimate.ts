/** Estimate slider maths (D-18). Pure display helpers: the server does the grading. */

export type EstimateConfig = { min: number; max: number; step: number };

/** Snap a raw value to the step grid inside the range. */
export function snap(raw: number, { min, max, step }: EstimateConfig): number {
  const clamped = Math.min(Math.max(raw, min), max);
  const snapped = min + Math.round((clamped - min) / step) * step;
  const decimals = (String(step).split(".")[1] ?? "").length;
  return Number(Math.min(snapped, max).toFixed(decimals));
}

/** Position of a value along the track, 0..1. */
export function fraction(value: number, { min, max }: EstimateConfig): number {
  return max > min ? (Math.min(Math.max(value, min), max) - min) / (max - min) : 0;
}

/** Value under a touch at x pixels along a track of the given width. */
export function valueAt(x: number, width: number, config: EstimateConfig): number {
  if (width <= 0) return config.min;
  return snap(config.min + (x / width) * (config.max - config.min), config);
}

/** A screen-reader step: about a twentieth of the range, on the step grid. */
export function a11yStep({ min, max, step }: EstimateConfig): number {
  return Math.max(step, Math.round((max - min) / 20 / step) * step);
}

/** 3700 -> "3,700"; keeps up to two decimals. */
export function formatNumber(n: number): string {
  const [whole, decimals] = String(Math.round(n * 100) / 100).split(".");
  const sign = whole!.startsWith("-") ? "-" : "";
  const digits = whole!.replace("-", "").replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${sign}${digits}${decimals ? `.${decimals}` : ""}`;
}

/** The first, middle value a slider starts on. */
export function startValue(config: EstimateConfig): number {
  return snap((config.min + config.max) / 2, config);
}
