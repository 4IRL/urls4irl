/**
 * Shared SVG render helpers consumed by every admin metrics chart renderer.
 *
 * `appendEmptyState` appends a single centered `<text>` node to the chart's
 * SVG element. The caller passes the empty-state message verbatim so each
 * renderer can keep its own user-facing string (e.g.,
 * `METRICS_EMPTY_STATE` for the timeseries chart vs
 * `METRICS_PIPELINE_HEALTH_EMPTY_STATE` for the pipeline-health card).
 *
 * Pure DOM mutation; no fetching, no event binding, no APP_CONFIG access.
 */

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

// Matches the viewBox conventions used by every admin metrics chart
// (`viewBox="0 0 800 240"`); the centered empty-state text sits at the
// geometric center of that viewBox so it reads consistently across charts.
const EMPTY_STATE_TEXT_X = 400;
const EMPTY_STATE_TEXT_Y = 120;

export function appendEmptyState({
  svg,
  message,
}: {
  svg: SVGSVGElement;
  message: string;
}): void {
  const emptyText = document.createElementNS(SVG_NAMESPACE, "text");
  emptyText.setAttribute("x", String(EMPTY_STATE_TEXT_X));
  emptyText.setAttribute("y", String(EMPTY_STATE_TEXT_Y));
  emptyText.setAttribute("text-anchor", "middle");
  emptyText.setAttribute("dominant-baseline", "middle");
  emptyText.setAttribute("class", "MetricsEmptyState");
  emptyText.textContent = message;
  svg.appendChild(emptyText);
}
