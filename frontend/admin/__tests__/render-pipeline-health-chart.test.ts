import type { Schema } from "../../types/api-helpers.d.ts";

import { renderPipelineHealthChart } from "../render-pipeline-health-chart.js";

type GroupedTimeseriesResponseSchema =
  Schema<"GroupedTimeseriesResponseSchema">;
type GroupedTimeseriesBucket = Schema<"GroupedTimeseriesBucket">;

const SVG_NAMESPACE = "http://www.w3.org/2000/svg";

const ALL_BAR_CLASSES = [
  ".MetricsPipelineHealthBar--fetch-desktop",
  ".MetricsPipelineHealthBar--fetch-mobile",
  ".MetricsPipelineHealthBar--beacon-desktop",
  ".MetricsPipelineHealthBar--beacon-mobile",
] as const;

function buildResponse(
  buckets: GroupedTimeseriesBucket[],
  overrides: Partial<GroupedTimeseriesResponseSchema> = {},
): GroupedTimeseriesResponseSchema {
  return {
    event_name: "api_metrics_ingest_batch",
    window: "day",
    resolution: "hour",
    window_start: "2026-06-06T00:00:00Z",
    window_end: "2026-06-07T00:00:00Z",
    group_by: ["batch_size_bucket", "transport", "device_type"],
    buckets,
    ...overrides,
  };
}

describe("renderPipelineHealthChart", () => {
  let svg: SVGSVGElement;
  let legendRoot: HTMLElement;

  beforeEach(() => {
    svg = document.createElementNS(
      SVG_NAMESPACE,
      "svg",
    ) as unknown as SVGSVGElement;
    svg.setAttribute("viewBox", "0 0 800 240");
    legendRoot = document.createElement("ul");
    document.body.appendChild(svg);
    document.body.appendChild(legendRoot);
  });

  afterEach(() => {
    svg.remove();
    legendRoot.remove();
  });

  it("renders empty-state text and no rects when buckets are empty", () => {
    renderPipelineHealthChart({
      svg,
      response: buildResponse([]),
      legendRoot,
      window: "day",
    });

    for (const barClassSelector of ALL_BAR_CLASSES) {
      expect(svg.querySelectorAll(barClassSelector).length).toBe(0);
    }
    const emptyState = svg.querySelector(".MetricsEmptyState");
    expect(emptyState?.textContent).toBe(
      "No ingest batches recorded in the selected window.",
    );
  });

  it("renders four stacked rects for one bucket containing all four (transport, device_type) combinations", () => {
    const buckets: GroupedTimeseriesBucket[] = [
      {
        bucket: "2026-06-06T00:00:00Z",
        dimensions: {
          batch_size_bucket: "2-5",
          transport: "fetch",
          device_type: 2,
        },
        count: 4,
      },
      {
        bucket: "2026-06-06T00:00:00Z",
        dimensions: {
          batch_size_bucket: "2-5",
          transport: "fetch",
          device_type: 1,
        },
        count: 3,
      },
      {
        bucket: "2026-06-06T00:00:00Z",
        dimensions: {
          batch_size_bucket: "2-5",
          transport: "beacon",
          device_type: 2,
        },
        count: 2,
      },
      {
        bucket: "2026-06-06T00:00:00Z",
        dimensions: {
          batch_size_bucket: "2-5",
          transport: "beacon",
          device_type: 1,
        },
        count: 1,
      },
    ];
    renderPipelineHealthChart({
      svg,
      response: buildResponse(buckets),
      legendRoot,
      window: "day",
    });

    for (const barClassSelector of ALL_BAR_CLASSES) {
      const rects = svg.querySelectorAll(barClassSelector);
      expect(rects.length).toBe(1);
    }

    // All four rects belong to the same column ("2-5"), so their `x` is identical.
    const xValues = Array.from(svg.querySelectorAll("rect")).map((rect) =>
      Number(rect.getAttribute("x")),
    );
    const distinctX = new Set(xValues);
    expect(distinctX.size).toBe(1);

    // Stacking sanity-check: the fetch-desktop rect (bottom of stack) must
    // have the largest `y` of the four, and beacon-mobile (top of stack)
    // must have the smallest. The SVG y-axis grows downward.
    const fetchDesktopY = Number(
      svg
        .querySelector(".MetricsPipelineHealthBar--fetch-desktop")!
        .getAttribute("y"),
    );
    const beaconMobileY = Number(
      svg
        .querySelector(".MetricsPipelineHealthBar--beacon-mobile")!
        .getAttribute("y"),
    );
    expect(beaconMobileY).toBeLessThan(fetchDesktopY);
  });

  it("renders a single rect for a bucket with only one (transport, device_type) combination", () => {
    const buckets: GroupedTimeseriesBucket[] = [
      {
        bucket: "2026-06-06T00:00:00Z",
        dimensions: {
          batch_size_bucket: "1",
          transport: "fetch",
          device_type: 2,
        },
        count: 10,
      },
    ];
    renderPipelineHealthChart({
      svg,
      response: buildResponse(buckets),
      legendRoot,
      window: "day",
    });

    expect(
      svg.querySelectorAll(".MetricsPipelineHealthBar--fetch-desktop").length,
    ).toBe(1);
    expect(
      svg.querySelectorAll(".MetricsPipelineHealthBar--fetch-mobile").length,
    ).toBe(0);
    expect(
      svg.querySelectorAll(".MetricsPipelineHealthBar--beacon-desktop").length,
    ).toBe(0);
    expect(
      svg.querySelectorAll(".MetricsPipelineHealthBar--beacon-mobile").length,
    ).toBe(0);
  });

  it("renders three columns at distinct X positions when three batch-size buckets are populated", () => {
    const buckets: GroupedTimeseriesBucket[] = [
      {
        bucket: "2026-06-06T00:00:00Z",
        dimensions: {
          batch_size_bucket: "1",
          transport: "fetch",
          device_type: 2,
        },
        count: 5,
      },
      {
        bucket: "2026-06-06T00:00:00Z",
        dimensions: {
          batch_size_bucket: "6-25",
          transport: "fetch",
          device_type: 2,
        },
        count: 8,
      },
      {
        bucket: "2026-06-06T00:00:00Z",
        dimensions: {
          batch_size_bucket: "26-100",
          transport: "beacon",
          device_type: 1,
        },
        count: 2,
      },
    ];
    renderPipelineHealthChart({
      svg,
      response: buildResponse(buckets),
      legendRoot,
      window: "day",
    });

    const rects = svg.querySelectorAll("rect");
    expect(rects.length).toBe(3);
    const xValues = Array.from(rects).map((rect) =>
      Number(rect.getAttribute("x")),
    );
    expect(new Set(xValues).size).toBe(3);
    // X positions must follow the BATCH_SIZE_BUCKET_ORDER index — "1" < "6-25"
    // < "26-100", so the first rect (from the "1" column) sits left of the
    // "6-25" rect, and "6-25" sits left of "26-100".
    const sortedXValues = [...xValues].sort((a, b) => a - b);
    expect(sortedXValues).toEqual(xValues);
  });

  it("updates <title> and <desc> on non-empty render", () => {
    const buckets: GroupedTimeseriesBucket[] = [
      {
        bucket: "2026-06-06T00:00:00Z",
        dimensions: {
          batch_size_bucket: "2-5",
          transport: "fetch",
          device_type: 2,
        },
        count: 7,
      },
      {
        bucket: "2026-06-06T00:00:00Z",
        dimensions: {
          batch_size_bucket: "6-25",
          transport: "beacon",
          device_type: 1,
        },
        count: 3,
      },
    ];
    renderPipelineHealthChart({
      svg,
      response: buildResponse(buckets),
      legendRoot,
      window: "day",
    });

    const titleText = svg.querySelector("title")?.textContent ?? "";
    const descText = svg.querySelector("desc")?.textContent ?? "";
    expect(titleText).toContain("Pipeline Health");
    expect(descText).toContain("10 total batches");
  });
});
