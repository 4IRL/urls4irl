/**
 * Render a timeseries response into a bar-chart SVG. Clears all children,
 * computes the y-domain from the bucket counts, places one `<rect>` per
 * bucket, and lays out a y-axis with `<line>`/`<text>` tick labels.
 *
 * Wires `<title>` and `<desc>` content for screen readers; the SVG itself
 * already references those nodes via `aria-labelledby`/`aria-describedby` in
 * the template, so populating the text content here makes the chart announce
 * its summary on focus.
 *
 * Empty state: when no buckets are returned, append a single centered
 * `<text>` with `APP_CONFIG.strings.METRICS_EMPTY_STATE`, parallel to the
 * empty-state row rendered by `renderTopTable`.
 *
 * Pure DOM mutation; no fetching, no event binding.
 */

import type { Schema } from "../types/api-helpers.d.ts";

import { APP_CONFIG } from "../lib/config.js";
import { buildAxisTicks } from "../lib/charts/axis.js";
import { buildBarAttrs } from "../lib/charts/bar.js";
import { linearScale, niceTicks } from "../lib/charts/scale.js";

type TimeseriesResponseSchema = Schema<"TimeseriesResponseSchema">;

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

// Matches the panel template's `viewBox="0 0 800 240"`. The drawing area is
// inset for the y-axis tick labels on the left.
const VIEWBOX_WIDTH = 800;
const VIEWBOX_HEIGHT = 240;
const AXIS_LEFT_PADDING = 40;
const AXIS_BOTTOM_PADDING = 30;
const PLOT_WIDTH = VIEWBOX_WIDTH - AXIS_LEFT_PADDING;
const PLOT_HEIGHT = VIEWBOX_HEIGHT - AXIS_BOTTOM_PADDING;
const Y_AXIS_TICK_COUNT = 5;

// Centered empty-state coordinates within the viewBox. Chosen for visual
// parity with the panel's text-block placement.
const EMPTY_STATE_TEXT_X = 400;
const EMPTY_STATE_TEXT_Y = 120;

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

function appendEmptyState({ svg }: { svg: SVGSVGElement }): void {
  const emptyText = document.createElementNS(SVG_NAMESPACE, "text");
  emptyText.setAttribute("x", String(EMPTY_STATE_TEXT_X));
  emptyText.setAttribute("y", String(EMPTY_STATE_TEXT_Y));
  emptyText.setAttribute("text-anchor", "middle");
  emptyText.setAttribute("dominant-baseline", "middle");
  emptyText.setAttribute("class", "MetricsEmptyState");
  emptyText.textContent = APP_CONFIG.strings.METRICS_EMPTY_STATE;
  svg.appendChild(emptyText);
}

export function renderTimeseriesChart({
  svg,
  response,
}: {
  svg: SVGSVGElement;
  response: TimeseriesResponseSchema;
}): void {
  clearSvgChildren({ svg });

  if (response.buckets.length === 0) {
    appendTitleAndDesc({
      svg,
      titleText: response.event_name,
      descText: APP_CONFIG.strings.METRICS_EMPTY_STATE,
    });
    appendEmptyState({ svg });
    return;
  }

  const bucketCounts = response.buckets.map((bucket) => bucket.count);
  const maxCount = Math.max(...bucketCounts);

  // y-domain: zero up to the nearest "nice" tick at or above the max. Using
  // `niceTicks` here keeps the top axis label aligned to a round number. When
  // the entire series is zero, fall back to a domain of [0, 1] so the bars
  // render as a flat zero baseline rather than collapsing to a divide-by-zero.
  const yDomainMax = maxCount === 0 ? 1 : maxCount;
  const scaleY = linearScale({
    domain: [0, yDomainMax],
    range: [PLOT_HEIGHT, 0],
  });
  const yTicks = niceTicks({
    min: 0,
    max: yDomainMax,
    count: Y_AXIS_TICK_COUNT,
  });
  const axisTicks = buildAxisTicks({
    ticks: yTicks,
    scale: scaleY,
    axisLength: PLOT_HEIGHT,
  });

  appendTitleAndDesc({
    svg,
    titleText: response.event_name,
    descText: `${response.event_name}: ${bucketCounts.reduce((sum, count) => sum + count, 0).toLocaleString()} total across ${response.buckets.length} buckets`,
  });

  // y-axis tick lines + labels. Drawn before bars so bars layer on top.
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

  // Bars: one `<rect>` per bucket, sized via the shared `buildBarAttrs`
  // primitive against the plot area's width/height.
  const totalBuckets = response.buckets.length;
  for (let index = 0; index < totalBuckets; index += 1) {
    const bucket = response.buckets[index];
    const barAttrs = buildBarAttrs({
      value: bucket.count,
      index,
      total: totalBuckets,
      width: PLOT_WIDTH,
      height: PLOT_HEIGHT,
      scaleY,
    });
    const barRect = document.createElementNS(SVG_NAMESPACE, "rect");
    barRect.setAttribute("class", "MetricsTimeseriesBar");
    barRect.setAttribute("x", String(barAttrs.x + AXIS_LEFT_PADDING));
    barRect.setAttribute("y", String(barAttrs.y));
    barRect.setAttribute("width", String(barAttrs.width));
    barRect.setAttribute("height", String(barAttrs.height));
    barRect.setAttribute("data-bucket", bucket.bucket);
    barRect.setAttribute("data-count", String(bucket.count));
    svg.appendChild(barRect);
  }
}
