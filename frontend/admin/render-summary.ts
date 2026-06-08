/**
 * Render the four-card summary grid into `#MetricsSummaryGrid`. Pure DOM
 * mutation; no fetching, no event binding.
 *
 * The percent-change calculation falls back to a placeholder ("—") when the
 * previous-window count is zero so we don't divide by zero or display
 * meaningless "+Infinity%" badges.
 */

import type { Schema } from "../types/api-helpers.d.ts";

import { APP_CONFIG } from "../lib/config.js";

type SummaryResponseSchema = Schema<"SummaryResponseSchema">;
type MetricsCategory = "api" | "ui" | "domain";

type DeltaDirection = "up" | "down" | "flat" | "none";

type SummaryCard = {
  label: string;
  current: number;
  previous: number;
};

const CATEGORY_LABEL_KEYS: Record<MetricsCategory, string> = {
  api: "METRICS_SUMMARY_API_HITS",
  ui: "METRICS_SUMMARY_UI_EVENTS",
  domain: "METRICS_SUMMARY_DOMAIN_ACTIONS",
};

const CATEGORY_ORDER: readonly MetricsCategory[] = ["api", "ui", "domain"];

function formatDelta({
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

function buildCard({ label, current, previous }: SummaryCard): HTMLDivElement {
  const card = document.createElement("div");
  card.className = "summary-card";

  const labelElement = document.createElement("div");
  labelElement.className = "label";
  labelElement.textContent = label;

  const valueElement = document.createElement("div");
  valueElement.className = "value";
  valueElement.textContent = current.toLocaleString();

  const { text: deltaText, direction } = formatDelta({ current, previous });
  const deltaElement = document.createElement("div");
  deltaElement.className = `delta ${direction}`;
  deltaElement.textContent = `${deltaText}${APP_CONFIG.strings.METRICS_SUMMARY_DELTA_SUFFIX}`;

  card.appendChild(labelElement);
  card.appendChild(valueElement);
  card.appendChild(deltaElement);
  return card;
}

export function renderSummary({
  root,
  response,
}: {
  root: HTMLElement;
  response: SummaryResponseSchema;
}): void {
  while (root.firstChild !== null) {
    root.removeChild(root.firstChild);
  }

  const byCategory = new Map<
    MetricsCategory,
    { current: number; previous: number }
  >();
  for (const category of CATEGORY_ORDER) {
    const row = response.by_category.find(
      (entry) => entry.category === category,
    );
    byCategory.set(category, {
      current: row?.current ?? 0,
      previous: row?.previous ?? 0,
    });
  }

  let totalCurrent = 0;
  let totalPrevious = 0;
  for (const counts of byCategory.values()) {
    totalCurrent += counts.current;
    totalPrevious += counts.previous;
  }

  root.appendChild(
    buildCard({
      label: APP_CONFIG.strings.METRICS_SUMMARY_TOTAL_EVENTS,
      current: totalCurrent,
      previous: totalPrevious,
    }),
  );
  for (const category of CATEGORY_ORDER) {
    const counts = byCategory.get(category) ?? { current: 0, previous: 0 };
    root.appendChild(
      buildCard({
        label: APP_CONFIG.strings[CATEGORY_LABEL_KEYS[category]],
        current: counts.current,
        previous: counts.previous,
      }),
    );
  }
}
