/**
 * Render a latency timeseries response into a multi-series SVG chart overlaying
 * the p50, p95, and p99 percentile series over the bucket time axis. Unlike the
 * single-series `renderTimeseriesChart`, this renderer draws THREE polylines,
 * each differentiated by BOTH color and a stroke-dash pattern (p50 solid, p95
 * dashed, p99 dotted) so the series stay distinguishable in monochrome / for
 * color-blind users, plus a color-and-dash-coded legend.
 *
 * Null handling: a zero-sample zero-fill bucket carries `null` percentiles. Such
 * buckets render as GAPS in the polyline (the line breaks) rather than as
 * zero-latency points — `null` is never coerced to `0`. When EVERY bucket across
 * ALL three series is null, the shared `appendEmptyState` helper renders the
 * empty-state text and no chart geometry is drawn (mirrors `renderTimeseriesChart`).
 *
 * The y-axis is labeled in ms. Each `<polyline>` carries a bridged per-series
 * `aria-label`. The SVG `<title>`/`<desc>` (created by the caller in
 * `latency-card.ts`) are filled with the endpoint label and a per-series summary.
 *
 * Pure DOM mutation; no fetching, no event binding.
 */

import type { Schema } from "../types/api-helpers.d.ts";

import { APP_CONFIG } from "../lib/config.js";
import { buildAxisTicks } from "../lib/charts/axis.js";
import { linearScale, niceTicks } from "../lib/charts/scale.js";

import { appendEmptyState } from "./render-shared.js";

type LatencyTimeseriesResponse = Schema<"LatencyTimeseriesResponseSchema">;
type LatencyTimeseriesBucket = Schema<"LatencyTimeseriesBucket">;

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

// Matches the viewBox conventions used by every admin metrics chart.
const VIEWBOX_WIDTH = 800;
const VIEWBOX_HEIGHT = 240;
const AXIS_LEFT_PADDING = 56;
const AXIS_TOP_PADDING = 12;
const AXIS_BOTTOM_PADDING = 24;
const Y_AXIS_TITLE_X = 16;
const PLOT_WIDTH = VIEWBOX_WIDTH - AXIS_LEFT_PADDING;
const PLOT_HEIGHT = VIEWBOX_HEIGHT - AXIS_BOTTOM_PADDING;
const Y_AXIS_TICK_COUNT = 5;

// The three percentile series, in legend order. `dashArray` is `null` for the
// solid p50 line; p95/p99 use distinct non-color dash patterns so the series
// remain distinguishable in monochrome (WCAG-friendly). Colors are chosen to
// meet AA contrast against the chart background.
const SERIES: ReadonlyArray<{
  key: "p50" | "p95" | "p99";
  className: string;
  color: string;
  dashArray: string | null;
  ariaLabelKey:
    | "METRICS_LATENCY_SERIES_ARIA_P50"
    | "METRICS_LATENCY_SERIES_ARIA_P95"
    | "METRICS_LATENCY_SERIES_ARIA_P99";
}> = [
  {
    key: "p50",
    className: "MetricsLatencyLineP50",
    color: "#1f6feb",
    dashArray: null,
    ariaLabelKey: "METRICS_LATENCY_SERIES_ARIA_P50",
  },
  {
    key: "p95",
    className: "MetricsLatencyLineP95",
    color: "#d4761c",
    dashArray: "6,3",
    ariaLabelKey: "METRICS_LATENCY_SERIES_ARIA_P95",
  },
  {
    key: "p99",
    className: "MetricsLatencyLineP99",
    color: "#c2362f",
    dashArray: "2,3",
    ariaLabelKey: "METRICS_LATENCY_SERIES_ARIA_P99",
  },
];

function clearSvgChildren({ svg }: { svg: SVGSVGElement }): void {
  while (svg.firstChild !== null) {
    svg.removeChild(svg.firstChild);
  }
}

function ensureTitleAndDesc({ svg }: { svg: SVGSVGElement }): {
  title: SVGTitleElement;
  desc: SVGDescElement;
} {
  // `latency-card.ts` pre-appends `<title>`/`<desc>` and points the SVG's
  // `aria-labelledby`/`aria-describedby` at them. Reuse those nodes if present;
  // otherwise create them so the renderer is robust when called in isolation.
  let title = svg.querySelector<SVGTitleElement>("title");
  if (title === null) {
    title = document.createElementNS(SVG_NAMESPACE, "title");
    svg.appendChild(title);
  }
  let desc = svg.querySelector<SVGDescElement>("desc");
  if (desc === null) {
    desc = document.createElementNS(SVG_NAMESPACE, "desc");
    svg.appendChild(desc);
  }
  return { title, desc };
}

function formatBucketLabel(bucketIso: string): string {
  const parsed = new Date(bucketIso);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
    hour: "numeric",
    timeZone: "UTC",
  }).format(parsed);
}

function valueForSeries(
  bucket: LatencyTimeseriesBucket,
  key: "p50" | "p95" | "p99",
): number | null {
  return bucket[key];
}

function formatMs(value: number | null): string {
  return value === null ? "—" : `${Math.round(value)}ms`;
}

/**
 * Build the title (endpoint label) and desc (per-series aggregate summary) text.
 * The summary uses the median of each series' last non-null value as a
 * representative figure, and is null-safe for series with no data.
 */
function buildSummaryText(response: LatencyTimeseriesResponse): {
  titleText: string;
  descText: string;
} {
  const method = response.method !== null ? ` ${response.method}` : "";
  const endpoint = response.endpoint ?? "";
  const titleText = `${endpoint}${method}`.trim();

  const lastValue = (key: "p50" | "p95" | "p99"): number | null => {
    for (let index = response.buckets.length - 1; index >= 0; index -= 1) {
      const value = valueForSeries(response.buckets[index]!, key);
      if (value !== null) {
        return value;
      }
    }
    return null;
  };

  const descText =
    `p50 median ${formatMs(lastValue("p50"))}; ` +
    `p95 ${formatMs(lastValue("p95"))}; ` +
    `p99 ${formatMs(lastValue("p99"))} across ${response.buckets.length} buckets`;
  return { titleText, descText };
}

/**
 * Build the `points` strings for one series, broken into contiguous segments at
 * null buckets. Each segment is a separate `<polyline>` so a null bucket leaves
 * a visible gap (never connected through as zero). Returns one points string per
 * non-null run.
 */
function buildSeriesSegments({
  buckets,
  key,
  scaleY,
  stepX,
}: {
  buckets: LatencyTimeseriesBucket[];
  key: "p50" | "p95" | "p99";
  scaleY: (value: number) => number;
  stepX: number;
}): string[] {
  const segments: string[] = [];
  let current: string[] = [];
  buckets.forEach((bucket, index) => {
    const value = valueForSeries(bucket, key);
    if (value === null) {
      if (current.length > 0) {
        segments.push(current.join(" "));
        current = [];
      }
      return;
    }
    const xPosition = AXIS_LEFT_PADDING + index * stepX;
    current.push(`${xPosition},${scaleY(value)}`);
  });
  if (current.length > 0) {
    segments.push(current.join(" "));
  }
  return segments;
}

export function renderLatencyChart({
  svg,
  response,
}: {
  svg: SVGSVGElement;
  response: LatencyTimeseriesResponse;
}): void {
  clearSvgChildren({ svg });
  const { title, desc } = ensureTitleAndDesc({ svg });
  const { titleText, descText } = buildSummaryText(response);
  title.textContent = titleText;
  desc.textContent = descText;

  // All-null guard: when EVERY bucket across ALL three series is null (or there
  // are no buckets), render the shared empty state and draw no geometry. Mirrors
  // `renderTimeseriesChart`'s all-null early return.
  const allNull = response.buckets.every(
    (bucket) =>
      bucket.p50 === null && bucket.p95 === null && bucket.p99 === null,
  );
  if (allNull) {
    appendEmptyState({
      svg,
      message: APP_CONFIG.strings.METRICS_EMPTY_STATE,
    });
    return;
  }

  // y-domain: max across every non-null percentile in every series.
  let maxValue = 0;
  for (const bucket of response.buckets) {
    for (const series of SERIES) {
      const value = valueForSeries(bucket, series.key);
      if (value !== null && value > maxValue) {
        maxValue = value;
      }
    }
  }

  const baseYTicks =
    maxValue === 0
      ? niceTicks({ min: 0, max: 1, count: Y_AXIS_TICK_COUNT })
      : niceTicks({ min: 0, max: maxValue, count: Y_AXIS_TICK_COUNT });
  const baseTopTick = baseYTicks[baseYTicks.length - 1]!;
  const tickStep =
    baseYTicks.length >= 2 ? baseYTicks[1]! - baseYTicks[0]! : baseTopTick;
  const yTicks =
    baseTopTick === maxValue && maxValue > 0
      ? [...baseYTicks, baseTopTick + tickStep]
      : baseYTicks;
  const yDomainMax = yTicks[yTicks.length - 1]!;
  const scaleY = linearScale({
    domain: [0, yDomainMax],
    range: [PLOT_HEIGHT, AXIS_TOP_PADDING],
  });
  const axisTicks = buildAxisTicks({
    ticks: yTicks,
    scale: scaleY,
    axisLength: PLOT_HEIGHT,
  });

  // Rotated y-axis title ("Latency (ms)").
  const yAxisTitleY = (PLOT_HEIGHT + AXIS_TOP_PADDING) / 2;
  const yAxisTitle = document.createElementNS(SVG_NAMESPACE, "text");
  yAxisTitle.setAttribute("class", "MetricsAxisTitle");
  yAxisTitle.setAttribute("x", String(Y_AXIS_TITLE_X));
  yAxisTitle.setAttribute("y", String(yAxisTitleY));
  yAxisTitle.setAttribute("text-anchor", "middle");
  yAxisTitle.setAttribute("dominant-baseline", "middle");
  yAxisTitle.setAttribute(
    "transform",
    `rotate(-90, ${Y_AXIS_TITLE_X}, ${yAxisTitleY})`,
  );
  yAxisTitle.textContent = APP_CONFIG.strings.METRICS_LATENCY_Y_AXIS_LABEL;
  svg.appendChild(yAxisTitle);

  // y-axis tick lines + labels.
  for (const tick of axisTicks) {
    const axisLine = document.createElementNS(SVG_NAMESPACE, "line");
    axisLine.setAttribute("class", "MetricsAxisLine");
    axisLine.setAttribute("x1", String(AXIS_LEFT_PADDING));
    axisLine.setAttribute("x2", String(VIEWBOX_WIDTH));
    axisLine.setAttribute("y1", String(tick.position));
    axisLine.setAttribute("y2", String(tick.position));
    svg.appendChild(axisLine);

    const axisLabel = document.createElementNS(SVG_NAMESPACE, "text");
    axisLabel.setAttribute("class", "MetricsAxisLabel");
    axisLabel.setAttribute("x", String(AXIS_LEFT_PADDING - 4));
    axisLabel.setAttribute("y", String(tick.position));
    axisLabel.setAttribute("text-anchor", "end");
    axisLabel.setAttribute("dominant-baseline", "middle");
    axisLabel.textContent = tick.label;
    svg.appendChild(axisLabel);
  }

  const stepX =
    response.buckets.length > 1
      ? PLOT_WIDTH / (response.buckets.length - 1)
      : 0;

  // One or more polyline segments per series. Null buckets split a series into
  // multiple segments so the line breaks at gaps rather than connecting through.
  for (const series of SERIES) {
    const segments = buildSeriesSegments({
      buckets: response.buckets,
      key: series.key,
      scaleY,
      stepX,
    });
    for (const points of segments) {
      const polyline = document.createElementNS(SVG_NAMESPACE, "polyline");
      polyline.setAttribute("class", `MetricsLatencyLine ${series.className}`);
      polyline.setAttribute("points", points);
      polyline.setAttribute("fill", "none");
      polyline.setAttribute("stroke", series.color);
      if (series.dashArray !== null) {
        polyline.setAttribute("stroke-dasharray", series.dashArray);
      }
      polyline.setAttribute(
        "aria-label",
        APP_CONFIG.strings[series.ariaLabelKey],
      );
      svg.appendChild(polyline);
    }
  }

  // Color-and-dash-coded legend. Each entry is a short `<line>` swatch (carrying
  // the series' dash pattern) plus a `<text>` label, so the legend reads in
  // monochrome too.
  const legendGroup = document.createElementNS(SVG_NAMESPACE, "g");
  legendGroup.setAttribute("class", "MetricsLatencyLegend");
  const legendY = AXIS_TOP_PADDING + 4;
  let legendX = AXIS_LEFT_PADDING + 8;
  for (const series of SERIES) {
    const swatch = document.createElementNS(SVG_NAMESPACE, "line");
    swatch.setAttribute(
      "class",
      `MetricsLatencyLegendSwatch ${series.className}`,
    );
    swatch.setAttribute("x1", String(legendX));
    swatch.setAttribute("x2", String(legendX + 24));
    swatch.setAttribute("y1", String(legendY));
    swatch.setAttribute("y2", String(legendY));
    swatch.setAttribute("stroke", series.color);
    swatch.setAttribute("stroke-width", "2");
    if (series.dashArray !== null) {
      swatch.setAttribute("stroke-dasharray", series.dashArray);
    }
    legendGroup.appendChild(swatch);

    const label = document.createElementNS(SVG_NAMESPACE, "text");
    label.setAttribute("class", "MetricsLatencyLegendLabel");
    label.setAttribute("x", String(legendX + 28));
    label.setAttribute("y", String(legendY));
    label.setAttribute("dominant-baseline", "middle");
    label.textContent = series.key;
    legendGroup.appendChild(label);

    legendX += 78;
  }
  svg.appendChild(legendGroup);

  // x-axis labels: first, middle, last bucket.
  const xLabelIndices: number[] =
    response.buckets.length === 1
      ? [0]
      : [
          ...new Set([
            0,
            Math.floor((response.buckets.length - 1) / 2),
            response.buckets.length - 1,
          ]),
        ];
  const xLabelY = VIEWBOX_HEIGHT - 6;
  const lastIndex = response.buckets.length - 1;
  for (const index of xLabelIndices) {
    const xPosition = AXIS_LEFT_PADDING + index * stepX;
    const label = document.createElementNS(SVG_NAMESPACE, "text");
    label.setAttribute("class", "MetricsAxisLabel MetricsAxisLabelX");
    label.setAttribute("x", String(xPosition));
    label.setAttribute("y", String(xLabelY));
    const textAnchor =
      index === 0 ? "start" : index === lastIndex ? "end" : "middle";
    label.setAttribute("text-anchor", textAnchor);
    label.textContent = formatBucketLabel(response.buckets[index]!.bucket);
    svg.appendChild(label);
  }
}
