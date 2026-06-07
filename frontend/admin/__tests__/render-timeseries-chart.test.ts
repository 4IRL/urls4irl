import type { Schema } from "../../types/api-helpers.d.ts";

import { APP_CONFIG } from "../../lib/config.js";
import { renderTimeseriesChart } from "../render-timeseries-chart.js";

type TimeseriesResponseSchema = Schema<"TimeseriesResponseSchema">;
type TimeseriesBucketSchema = Schema<"TimeseriesBucketSchema">;

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

function buildResponse(
  buckets: TimeseriesBucketSchema[],
  overrides: Partial<TimeseriesResponseSchema> = {},
): TimeseriesResponseSchema {
  return {
    event_name: "utub_opened",
    window: "day",
    resolution: "hour",
    window_start: "2026-06-06T00:00:00Z",
    window_end: "2026-06-07T00:00:00Z",
    buckets,
    ...overrides,
  };
}

describe("renderTimeseriesChart", () => {
  let svg: SVGSVGElement;

  beforeEach(() => {
    svg = document.createElementNS(
      SVG_NAMESPACE,
      "svg",
    ) as unknown as SVGSVGElement;
    svg.setAttribute("viewBox", "0 0 800 240");
    document.body.appendChild(svg);
  });

  afterEach(() => {
    svg.remove();
  });

  it("renders one <rect class='MetricsTimeseriesBar'> per bucket", () => {
    const buckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-06T00:00:00Z", count: 10 },
      { bucket: "2026-06-06T01:00:00Z", count: 25 },
      { bucket: "2026-06-06T02:00:00Z", count: 5 },
    ];
    renderTimeseriesChart({ svg, response: buildResponse(buckets) });

    const bars = svg.querySelectorAll(".MetricsTimeseriesBar");
    expect(bars.length).toBe(buckets.length);
    for (let index = 0; index < bars.length; index += 1) {
      const bar = bars[index];
      expect(bar.getAttribute("data-bucket")).toBe(buckets[index].bucket);
      expect(bar.getAttribute("data-count")).toBe(String(buckets[index].count));
    }
  });

  it("emits a non-zero number of axis lines and labels for a normal series", () => {
    const buckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-06T00:00:00Z", count: 10 },
      { bucket: "2026-06-06T01:00:00Z", count: 50 },
    ];
    renderTimeseriesChart({ svg, response: buildResponse(buckets) });

    const axisLines = svg.querySelectorAll(".MetricsAxisLine");
    const axisLabels = svg.querySelectorAll(".MetricsAxisLabel");
    expect(axisLines.length).toBeGreaterThan(0);
    expect(axisLabels.length).toBe(axisLines.length);
  });

  it("wires <title> and <desc> for screen readers", () => {
    const buckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-06T00:00:00Z", count: 7 },
      { bucket: "2026-06-06T01:00:00Z", count: 3 },
    ];
    renderTimeseriesChart({
      svg,
      response: buildResponse(buckets, { event_name: "utub_opened" }),
    });

    const titleElement = svg.querySelector("title");
    const descElement = svg.querySelector("desc");
    expect(titleElement?.textContent).toBe("utub_opened");
    expect(descElement?.textContent).toContain("utub_opened");
    expect(descElement?.textContent).toContain("10");
    expect(descElement?.textContent).toContain("2 buckets");
  });

  it("clears prior children before rendering (no leftover bars on re-render)", () => {
    const firstBuckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-06T00:00:00Z", count: 10 },
      { bucket: "2026-06-06T01:00:00Z", count: 25 },
    ];
    const secondBuckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-07T00:00:00Z", count: 99 },
    ];
    renderTimeseriesChart({ svg, response: buildResponse(firstBuckets) });
    renderTimeseriesChart({ svg, response: buildResponse(secondBuckets) });

    const bars = svg.querySelectorAll(".MetricsTimeseriesBar");
    expect(bars.length).toBe(secondBuckets.length);
  });

  it("handles an all-zero series without divide-by-zero (flat baseline)", () => {
    const buckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-06T00:00:00Z", count: 0 },
      { bucket: "2026-06-06T01:00:00Z", count: 0 },
      { bucket: "2026-06-06T02:00:00Z", count: 0 },
    ];
    renderTimeseriesChart({ svg, response: buildResponse(buckets) });

    const bars = svg.querySelectorAll(".MetricsTimeseriesBar");
    expect(bars.length).toBe(buckets.length);
    for (const bar of bars) {
      expect(Number(bar.getAttribute("height"))).toBe(0);
    }
  });

  it("renders empty-state text when buckets array is empty", () => {
    renderTimeseriesChart({ svg, response: buildResponse([]) });

    const bars = svg.querySelectorAll(".MetricsTimeseriesBar");
    expect(bars.length).toBe(0);

    const emptyState = svg.querySelector(".MetricsEmptyState");
    expect(emptyState?.textContent).toBe(
      APP_CONFIG.strings.METRICS_EMPTY_STATE,
    );
    expect(emptyState?.getAttribute("x")).toBe("400");
    expect(emptyState?.getAttribute("y")).toBe("120");
    expect(emptyState?.getAttribute("text-anchor")).toBe("middle");
    expect(emptyState?.getAttribute("dominant-baseline")).toBe("middle");
  });
});
