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

  it("renders an area path, a line polyline, and one circle per bucket", () => {
    const buckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-06T00:00:00Z", count: 10 },
      { bucket: "2026-06-06T01:00:00Z", count: 25 },
      { bucket: "2026-06-06T02:00:00Z", count: 5 },
    ];
    renderTimeseriesChart({ svg, response: buildResponse(buckets) });

    const areaPath = svg.querySelector(".MetricsTimeseriesArea");
    const linePoly = svg.querySelector(".MetricsTimeseriesLine");
    const dots = svg.querySelectorAll(".MetricsTimeseriesPoint");
    expect(areaPath).not.toBeNull();
    expect(areaPath?.getAttribute("d")?.startsWith("M ")).toBe(true);
    expect(areaPath?.getAttribute("d")?.endsWith("Z")).toBe(true);
    expect(linePoly).not.toBeNull();
    expect(linePoly?.getAttribute("points")?.split(" ").length).toBe(
      buckets.length,
    );
    expect(dots.length).toBe(buckets.length);
    for (let index = 0; index < dots.length; index += 1) {
      expect(dots[index].getAttribute("data-bucket")).toBe(
        buckets[index].bucket,
      );
      expect(dots[index].getAttribute("data-count")).toBe(
        String(buckets[index].count),
      );
    }
  });

  it("emits a non-zero number of y-axis lines and labels for a normal series", () => {
    const buckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-06T00:00:00Z", count: 10 },
      { bucket: "2026-06-06T01:00:00Z", count: 50 },
    ];
    renderTimeseriesChart({ svg, response: buildResponse(buckets) });

    const axisLines = svg.querySelectorAll(".MetricsAxisLine");
    const yLabels = svg.querySelectorAll(
      ".MetricsAxisLabel:not(.MetricsAxisLabelX)",
    );
    expect(axisLines.length).toBeGreaterThan(0);
    expect(yLabels.length).toBe(axisLines.length);
  });

  it("renders three x-axis tick labels (first / middle / last) for a multi-bucket series", () => {
    const buckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-06T00:00:00Z", count: 10 },
      { bucket: "2026-06-06T01:00:00Z", count: 25 },
      { bucket: "2026-06-06T02:00:00Z", count: 5 },
      { bucket: "2026-06-06T03:00:00Z", count: 15 },
      { bucket: "2026-06-06T04:00:00Z", count: 12 },
    ];
    renderTimeseriesChart({ svg, response: buildResponse(buckets) });

    const xLabels = svg.querySelectorAll(".MetricsAxisLabelX");
    expect(xLabels.length).toBe(3);
    expect(xLabels[0].textContent).not.toBe("");
    expect(xLabels[2].textContent).not.toBe("");
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

  it("clears prior children before rendering (no leftover area/line on re-render)", () => {
    const firstBuckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-06T00:00:00Z", count: 10 },
      { bucket: "2026-06-06T01:00:00Z", count: 25 },
    ];
    const secondBuckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-07T00:00:00Z", count: 99 },
      { bucket: "2026-06-07T01:00:00Z", count: 50 },
    ];
    renderTimeseriesChart({ svg, response: buildResponse(firstBuckets) });
    renderTimeseriesChart({ svg, response: buildResponse(secondBuckets) });

    expect(svg.querySelectorAll(".MetricsTimeseriesArea").length).toBe(1);
    expect(svg.querySelectorAll(".MetricsTimeseriesPoint").length).toBe(
      secondBuckets.length,
    );
  });

  it("renders an area + line for an all-zero series without divide-by-zero", () => {
    const buckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-06T00:00:00Z", count: 0 },
      { bucket: "2026-06-06T01:00:00Z", count: 0 },
      { bucket: "2026-06-06T02:00:00Z", count: 0 },
    ];
    renderTimeseriesChart({ svg, response: buildResponse(buckets) });

    expect(svg.querySelector(".MetricsTimeseriesArea")).not.toBeNull();
    expect(svg.querySelectorAll(".MetricsTimeseriesPoint").length).toBe(
      buckets.length,
    );
  });

  it("renders empty-state text when buckets array is empty", () => {
    renderTimeseriesChart({ svg, response: buildResponse([]) });

    expect(svg.querySelectorAll(".MetricsTimeseriesArea").length).toBe(0);
    expect(svg.querySelectorAll(".MetricsTimeseriesPoint").length).toBe(0);

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
