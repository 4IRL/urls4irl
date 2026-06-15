/**
 * Render the Gauges tab as a 2-column table (gauge description + last value),
 * one `.gauge-row` per gauge, plus a single detail area beneath it. Selecting a
 * row (driven by `selectedGaugeName`) renders ONE timeseries chart for that
 * gauge in the detail area; with no selection the detail area shows a prompt to
 * pick a gauge. This replaces the previous all-charts-at-once card grid: only
 * the chosen gauge's trend is plotted at a time.
 *
 * The chart is built by the shared `renderTimeseriesChart` primitive via a
 * fully-valid `TimeseriesResponseSchema` adapter (`gaugeTimeseriesToChartResponse`):
 * k-anon-suppressed samples (both value fields null) are filtered out before
 * mapping, so an all-null gauge yields an empty bucket list and the chart's
 * built-in empty state renders instead of crashing.
 *
 * Pure DOM mutation; no fetching, no event binding (row clicks are wired in
 * `metrics-dashboard.ts`, mirroring the top-table row-click pattern).
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

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

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

/**
 * Build one `<tr.gauge-row>` for a single gauge: a name cell (description + kind
 * chip) and a value cell (last sample value). The row is a focusable, clickable
 * widget (`role="button"`, `tabindex="0"`) carrying its `data-gauge-name` so the
 * dashboard's delegated click/keydown handler can resolve the clicked gauge.
 */
function renderGaugeRow({
  entry,
  selected,
}: {
  entry: GaugeSeries;
  selected: boolean;
}): HTMLTableRowElement {
  const row = document.createElement("tr");
  row.className = "gauge-row";
  row.dataset.gaugeName = entry.gauge_name;
  row.setAttribute("role", "button");
  row.tabIndex = 0;

  const lastValueText = formatGaugeLastValue({ samples: entry.samples });
  const isSuppressed = lastValueText === SUPPRESSED_PLACEHOLDER;
  if (isSuppressed) {
    row.classList.add("gauge-row--suppressed");
  }
  if (selected) {
    row.classList.add("gauge-row--selected");
    row.setAttribute("aria-current", "true");
  }

  const nameCell = document.createElement("td");
  nameCell.className = "gauge-name-cell";

  const title = document.createElement("span");
  title.className = "gauge-title";
  title.textContent = entry.description;

  const kindChip = document.createElement("span");
  kindChip.className = "gauge-kind";
  kindChip.textContent = GAUGE_KIND_LABELS[entry.kind] ?? entry.kind;

  nameCell.appendChild(title);
  nameCell.appendChild(kindChip);

  const valueCell = document.createElement("td");
  valueCell.className = "gauge-value-cell";
  valueCell.textContent = lastValueText;
  if (isSuppressed) {
    // The bare en dash is meaningless read aloud — announce the suppressed
    // state with the bridged aria label instead (DD-11).
    valueCell.setAttribute(
      "aria-label",
      APP_CONFIG.strings.METRICS_GAUGE_SUPPRESSED_ARIA,
    );
  }

  // Screen-reader summary of the whole row (DD-9).
  row.setAttribute("aria-label", `${entry.description}: ${lastValueText}`);

  row.appendChild(nameCell);
  row.appendChild(valueCell);
  return row;
}

/**
 * Render the selected gauge's timeseries chart into the detail container, or the
 * bridged "select a gauge" prompt when no gauge is selected (or the selected
 * name is no longer present in the response). Never throws on an empty / all-null
 * series — `renderTimeseriesChart` shows its built-in empty state.
 */
function renderGaugeDetail({
  detail,
  response,
  selectedGaugeName,
}: {
  detail: HTMLElement;
  response: GaugesTimeseriesResponse;
  selectedGaugeName: string | null;
}): void {
  while (detail.firstChild !== null) {
    detail.removeChild(detail.firstChild);
  }

  const selectedEntry =
    selectedGaugeName === null
      ? undefined
      : response.gauges.find((entry) => entry.gauge_name === selectedGaugeName);

  if (selectedEntry === undefined) {
    const prompt = document.createElement("p");
    prompt.className = "gauge-detail-prompt";
    prompt.textContent = APP_CONFIG.strings.METRICS_GAUGE_SELECT_PROMPT;
    detail.appendChild(prompt);
    return;
  }

  const heading = document.createElement("h3");
  heading.className = "gauge-detail-title";
  heading.textContent = selectedEntry.description;
  detail.appendChild(heading);

  const svg = document.createElementNS(SVG_NAMESPACE, "svg");
  svg.setAttribute("class", "gauge-chart");
  svg.setAttribute("viewBox", "0 0 800 240");
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  // `renderTimeseriesChart` relies on these aria hooks being pre-set (mirrors
  // the static template in `metrics_panel.html`).
  const svgId = `gauge-chart-${selectedEntry.gauge_name}`;
  svg.setAttribute("id", svgId);
  svg.setAttribute("role", "img");
  svg.setAttribute("aria-labelledby", `${svgId}-title`);
  svg.setAttribute("aria-describedby", `${svgId}-desc`);

  renderTimeseriesChart({
    svg: svg as SVGSVGElement,
    response: gaugeTimeseriesToChartResponse({
      description: selectedEntry.description,
      samples: selectedEntry.samples,
      window: response.window,
      window_start: response.window_start,
      window_end: response.window_end,
    }),
  });
  detail.appendChild(svg);
}

/**
 * Build the `.gauge-table` skeleton (header row + empty tbody) inside the grid
 * container. The "Gauge" / "Value" column headers are bridged through
 * APP_CONFIG so no display string is hardcoded in TS.
 */
function buildGaugeTable(): HTMLTableElement {
  const table = document.createElement("table");
  table.className = "gauge-table";

  const thead = document.createElement("thead");
  const headRow = document.createElement("tr");
  const nameHead = document.createElement("th");
  nameHead.setAttribute("scope", "col");
  nameHead.textContent = APP_CONFIG.strings.METRICS_GAUGE_COL_NAME;
  const valueHead = document.createElement("th");
  valueHead.setAttribute("scope", "col");
  valueHead.textContent = APP_CONFIG.strings.METRICS_GAUGE_COL_VALUE;
  headRow.appendChild(nameHead);
  headRow.appendChild(valueHead);
  thead.appendChild(headRow);

  const tbody = document.createElement("tbody");

  table.appendChild(thead);
  table.appendChild(tbody);
  return table;
}

/**
 * Render the full Gauges panel: a 2-column table (one `.gauge-row` per gauge in
 * the batched response's declaration order) plus a detail area showing the
 * selected gauge's chart — or the select-a-gauge prompt when nothing is chosen.
 *
 * Pure renderer — does NOT emit the no-data empty state; that responsibility
 * lives exclusively in `renderGaugesPanel`. The table/detail scaffold is rebuilt
 * each call from the fresh batched response (the fetch always returns a new
 * object), and the detail re-renders so the selected gauge's chart and the row
 * values stay current across polls.
 */
export function renderGaugeGrid({
  container,
  response,
  selectedGaugeName = null,
}: {
  container: HTMLElement;
  response: GaugesTimeseriesResponse;
  selectedGaugeName?: string | null;
}): void {
  while (container.firstChild !== null) {
    container.removeChild(container.firstChild);
  }

  const table = buildGaugeTable();
  const tbody = table.querySelector("tbody")!;
  for (const entry of response.gauges) {
    tbody.appendChild(
      renderGaugeRow({
        entry,
        selected: entry.gauge_name === selectedGaugeName,
      }),
    );
  }
  container.appendChild(table);

  const detail = document.createElement("div");
  detail.className = "gauge-detail";
  renderGaugeDetail({ detail, response, selectedGaugeName });
  container.appendChild(detail);
}
