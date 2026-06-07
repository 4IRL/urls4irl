/**
 * Render a single category's current/previous totals into a panel's summary
 * `<div>`. Pure DOM mutation; no fetching, no event binding.
 *
 * The percent-change calculation falls back to a placeholder ("—") when the
 * previous-window count is zero so we don't divide by zero or display
 * meaningless "+Infinity%" badges.
 */

import type { Schema } from "../types/api-helpers.d.ts";

type SummaryResponseSchema = Schema<"SummaryResponseSchema">;
type MetricsCategory = "api" | "ui" | "domain";

const PERCENT_CHANGE_UNAVAILABLE_PLACEHOLDER = "—";

/**
 * Format the percent-change badge text for a current/previous pair.
 *
 * Examples:
 *   formatPercentChange({ current: 150, previous: 100 }) -> "+50.0%"
 *   formatPercentChange({ current: 80, previous: 100 })  -> "-20.0%"
 *   formatPercentChange({ current: 42, previous: 0 })    -> "—" (cannot divide)
 *   formatPercentChange({ current: 0, previous: 0 })     -> "—" (no signal)
 */
function formatPercentChange({
  current,
  previous,
}: {
  current: number;
  previous: number;
}): string {
  if (previous === 0) {
    return PERCENT_CHANGE_UNAVAILABLE_PLACEHOLDER;
  }
  const deltaFraction = (current - previous) / previous;
  const signPrefix = deltaFraction >= 0 ? "+" : "";
  return `${signPrefix}${(deltaFraction * 100).toFixed(1)}%`;
}

export function renderSummary({
  root,
  response,
  category,
}: {
  root: HTMLElement;
  response: SummaryResponseSchema;
  category: MetricsCategory;
}): void {
  const categoryRow = response.by_category.find(
    (entry) => entry.category === category,
  );
  const currentCount = categoryRow?.current ?? 0;
  const previousCount = categoryRow?.previous ?? 0;

  const formattedCount = currentCount.toLocaleString();
  const formattedChange = formatPercentChange({
    current: currentCount,
    previous: previousCount,
  });

  // Clear and rebuild the summary content. Two `<span>` elements so the count
  // and percent-change badge can be styled independently.
  while (root.firstChild !== null) {
    root.removeChild(root.firstChild);
  }

  const countElement = document.createElement("span");
  countElement.className = "MetricsSummaryCount";
  countElement.textContent = formattedCount;

  const changeElement = document.createElement("span");
  changeElement.className = "MetricsSummaryChange";
  changeElement.textContent = formattedChange;

  root.appendChild(countElement);
  root.appendChild(changeElement);
}
