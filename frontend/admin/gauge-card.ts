/**
 * Render each gauge from a batched `gauges/timeseries` response as a
 * `.gauge-card` — a header (description + bridged kind chip + last-value
 * headline) plus a line chart of that gauge's samples over the active window.
 *
 * The chart is built by the shared `renderTimeseriesChart` primitive via a
 * fully-valid `TimeseriesResponseSchema` adapter (`gaugeTimeseriesToChartResponse`):
 * k-anon-suppressed samples (both value fields null) are filtered out before
 * mapping, so an all-null gauge yields an empty bucket list and the chart's
 * built-in empty state renders instead of crashing.
 *
 * Pure DOM mutation; no fetching, no event binding.
 */

import type { Schema } from "../types/api-helpers.d.ts";

import { APP_CONFIG } from "../lib/config.js";

import { renderTimeseriesChart } from "./render-timeseries-chart.js";

type GaugesTimeseriesResponse = Schema<"GaugesTimeseriesResponseSchema">;
type GaugeSeries = Schema<"GaugeSeries">;
type GaugeSampleSchema = Schema<"GaugeSampleSchema">;
type TimeseriesResponseSchema = Schema<"TimeseriesResponseSchema">;

// Visible placeholder for a suppressed / missing last value. A local module
// constant (en dash, U+2013), NOT bridged through APP_CONFIG (DD-6) — mirrors
// `flow-card.ts`'s `NULL_PCT_PLACEHOLDER`.
const SUPPRESSED_PLACEHOLDER = "–";

// Maps each GaugeKind value to its bridged human label. No `event_derived_max`
// entry — no shipped gauge uses that kind.
const GAUGE_KIND_LABELS: Record<string, string> = {
  volume: APP_CONFIG.strings.METRICS_GAUGE_KIND_VOLUME,
  distribution_max: APP_CONFIG.strings.METRICS_GAUGE_KIND_DISTRIBUTION_MAX,
  distribution_avg: APP_CONFIG.strings.METRICS_GAUGE_KIND_DISTRIBUTION_AVG,
};

/**
 * Build a fully-valid `TimeseriesResponseSchema` from a single gauge's series
 * plus the batched response's window envelope. No `as` cast on the response
 * shape — only the post-filter `value_int ?? value_float` narrowing assertion.
 *
 * `event_name` is set to the gauge `description` (human text), not the raw
 * snake_case gauge name, because `renderTimeseriesChart` writes it verbatim into
 * the SVG `<title>` — a screen reader would otherwise verbalize the underscores.
 */
function gaugeTimeseriesToChartResponse({
  description,
  samples,
  window,
  window_start,
  window_end,
}: {
  description: string;
  samples: GaugeSampleSchema[];
  window: string | null;
  window_start: string;
  window_end: string;
}): TimeseriesResponseSchema {
  return {
    event_name: description,
    window,
    resolution: "hour",
    window_start,
    window_end,
    // Filter before map: suppressed (both null) samples excluded; all-null gauge
    // produces empty buckets triggering empty-chart state.
    buckets: samples
      .filter(
        (sample) => sample.value_int !== null || sample.value_float !== null,
      )
      .map((sample) => ({
        bucket: sample.sampled_at,
        count: (sample.value_int ?? sample.value_float) as number,
      })),
  };
}

/**
 * Format the last non-null sample's value, or the en-dash placeholder when the
 * gauge has no non-null sample (suppressed / empty). AVG gauges (value_float)
 * render with 1–2 fraction digits; VOLUME / MAX gauges (value_int) render as a
 * grouped integer.
 */
export function formatGaugeLastValue({
  samples,
}: {
  samples: GaugeSampleSchema[];
}): string {
  for (let index = samples.length - 1; index >= 0; index -= 1) {
    const sample = samples[index]!;
    if (typeof sample.value_float === "number") {
      return sample.value_float.toLocaleString(undefined, {
        minimumFractionDigits: 1,
        maximumFractionDigits: 2,
      });
    }
    if (typeof sample.value_int === "number") {
      return sample.value_int.toLocaleString();
    }
  }
  return SUPPRESSED_PLACEHOLDER;
}

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

/**
 * Build one `.gauge-card` for a single gauge series. Never throws on a missing
 * or empty series — it renders the empty-chart card (and applies the
 * `gauge-card--suppressed` modifier) instead.
 */
export function renderGaugeCard({
  entry,
  window,
  window_start,
  window_end,
}: {
  entry: GaugeSeries;
  window: string | null;
  window_start: string;
  window_end: string;
}): HTMLElement {
  const card = document.createElement("section");
  card.className = "gauge-card";
  // Stable identity so `renderGaugeGrid` can reconcile per-gauge in place.
  card.dataset.gaugeName = entry.gauge_name;

  const lastValueText = formatGaugeLastValue({ samples: entry.samples });
  const isSuppressed = lastValueText === SUPPRESSED_PLACEHOLDER;
  if (isSuppressed) {
    card.classList.add("gauge-card--suppressed");
  }

  const header = document.createElement("div");
  header.className = "gauge-header";

  const title = document.createElement("h3");
  title.className = "gauge-title";
  title.textContent = entry.description;

  const kindChip = document.createElement("span");
  kindChip.className = "gauge-kind";
  kindChip.textContent = GAUGE_KIND_LABELS[entry.kind] ?? entry.kind;

  const lastValue = document.createElement("span");
  lastValue.className = "gauge-last-value";
  lastValue.textContent = lastValueText;
  if (isSuppressed) {
    // The bare en dash is meaningless read aloud — announce the suppressed
    // state with the bridged aria label instead (DD-11).
    lastValue.setAttribute(
      "aria-label",
      APP_CONFIG.strings.METRICS_GAUGE_SUPPRESSED_ARIA,
    );
  }

  header.appendChild(title);
  header.appendChild(kindChip);
  header.appendChild(lastValue);
  card.appendChild(header);

  // Screen-reader summary of the whole card (DD-9).
  card.setAttribute("aria-label", `${entry.description}: ${lastValueText}`);

  const svg = document.createElementNS(SVG_NAMESPACE, "svg");
  svg.setAttribute("class", "gauge-chart");
  svg.setAttribute("viewBox", "0 0 800 240");
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  // `renderTimeseriesChart` relies on these aria hooks being pre-set (mirrors
  // the static template in `metrics_panel.html`).
  const svgId = `gauge-chart-${entry.gauge_name}`;
  svg.setAttribute("id", svgId);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-labelledby", `${svgId}-title`);
  svg.setAttribute("aria-describedby", `${svgId}-desc`);

  renderTimeseriesChart({
    svg: svg as SVGSVGElement,
    response: gaugeTimeseriesToChartResponse({
      description: entry.description,
      samples: entry.samples,
      window,
      window_start,
      window_end,
    }),
  });
  card.appendChild(svg);

  return card;
}

// Remembers the batched response last rendered per grid container so
// `renderGaugeGrid` reconciles per-gauge in place (replace one card) rather than
// clearing the container wholesale — which would detach held element references
// (e.g. a Selenium assertion). WeakMap-keyed by the container so a
// detached/replaced grid does not leak state.
const lastRenderedGaugeState: WeakMap<HTMLElement, GaugesTimeseriesResponse> =
  new WeakMap();

/**
 * Render the full Gauges grid: one `.gauge-card` per gauge in the batched
 * response's order (the backend orders by GaugeName declaration order).
 *
 * Pure card-renderer — does NOT emit an empty state; that responsibility lives
 * exclusively in `renderGaugesPanel`. A gauge whose `samples` is empty or all
 * suppressed still renders a card with an empty-chart state.
 *
 * Reconciles per-gauge by `data-gauge-name`: an existing card whose series is
 * unchanged by reference is left in place; otherwise the card is rebuilt and
 * replaced. Because the batched fetch always returns a fresh response, every
 * series reference differs and all cards rebuild each fetch; the WeakMap keeps
 * the in-place replacement so held element references survive an update.
 */
export function renderGaugeGrid({
  container,
  response,
}: {
  container: HTMLElement;
  response: GaugesTimeseriesResponse;
}): void {
  const previous = lastRenderedGaugeState.get(container);
  const previousByName: Map<string, GaugeSeries> = new Map(
    (previous?.gauges ?? []).map((series) => [series.gauge_name, series]),
  );
  let previousCard: HTMLElement | null = null;
  for (const entry of response.gauges) {
    const existingCard = container.querySelector<HTMLElement>(
      `.gauge-card[data-gauge-name="${entry.gauge_name}"]`,
    );
    if (
      existingCard !== null &&
      previousByName.get(entry.gauge_name) === entry
    ) {
      previousCard = existingCard;
      continue;
    }
    const newCard = renderGaugeCard({
      entry,
      window: response.window,
      window_start: response.window_start,
      window_end: response.window_end,
    });
    if (existingCard !== null) {
      container.replaceChild(newCard, existingCard);
    } else if (previousCard !== null) {
      previousCard.insertAdjacentElement("afterend", newCard);
    } else {
      container.insertBefore(newCard, container.firstChild);
    }
    previousCard = newCard;
  }
  lastRenderedGaugeState.set(container, response);
}
