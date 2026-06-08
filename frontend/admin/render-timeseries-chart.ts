/**
 * Render a timeseries response into an area-under-line SVG. Clears all
 * children, computes the y-domain from the bucket counts, lays out a y-axis
 * with `<line>`/`<text>` tick labels, then draws a filled `<path>` for the
 * area under the line and a `<polyline>` for the line itself. Adds three
 * x-axis labels (first / middle / last bucket).
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
import { buildPolylinePoints } from "../lib/charts/line.js";
import { linearScale, niceTicks } from "../lib/charts/scale.js";

type TimeseriesResponseSchema = Schema<"TimeseriesResponseSchema">;

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

// Matches the panel template's `viewBox="0 0 800 240"`. The drawing area is
// inset for the y-axis tick labels on the left and the x-axis tick labels at
// the bottom.
const VIEWBOX_WIDTH = 800;
const VIEWBOX_HEIGHT = 240;
const AXIS_LEFT_PADDING = 40;
const AXIS_BOTTOM_PADDING = 24;
const PLOT_WIDTH = VIEWBOX_WIDTH - AXIS_LEFT_PADDING;
const PLOT_HEIGHT = VIEWBOX_HEIGHT - AXIS_BOTTOM_PADDING;
const Y_AXIS_TICK_COUNT = 5;

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

function formatBucketLabel(bucketIso: string): string {
  const parsed = new Date(bucketIso);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    timeZone: "UTC",
  }).format(parsed);
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
  // `niceTicks` keeps the top axis label aligned to a round number. When the
  // entire series is zero, fall back to a domain of [0, 1] so the area still
  // renders against a flat baseline rather than dividing by zero.
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
    descText: `${response.event_name}: ${bucketCounts
      .reduce((sum, count) => sum + count, 0)
      .toLocaleString()} total across ${response.buckets.length} buckets`,
  });

  // y-axis tick lines + labels. Drawn before the area/line so they layer beneath.
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

  // Filled area beneath the line. Built from the same point sequence as the
  // polyline but closed back to the baseline on either end. `buildPolylinePoints`
  // emits "x,y" pairs separated by spaces — we reuse it then assemble the closed
  // path manually so the line + area share a single source of truth for x/y.
  const pointsString = buildPolylinePoints({
    values: bucketCounts,
    width: PLOT_WIDTH,
    height: PLOT_HEIGHT,
    scaleY,
  });
  if (pointsString !== "") {
    const offsetPoints = pointsString.split(" ").map((pair) => {
      const [rawX, rawY] = pair.split(",");
      return `${Number(rawX) + AXIS_LEFT_PADDING},${rawY}`;
    });
    const firstX = offsetPoints[0]!.split(",")[0]!;
    const lastX = offsetPoints[offsetPoints.length - 1]!.split(",")[0]!;
    const baselineY = String(PLOT_HEIGHT);
    const areaPath = document.createElementNS(SVG_NAMESPACE, "path");
    areaPath.setAttribute("class", "MetricsTimeseriesArea");
    areaPath.setAttribute(
      "d",
      `M ${firstX},${baselineY} L ${offsetPoints.join(" L ")} L ${lastX},${baselineY} Z`,
    );
    svg.appendChild(areaPath);

    const linePoly = document.createElementNS(SVG_NAMESPACE, "polyline");
    linePoly.setAttribute("class", "MetricsTimeseriesLine");
    linePoly.setAttribute("points", offsetPoints.join(" "));
    svg.appendChild(linePoly);

    for (
      let pointIndex = 0;
      pointIndex < offsetPoints.length;
      pointIndex += 1
    ) {
      const [pointX, pointY] = offsetPoints[pointIndex]!.split(",");
      const dot = document.createElementNS(SVG_NAMESPACE, "circle");
      dot.setAttribute("class", "MetricsTimeseriesPoint");
      dot.setAttribute("cx", pointX!);
      dot.setAttribute("cy", pointY!);
      dot.setAttribute("r", "2.5");
      dot.setAttribute("data-bucket", response.buckets[pointIndex]!.bucket);
      dot.setAttribute(
        "data-count",
        String(response.buckets[pointIndex]!.count),
      );
      svg.appendChild(dot);
    }
  }

  // x-axis labels: first, middle, last bucket. Mirrors the mock's day-name
  // labels under a weekly chart; for hourly resolution falls back to the
  // formatted timestamp.
  const xLabelIndices: number[] =
    response.buckets.length === 1
      ? [0]
      : [
          0,
          Math.floor((response.buckets.length - 1) / 2),
          response.buckets.length - 1,
        ];
  const xLabelY = VIEWBOX_HEIGHT - 6;
  const stepX =
    response.buckets.length > 1
      ? PLOT_WIDTH / (response.buckets.length - 1)
      : 0;
  for (const index of xLabelIndices) {
    const xPosition = AXIS_LEFT_PADDING + index * stepX;
    const label = document.createElementNS(SVG_NAMESPACE, "text");
    label.setAttribute("class", "MetricsAxisLabel MetricsAxisLabelX");
    label.setAttribute("x", String(xPosition));
    label.setAttribute("y", String(xLabelY));
    label.setAttribute("text-anchor", "middle");
    label.textContent = formatBucketLabel(response.buckets[index]!.bucket);
    svg.appendChild(label);
  }
}
