/**
 * Shared delta formatter for current-vs-previous-window comparisons.
 *
 * Used by chart/render modules (admin metrics summary cards, top-events
 * tables) that display a percent delta with an arrow glyph and direction
 * class. Returns a placeholder when the previous-window count is zero so
 * callers don't divide by zero or display meaningless "+Infinity%" badges.
 */

import { APP_CONFIG } from "../config.js";

export type DeltaDirection = "up" | "down" | "flat" | "none";

export function formatDelta({
  current,
  previous,
}: {
  current: number;
  previous: number;
}): { text: string; direction: DeltaDirection } {
  if (previous === 0) {
    return {
      text: APP_CONFIG.strings.METRICS_SUMMARY_DELTA_UNAVAILABLE,
      direction: "none",
    };
  }
  const deltaFraction = (current - previous) / previous;
  const absolutePercent = `${Math.abs(deltaFraction * 100).toFixed(1)}%`;
  if (deltaFraction > 0) {
    return { text: `▲ ${absolutePercent}`, direction: "up" };
  }
  if (deltaFraction < 0) {
    return { text: `▼ ${absolutePercent}`, direction: "down" };
  }
  return { text: `— ${absolutePercent}`, direction: "flat" };
}
