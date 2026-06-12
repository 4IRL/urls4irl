/**
 * Render a grouped-timeseries response into a stacked-bar SVG for the
 * Pipeline Health card.
 *
 * Each X-column corresponds to one `batch_size_bucket` value ("1" / "2-5" /
 * "6-25" / "26-100"). Within each column, four stacked segments split the
 * total by `(transport × device_type)` — bottom-to-top: fetch · desktop,
 * fetch · mobile, beacon · desktop, beacon · mobile (legend order matches).
 *
 * The card deliberately ignores the per-tab device filter — the entire
 * point of the chart is to surface mobile-vs-desktop chattiness as a
 * cross-tab signal. The `window` argument drives the windowLabel embedded
 * in the SVG `<desc>` for screen readers (WCAG 4.1.2).
 *
 * Pure DOM mutation; no fetching, no event binding.
 */

import type { Schema } from "../types/api-helpers.d.ts";

import { APP_CONFIG } from "../lib/config.js";
import { buildAxisTicks } from "../lib/charts/axis.js";
import { buildStackedBarSegments } from "../lib/charts/bar.js";
import { linearScale, niceTicks } from "../lib/charts/scale.js";

import type { MetricsWindow } from "./metrics-dashboard.js";
import { appendEmptyState } from "./render-shared.js";

type GroupedTimeseriesResponseSchema =
  Schema<"GroupedTimeseriesResponseSchema">;
type GroupedTimeseriesBucket = Schema<"GroupedTimeseriesBucket">;

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

// Matches the panel template's `viewBox="0 0 800 240"`. The drawing area
// reserves space for y-axis tick labels on the left and x-axis tick labels
// at the bottom, plus top padding so the topmost y-axis tick label sits
// fully inside the viewBox.
const VIEWBOX_WIDTH = 800;
const VIEWBOX_HEIGHT = 240;
const AXIS_LEFT_PADDING = 56;
const AXIS_TOP_PADDING = 12;
const AXIS_BOTTOM_PADDING = 24;
const Y_AXIS_TITLE_X = 16;
const PLOT_WIDTH = VIEWBOX_WIDTH - AXIS_LEFT_PADDING;
const PLOT_HEIGHT = VIEWBOX_HEIGHT - AXIS_BOTTOM_PADDING;
const Y_AXIS_TICK_COUNT = 5;

// Closed-set X-axis column order. Source of truth: the `batch_size_bucket`
// Literal in `_DimApiMetricsIngestBatch` (backend/metrics/dimension_models.py).
// String values do NOT sort lexicographically in numeric order
// ("26-100" sorts before "6-25"), so the renderer always uses this fixed
// order instead of deriving it from response data.
const BATCH_SIZE_BUCKET_ORDER = ["1", "2-5", "6-25", "26-100"] as const;

type BatchSizeBucket = (typeof BATCH_SIZE_BUCKET_ORDER)[number];

// Wire values for the (transport, device_type) tuple. Transport values come
// from the API's `?transport=beacon` query param (default "fetch");
// device_type values are the `DeviceType` IntEnum members (1 = MOBILE,
// 2 = DESKTOP) injected by the metrics middleware.
const TRANSPORT_FETCH = "fetch";
const TRANSPORT_BEACON = "beacon";
const DEVICE_TYPE_MOBILE = 1;
const DEVICE_TYPE_DESKTOP = 2;

// Bottom-to-top stack ordering. The legend renders in this same order so
// the chart's vertical sequence matches the legend's horizontal sequence.
type StackSegmentKey =
  | "fetch-desktop"
  | "fetch-mobile"
  | "beacon-desktop"
  | "beacon-mobile";

const STACK_SEGMENT_ORDER: readonly StackSegmentKey[] = [
  "fetch-desktop",
  "fetch-mobile",
  "beacon-desktop",
  "beacon-mobile",
];

const SEGMENT_CLASS_NAMES: Record<StackSegmentKey, string> = {
  "fetch-desktop": "MetricsPipelineHealthBar--fetch-desktop",
  "fetch-mobile": "MetricsPipelineHealthBar--fetch-mobile",
  "beacon-desktop": "MetricsPipelineHealthBar--beacon-desktop",
  "beacon-mobile": "MetricsPipelineHealthBar--beacon-mobile",
};

// Human-readable window label embedded in the SVG `<desc>` so the chart's
// summary announces the active window to screen readers. Keys must stay
// aligned with `MetricsWindow` (defined in metrics-dashboard.ts).
const WINDOW_LABELS: Record<MetricsWindow, string> = {
  day: "last 24 hours",
  week: "last 7 days",
  month: "last 30 days",
  year: "last 365 days",
};

function clearSvgChildren({ svg }: { svg: SVGSVGElement }): void {
  while (svg.firstChild !== null) {
    svg.removeChild(svg.firstChild);
  }
}

function appendTitleAndDesc({
  svg,
  titleText,
  descText,
}: {
  svg: SVGSVGElement;
  titleText: string;
  descText: string;
}): void {
  const titleElement = document.createElementNS(SVG_NAMESPACE, "title");
  titleElement.textContent = titleText;
  const descElement = document.createElementNS(SVG_NAMESPACE, "desc");
  descElement.textContent = descText;
  svg.appendChild(titleElement);
  svg.appendChild(descElement);
}

function isBatchSizeBucket(value: unknown): value is BatchSizeBucket {
  return (
    typeof value === "string" &&
    (BATCH_SIZE_BUCKET_ORDER as readonly string[]).includes(value)
  );
}

function segmentKeyForBucketDims(
  dimensions: GroupedTimeseriesBucket["dimensions"],
): StackSegmentKey | null {
  const transport = dimensions["transport"];
  const deviceType = dimensions["device_type"];
  // device_type is an int wire value; transport is a string. Both come from
  // the JSONB payload typed loosely as `string | number` over the API.
  const isFetch = transport === TRANSPORT_FETCH;
  const isBeacon = transport === TRANSPORT_BEACON;
  const isMobile =
    deviceType === DEVICE_TYPE_MOBILE ||
    deviceType === String(DEVICE_TYPE_MOBILE);
  const isDesktop =
    deviceType === DEVICE_TYPE_DESKTOP ||
    deviceType === String(DEVICE_TYPE_DESKTOP);

  if (isFetch && isDesktop) {
    return "fetch-desktop";
  }
  if (isFetch && isMobile) {
    return "fetch-mobile";
  }
  if (isBeacon && isDesktop) {
    return "beacon-desktop";
  }
  if (isBeacon && isMobile) {
    return "beacon-mobile";
  }
  return null;
}

/**
 * Aggregate the response's `(bucket × dim-tuple)` rows into a flat map keyed
 * by `(batch_size_bucket, stackSegmentKey)`, summing counts across time
 * buckets. The card is summed over the full window — no time axis on this
 * chart, only the four batch-size columns split by (transport × device_type).
 */
function aggregateByBatchSizeAndStack(
  response: GroupedTimeseriesResponseSchema,
): Map<BatchSizeBucket, Map<StackSegmentKey, number>> {
  const aggregated = new Map<BatchSizeBucket, Map<StackSegmentKey, number>>();
  for (const responseBucket of response.buckets) {
    const batchSizeBucket = responseBucket.dimensions["batch_size_bucket"];
    if (!isBatchSizeBucket(batchSizeBucket)) {
      continue;
    }
    const segmentKey = segmentKeyForBucketDims(responseBucket.dimensions);
    if (segmentKey === null) {
      continue;
    }
    let perBatchSize = aggregated.get(batchSizeBucket);
    if (perBatchSize === undefined) {
      perBatchSize = new Map<StackSegmentKey, number>();
      aggregated.set(batchSizeBucket, perBatchSize);
    }
    const existingCount = perBatchSize.get(segmentKey) ?? 0;
    perBatchSize.set(segmentKey, existingCount + responseBucket.count);
  }
  return aggregated;
}

export function renderPipelineHealthChart({
  svg,
  response,
  window,
}: {
  svg: SVGSVGElement;
  response: GroupedTimeseriesResponseSchema;
  window: MetricsWindow;
}): void {
  clearSvgChildren({ svg });

  const windowLabel = WINDOW_LABELS[window];

  if (response.buckets.length === 0) {
    appendTitleAndDesc({
      svg,
      titleText: APP_CONFIG.strings.METRICS_PIPELINE_HEALTH_TITLE,
      descText: APP_CONFIG.strings.METRICS_PIPELINE_HEALTH_EMPTY_STATE,
    });
    appendEmptyState({
      svg,
      message: APP_CONFIG.strings.METRICS_PIPELINE_HEALTH_EMPTY_STATE,
    });
    return;
  }

  const aggregated = aggregateByBatchSizeAndStack(response);

  // Compute per-column totals so the y-domain covers the tallest stacked bar.
  const columnTotals = BATCH_SIZE_BUCKET_ORDER.map((batchSizeBucket) => {
    const perBatchSize = aggregated.get(batchSizeBucket);
    if (perBatchSize === undefined) {
      return 0;
    }
    let total = 0;
    for (const stackedCount of perBatchSize.values()) {
      total += stackedCount;
    }
    return total;
  });
  const maxColumnTotal = Math.max(...columnTotals);
  const totalBatches = columnTotals.reduce((sum, value) => sum + value, 0);

  // y-axis ticks: same pattern as render-timeseries-chart — `niceTicks` over
  // [0, max] with a step's worth of headroom so the topmost stack does not
  // touch the top axis line.
  const baseYTicks =
    maxColumnTotal === 0
      ? niceTicks({ min: 0, max: 1, count: Y_AXIS_TICK_COUNT })
      : niceTicks({ min: 0, max: maxColumnTotal, count: Y_AXIS_TICK_COUNT });
  const baseTopTick = baseYTicks[baseYTicks.length - 1]!;
  const tickStep =
    baseYTicks.length >= 2 ? baseYTicks[1]! - baseYTicks[0]! : baseTopTick;
  const yTicks =
    baseTopTick === maxColumnTotal && maxColumnTotal > 0
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

  appendTitleAndDesc({
    svg,
    titleText: APP_CONFIG.strings.METRICS_PIPELINE_HEALTH_TITLE,
    descText:
      APP_CONFIG.strings.METRICS_PIPELINE_HEALTH_CHART_DESC +
      " (" +
      windowLabel +
      " window, " +
      totalBatches +
      " total batches)",
  });

  // Rotated y-axis title on the left edge. Same pattern as the timeseries
  // chart's y-axis title so the two charts read consistently.
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
  yAxisTitle.textContent =
    APP_CONFIG.strings.METRICS_PIPELINE_HEALTH_AXIS_LABEL;
  svg.appendChild(yAxisTitle);

  // y-axis tick lines + labels — drawn before bars so they layer beneath.
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

  // Stacked-bar rects: one column per batch-size bucket, four segments per
  // column ordered bottom-to-top. Skip `<rect>` creation for zero-height
  // segments to keep the DOM lean and avoid invisible rects intercepting
  // pointer events.
  const totalColumns = BATCH_SIZE_BUCKET_ORDER.length;
  const xLabelY = VIEWBOX_HEIGHT - 6;
  for (
    let columnIndex = 0;
    columnIndex < BATCH_SIZE_BUCKET_ORDER.length;
    columnIndex += 1
  ) {
    const batchSizeBucket = BATCH_SIZE_BUCKET_ORDER[columnIndex];
    const perBatchSize = aggregated.get(batchSizeBucket);
    const segments = STACK_SEGMENT_ORDER.map((segmentKey) => ({
      value: perBatchSize?.get(segmentKey) ?? 0,
      className: SEGMENT_CLASS_NAMES[segmentKey],
    }));
    const stackedRects = buildStackedBarSegments({
      segments,
      index: columnIndex,
      total: totalColumns,
      width: PLOT_WIDTH,
      height: PLOT_HEIGHT,
      scaleY,
    });
    for (const rectAttrs of stackedRects) {
      if (rectAttrs.height === 0) {
        continue;
      }
      const rect = document.createElementNS(SVG_NAMESPACE, "rect");
      rect.setAttribute("class", rectAttrs.className);
      rect.setAttribute("x", String(rectAttrs.x + AXIS_LEFT_PADDING));
      rect.setAttribute("y", String(rectAttrs.y));
      rect.setAttribute("width", String(rectAttrs.width));
      rect.setAttribute("height", String(rectAttrs.height));
      svg.appendChild(rect);
    }

    // X-axis label for this column. Centered under the column's bar width.
    const columnWidth = PLOT_WIDTH / totalColumns;
    const columnCenter =
      AXIS_LEFT_PADDING + columnIndex * columnWidth + columnWidth / 2;
    const xLabel = document.createElementNS(SVG_NAMESPACE, "text");
    xLabel.setAttribute("class", "MetricsAxisLabel MetricsAxisLabelX");
    xLabel.setAttribute("x", String(columnCenter));
    xLabel.setAttribute("y", String(xLabelY));
    xLabel.setAttribute("text-anchor", "middle");
    xLabel.textContent = batchSizeBucket;
    svg.appendChild(xLabel);
  }
}
