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

import { appendEmptyState } from "./render-shared.js";

type TimeseriesResponseSchema = Schema<"TimeseriesResponseSchema">;

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

// Matches the panel template's `viewBox="0 0 800 240"`. The drawing area is
// inset for the y-axis tick labels on the left, the x-axis tick labels at
// the bottom, and a top inset so the topmost y-axis tick label has room
// to render fully inside the viewBox instead of being clipped at y=0.
const VIEWBOX_WIDTH = 800;
const VIEWBOX_HEIGHT = 240;
const AXIS_LEFT_PADDING = 56;
const AXIS_TOP_PADDING = 12;
const AXIS_BOTTOM_PADDING = 24;
const Y_AXIS_TITLE_X = 16;
const PLOT_WIDTH = VIEWBOX_WIDTH - AXIS_LEFT_PADDING;
const PLOT_HEIGHT = VIEWBOX_HEIGHT - AXIS_BOTTOM_PADDING;
const Y_AXIS_TICK_COUNT = 5;

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
    appendEmptyState({
      svg,
      message: APP_CONFIG.strings.METRICS_EMPTY_STATE,
    });
    return;
  }

  const bucketCounts = response.buckets.map((bucket) => bucket.count);
  const maxCount = Math.max(...bucketCounts);

  // y-axis ticks: compute round-number ticks covering [0, maxCount], then
  // ensure the top tick is STRICTLY GREATER than the data max so the peak
  // sits below the top axis line with visible headroom. When `niceTicks`
  // happens to land on the data max (e.g. max=10 -> ticks=[0,2.5,5,7.5,10]),
  // append one more step so the top axis value gives the peak room to breathe.
  // The y-domain max then becomes the topmost tick — this keeps every tick
  // (including the new ceiling) inside the visible plot area.
  // For an all-zero series, fall back to a [0, 1] domain so the area renders
  // against a flat baseline rather than dividing by zero.
  const baseYTicks =
    maxCount === 0
      ? niceTicks({ min: 0, max: 1, count: Y_AXIS_TICK_COUNT })
      : niceTicks({ min: 0, max: maxCount, count: Y_AXIS_TICK_COUNT });
  const baseTopTick = baseYTicks[baseYTicks.length - 1]!;
  const tickStep =
    baseYTicks.length >= 2 ? baseYTicks[1]! - baseYTicks[0]! : baseTopTick;
  const yTicks =
    baseTopTick === maxCount && maxCount > 0
      ? [...baseYTicks, baseTopTick + tickStep]
      : baseYTicks;
  const yDomainMax = yTicks[yTicks.length - 1]!;
  // Range upper bound is AXIS_TOP_PADDING (not 0) so the topmost tick label
  // sits below the viewBox top edge with enough room to render fully — the
  // `dominant-baseline="middle"` on tick labels otherwise pushes the top
  // label half-above y=0 where it gets clipped by the SVG's outer bounds.
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
    titleText: response.event_name,
    descText: `${response.event_name}: ${bucketCounts
      .reduce((sum, count) => sum + count, 0)
      .toLocaleString()} total across ${response.buckets.length} buckets`,
  });

  // Rotated y-axis title on the left edge of the plot area. Anchored at the
  // vertical center of the plot and rotated -90° around that point so the
  // text reads bottom-to-top, matching the convention for vertical axis
  // titles in most chart libraries.
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
  yAxisTitle.textContent = APP_CONFIG.strings.METRICS_CHART_Y_AXIS_LABEL;
  svg.appendChild(yAxisTitle);

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
  // For a 2-bucket series, [0, floor((2-1)/2), 1] collapses to [0, 0, 1].
  // Dedupe so two `<text>` labels never render at the same x position.
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
