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

  it("places the data max strictly below the top y-axis tick so the peak has headroom", () => {
    // Peak count = 11. niceTicks([0, 11], 5) lands on 12.5 (already strictly
    // above 11) so the y-axis renders [0, 2.5, 5, 7.5, 10, 12.5] and the
    // peak point's cy sits below the y=0 viewBox edge (i.e. yMin > 0 in
    // viewBox coords because 0 maps to PLOT_HEIGHT and 12.5 maps to 0).
    const buckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-06T00:00:00Z", count: 2 },
      { bucket: "2026-06-06T01:00:00Z", count: 11 },
      { bucket: "2026-06-06T02:00:00Z", count: 10 },
    ];
    renderTimeseriesChart({ svg, response: buildResponse(buckets) });

    const yLabels = Array.from(
      svg.querySelectorAll(".MetricsAxisLabel:not(.MetricsAxisLabelX)"),
    ).map((node) => Number(node.textContent));
    const topTick = Math.max(...yLabels);
    expect(topTick).toBeGreaterThan(11);

    const peakDot = Array.from(
      svg.querySelectorAll<SVGCircleElement>(".MetricsTimeseriesPoint"),
    ).find((dot) => dot.getAttribute("data-count") === "11");
    expect(peakDot).toBeDefined();
    // Peak cy is below the top of the plot (viewBox y=0) because the top tick
    // is strictly greater than the data max — concretely, > 0 in viewBox coords.
    expect(Number(peakDot!.getAttribute("cy"))).toBeGreaterThan(0);
  });

  it("when data max equals a nice round tick, extends the y-axis one step further so the peak still has headroom", () => {
    // count=10 lands exactly on a nice round tick (niceTicks([0,10],5) yields
    // [0, 2.5, 5, 7.5, 10]). Without the headroom guard, the peak would sit
    // at the very top of the plot (y=0) — the renderer must extend by one
    // step (here 2.5) so the top tick becomes 12.5.
    const buckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-06T00:00:00Z", count: 4 },
      { bucket: "2026-06-06T01:00:00Z", count: 10 },
    ];
    renderTimeseriesChart({ svg, response: buildResponse(buckets) });

    const yLabels = Array.from(
      svg.querySelectorAll(".MetricsAxisLabel:not(.MetricsAxisLabelX)"),
    ).map((node) => Number(node.textContent));
    const topTick = Math.max(...yLabels);
    expect(topTick).toBe(12.5);

    const peakDot = Array.from(
      svg.querySelectorAll<SVGCircleElement>(".MetricsTimeseriesPoint"),
    ).find((dot) => dot.getAttribute("data-count") === "10");
    expect(Number(peakDot!.getAttribute("cy"))).toBeGreaterThan(0);
  });

  it("renders a rotated Y-axis title with the configured label string", () => {
    const buckets: TimeseriesBucketSchema[] = [
      { bucket: "2026-06-06T00:00:00Z", count: 5 },
      { bucket: "2026-06-06T01:00:00Z", count: 10 },
    ];
    renderTimeseriesChart({ svg, response: buildResponse(buckets) });

    const yAxisTitle = svg.querySelector(".MetricsAxisTitle");
    expect(yAxisTitle).not.toBeNull();
    expect(yAxisTitle?.textContent).toBe(
      APP_CONFIG.strings.METRICS_CHART_Y_AXIS_LABEL,
    );
    // -90° rotation around the title's own anchor point so the text reads
    // bottom-to-top along the left edge.
    expect(yAxisTitle?.getAttribute("transform")).toMatch(/^rotate\(-90,/);
  });

  it("does not render the Y-axis title when the buckets array is empty", () => {
    renderTimeseriesChart({ svg, response: buildResponse([]) });
    expect(svg.querySelector(".MetricsAxisTitle")).toBeNull();
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
