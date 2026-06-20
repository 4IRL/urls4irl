/**
 * Renderer tests for the multi-series latency chart (`render-latency-chart.ts`).
 * The renderer is pure DOM, so no jQuery/XHR mock is needed — only the global
 * APP_CONFIG.strings mock from `test-setup.ts`.
 *
 * Happy path: all three percentile series populated → three polylines with the
 * correct per-series stroke-dasharray (p50 solid, p95 "6,3", p99 "2,3"), a legend
 * with dash swatches, a ms y-axis label, per-series aria-labels, and non-empty
 * <title>/<desc>.
 * Sad path (all-null): every bucket null across all series → zero polylines plus
 * the shared empty-state <text> (appendEmptyState fired).
 * Mixed-null: a null middle bucket breaks the polyline into multiple segments
 * (null-to-gap, not null-to-zero).
 */

import type { Schema } from "../../types/api-helpers.d.ts";

import { APP_CONFIG } from "../../lib/config.js";
import { renderLatencyChart } from "../render-latency-chart.js";

type LatencyTimeseriesResponse = Schema<"LatencyTimeseriesResponseSchema">;
type LatencyTimeseriesBucket = Schema<"LatencyTimeseriesBucket">;

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

function buildSvg(): SVGSVGElement {
  const svg = document.createElementNS(SVG_NAMESPACE, "svg");
  svg.setAttribute("id", "MetricsLatencyChart");
  svg.setAttribute("aria-labelledby", "MetricsLatencyChart-title");
  svg.setAttribute("aria-describedby", "MetricsLatencyChart-desc");
  const title = document.createElementNS(SVG_NAMESPACE, "title");
  title.setAttribute("id", "MetricsLatencyChart-title");
  const desc = document.createElementNS(SVG_NAMESPACE, "desc");
  desc.setAttribute("id", "MetricsLatencyChart-desc");
  svg.appendChild(title);
  svg.appendChild(desc);
  return svg as SVGSVGElement;
}

function buildBucket(
  overrides: Partial<LatencyTimeseriesBucket> = {},
): LatencyTimeseriesBucket {
  return {
    bucket: "2026-06-01T00:00:00+00:00",
    p50: 10,
    p95: 50,
    p99: 100,
    sample_count: 5,
    ...overrides,
  };
}

function buildResponse(
  buckets: LatencyTimeseriesBucket[],
): LatencyTimeseriesResponse {
  return {
    window: "day",
    window_start: "2026-06-01T00:00:00+00:00",
    window_end: "2026-06-02T00:00:00+00:00",
    endpoint: "utubs.get_utub",
    method: "GET",
    buckets,
  };
}

describe("renderLatencyChart (happy path)", () => {
  it("renders three polylines with the correct per-series dash patterns", () => {
    const svg = buildSvg();
    renderLatencyChart({
      svg,
      response: buildResponse([
        buildBucket({ bucket: "2026-06-01T00:00:00+00:00" }),
        buildBucket({
          bucket: "2026-06-01T01:00:00+00:00",
          p50: 20,
          p95: 60,
          p99: 120,
        }),
      ]),
    });

    const polylines = svg.querySelectorAll("polyline");
    expect(polylines.length).toBe(3);

    const p50 = svg.querySelector("polyline.MetricsLatencyLineP50")!;
    const p95 = svg.querySelector("polyline.MetricsLatencyLineP95")!;
    const p99 = svg.querySelector("polyline.MetricsLatencyLineP99")!;
    expect(p50.getAttribute("stroke-dasharray")).toBeNull();
    expect(p95.getAttribute("stroke-dasharray")).toBe("6,3");
    expect(p99.getAttribute("stroke-dasharray")).toBe("2,3");
  });

  it("renders a color-coded legend with dash-pattern swatches", () => {
    const svg = buildSvg();
    renderLatencyChart({ svg, response: buildResponse([buildBucket()]) });

    const legend = svg.querySelector(".MetricsLatencyLegend")!;
    expect(legend).not.toBeNull();
    const swatches = legend.querySelectorAll(".MetricsLatencyLegendSwatch");
    expect(swatches.length).toBe(3);
    // p95 swatch carries the dashed pattern; p50 swatch is solid.
    expect(
      legend
        .querySelector(".MetricsLatencyLegendSwatch.MetricsLatencyLineP95")!
        .getAttribute("stroke-dasharray"),
    ).toBe("6,3");
    expect(
      legend
        .querySelector(".MetricsLatencyLegendSwatch.MetricsLatencyLineP50")!
        .getAttribute("stroke-dasharray"),
    ).toBeNull();
  });

  it("renders the ms y-axis label and per-series aria-labels", () => {
    const svg = buildSvg();
    renderLatencyChart({ svg, response: buildResponse([buildBucket()]) });

    const axisTitle = svg.querySelector(".MetricsAxisTitle")!;
    expect(axisTitle.textContent).toBe(
      APP_CONFIG.strings.METRICS_LATENCY_Y_AXIS_LABEL,
    );

    expect(
      svg
        .querySelector("polyline.MetricsLatencyLineP95")!
        .getAttribute("aria-label"),
    ).toBe(APP_CONFIG.strings.METRICS_LATENCY_SERIES_ARIA_P95);
    expect(
      svg
        .querySelector("polyline.MetricsLatencyLineP50")!
        .getAttribute("aria-label"),
    ).toBe(APP_CONFIG.strings.METRICS_LATENCY_SERIES_ARIA_P50);
    expect(
      svg
        .querySelector("polyline.MetricsLatencyLineP99")!
        .getAttribute("aria-label"),
    ).toBe(APP_CONFIG.strings.METRICS_LATENCY_SERIES_ARIA_P99);
  });

  it("fills the SVG <title> and <desc> with non-empty text", () => {
    const svg = buildSvg();
    renderLatencyChart({ svg, response: buildResponse([buildBucket()]) });

    expect(svg.querySelector("title")!.textContent!.length).toBeGreaterThan(0);
    expect(svg.querySelector("desc")!.textContent!.length).toBeGreaterThan(0);
  });
});

describe("renderLatencyChart (sad path: all-null)", () => {
  it("renders zero polylines and the shared empty-state text", () => {
    const svg = buildSvg();
    renderLatencyChart({
      svg,
      response: buildResponse([
        buildBucket({ p50: null, p95: null, p99: null, sample_count: 0 }),
        buildBucket({
          bucket: "2026-06-01T01:00:00+00:00",
          p50: null,
          p95: null,
          p99: null,
          sample_count: 0,
        }),
      ]),
    });

    expect(svg.querySelectorAll("polyline").length).toBe(0);
    const emptyState = svg.querySelector("text.MetricsEmptyState")!;
    expect(emptyState).not.toBeNull();
    expect(emptyState.textContent).toBe(APP_CONFIG.strings.METRICS_EMPTY_STATE);
  });

  it("treats an empty buckets array as all-null", () => {
    const svg = buildSvg();
    renderLatencyChart({ svg, response: buildResponse([]) });

    expect(svg.querySelectorAll("polyline").length).toBe(0);
    expect(svg.querySelector("text.MetricsEmptyState")).not.toBeNull();
  });
});

describe("renderLatencyChart (mixed-null gaps)", () => {
  it("breaks each series into multiple segments at a null middle bucket", () => {
    const svg = buildSvg();
    renderLatencyChart({
      svg,
      response: buildResponse([
        buildBucket({ bucket: "2026-06-01T00:00:00+00:00" }),
        buildBucket({
          bucket: "2026-06-01T01:00:00+00:00",
          p50: null,
          p95: null,
          p99: null,
          sample_count: 0,
        }),
        buildBucket({
          bucket: "2026-06-01T02:00:00+00:00",
          p50: 30,
          p95: 70,
          p99: 130,
        }),
      ]),
    });

    // Each series splits into 2 segments (before + after the null bucket), so 3
    // series × 2 segments = 6 polylines. The null bucket is a gap, NOT a
    // zero-latency point — so no segment connects through it.
    const p50Segments = svg.querySelectorAll("polyline.MetricsLatencyLineP50");
    expect(p50Segments.length).toBe(2);
    // No single continuous polyline spans all three buckets.
    for (const segment of Array.from(p50Segments)) {
      const pointCount = segment
        .getAttribute("points")!
        .trim()
        .split(" ").length;
      expect(pointCount).toBe(1);
    }
    expect(svg.querySelectorAll("polyline").length).toBe(6);
  });
});
