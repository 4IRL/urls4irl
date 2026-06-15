/**
 * Renderer tests for the Gauges tab (`gauge-card.ts`). The renderer is pure DOM,
 * so no jQuery/XHR mock is needed — only the global APP_CONFIG.strings mock from
 * `test-setup.ts`.
 *
 * Happy path: a full batched response renders one `.gauge-row` per gauge with
 * the correct identity, kind chip and formatted last value; with no selection
 * the detail area shows the select-a-gauge prompt and no chart. Selecting a
 * gauge renders exactly one chart (that gauge's) in the detail area and marks
 * its row. Sad path: a k-anon-suppressed series (every sample null) and an
 * empty-samples series render an en-dash value and an empty-chart detail.
 */

import type { Schema } from "../../types/api-helpers.d.ts";

import { formatGaugeLastValue, renderGaugeGrid } from "../gauge-card.js";

type GaugesTimeseriesResponse = Schema<"GaugesTimeseriesResponseSchema">;
type GaugeSeries = Schema<"GaugeSeries">;
type GaugeSampleSchema = Schema<"GaugeSampleSchema">;

const WINDOW_START = "2026-06-01T00:00:00+00:00";
const WINDOW_END = "2026-06-02T00:00:00+00:00";
const SELECT_PROMPT = "Select a gauge to view its timeseries.";

function buildSample(
  overrides: Partial<GaugeSampleSchema> = {},
): GaugeSampleSchema {
  return {
    sampled_at: "2026-06-01T01:00:00+00:00",
    value_int: 10,
    value_float: null,
    ...overrides,
  };
}

function buildSeries(overrides: Partial<GaugeSeries> = {}): GaugeSeries {
  return {
    gauge_name: "total_users",
    kind: "volume",
    description: "Total Users",
    samples: [
      buildSample({ sampled_at: "2026-06-01T01:00:00+00:00", value_int: 5 }),
      buildSample({ sampled_at: "2026-06-01T02:00:00+00:00", value_int: 8 }),
    ],
    ...overrides,
  };
}

function buildResponse(gauges: GaugeSeries[]): GaugesTimeseriesResponse {
  return {
    window: "day",
    window_start: WINDOW_START,
    window_end: WINDOW_END,
    gauges,
  };
}

/** 16 gauge series mirroring the shipped registry — distinct kinds. */
function buildFullResponse(): GaugesTimeseriesResponse {
  const names: Array<[string, string, string]> = [
    ["total_users", "volume", "Total Users"],
    ["total_utubs", "volume", "Total UTubs"],
    ["total_urls", "volume", "Total URLs"],
    ["total_tags", "volume", "Total Tags"],
    ["total_utub_url_associations", "volume", "Total UTub-URL Associations"],
    ["max_urls_per_utub", "distribution_max", "Max URLs per UTub"],
    ["avg_urls_per_utub", "distribution_avg", "Avg URLs per UTub"],
    ["max_tags_per_url", "distribution_max", "Max Tags per URL"],
    ["avg_tags_per_url", "distribution_avg", "Avg Tags per URL"],
    ["max_tags_per_utub", "distribution_max", "Max Tags per UTub"],
    ["avg_tags_per_utub", "distribution_avg", "Avg Tags per UTub"],
    ["max_utubs_per_user", "distribution_max", "Max UTubs per User"],
    ["max_members_per_utub", "distribution_max", "Max Members per UTub"],
    ["avg_members_per_utub", "distribution_avg", "Avg Members per UTub"],
    ["max_utubs_per_url", "distribution_max", "Max UTubs per URL"],
    ["max_urls_per_user", "distribution_max", "Max URLs per User"],
  ];
  return buildResponse(
    names.map(([gauge_name, kind, description]) =>
      buildSeries({
        gauge_name,
        kind,
        description,
        samples:
          kind === "distribution_avg"
            ? [
                buildSample({ value_int: null, value_float: 2.5 }),
                buildSample({ value_int: null, value_float: 3.25 }),
              ]
            : [buildSample({ value_int: 4 }), buildSample({ value_int: 7 })],
      }),
    ),
  );
}

describe("renderGaugeGrid table (happy path)", () => {
  it("renders a 2-column table with one row per gauge in response order", () => {
    const container = document.createElement("div");
    renderGaugeGrid({ container, response: buildFullResponse() });

    const headers = container.querySelectorAll<HTMLElement>(".gauge-table th");
    expect(Array.from(headers).map((th) => th.textContent)).toEqual([
      "Gauge",
      "Value",
    ]);

    const rows = container.querySelectorAll<HTMLElement>(".gauge-row");
    expect(rows.length).toBe(16);
    expect(rows[0]!.dataset.gaugeName).toBe("total_users");
    expect(rows[5]!.dataset.gaugeName).toBe("max_urls_per_utub");

    // No charts are rendered until a row is selected.
    expect(container.querySelectorAll("svg.gauge-chart").length).toBe(0);
  });

  it("renders the bridged kind chip and formatted last value per row", () => {
    const container = document.createElement("div");
    renderGaugeGrid({ container, response: buildFullResponse() });

    const volumeRow = container.querySelector<HTMLElement>(
      '.gauge-row[data-gauge-name="total_users"]',
    )!;
    expect(volumeRow.querySelector(".gauge-kind")!.textContent).toBe("Volume");
    expect(volumeRow.querySelector(".gauge-value-cell")!.textContent).toBe("7");

    const avgRow = container.querySelector<HTMLElement>(
      '.gauge-row[data-gauge-name="avg_urls_per_utub"]',
    )!;
    expect(avgRow.querySelector(".gauge-kind")!.textContent).toBe(
      "Distribution (avg)",
    );
    expect(avgRow.querySelector(".gauge-value-cell")!.textContent).toBe("3.25");
  });

  it("makes each row a focusable button widget with a summary aria-label", () => {
    const container = document.createElement("div");
    renderGaugeGrid({
      container,
      response: buildResponse([
        buildSeries({
          description: "Total Users",
          samples: [buildSample({ value_int: 42 })],
        }),
      ]),
    });

    const row = container.querySelector<HTMLElement>(".gauge-row")!;
    expect(row.getAttribute("role")).toBe("button");
    expect(row.tabIndex).toBe(0);
    expect(row.getAttribute("aria-label")).toBe("Total Users: 42");
  });
});

describe("renderGaugeGrid detail area", () => {
  it("shows the select-a-gauge prompt and no chart when nothing is selected", () => {
    const container = document.createElement("div");
    renderGaugeGrid({ container, response: buildFullResponse() });

    const prompt = container.querySelector<HTMLElement>(".gauge-detail-prompt");
    expect(prompt).not.toBeNull();
    expect(prompt!.textContent).toBe(SELECT_PROMPT);
    expect(container.querySelector("svg.gauge-chart")).toBeNull();
  });

  it("renders only the selected gauge's chart with a plotted line", () => {
    const container = document.createElement("div");
    renderGaugeGrid({
      container,
      response: buildFullResponse(),
      selectedGaugeName: "total_users",
    });

    const charts = container.querySelectorAll<SVGSVGElement>("svg.gauge-chart");
    expect(charts.length).toBe(1);
    const chart = charts[0]!;
    expect(chart.getAttribute("id")).toBe("gauge-chart-total_users");
    expect(chart.querySelector("polyline")).not.toBeNull();
    expect(container.querySelector(".gauge-detail-prompt")).toBeNull();

    // Detail title is the human description, and the SVG <title> mirrors it.
    expect(container.querySelector(".gauge-detail-title")!.textContent).toBe(
      "Total Users",
    );
    expect(chart.querySelector("title")!.textContent).toBe("Total Users");
  });

  it("marks the selected row with the selected class and aria-current", () => {
    const container = document.createElement("div");
    renderGaugeGrid({
      container,
      response: buildFullResponse(),
      selectedGaugeName: "total_urls",
    });

    const selectedRow = container.querySelector<HTMLElement>(
      ".gauge-row--selected",
    )!;
    expect(selectedRow.dataset.gaugeName).toBe("total_urls");
    expect(selectedRow.getAttribute("aria-current")).toBe("true");
    // Exactly one row is selected.
    expect(container.querySelectorAll(".gauge-row--selected").length).toBe(1);
  });

  it("falls back to the prompt when the selected gauge is absent", () => {
    const container = document.createElement("div");
    renderGaugeGrid({
      container,
      response: buildResponse([buildSeries()]),
      selectedGaugeName: "no_such_gauge",
    });

    expect(container.querySelector(".gauge-detail-prompt")!.textContent).toBe(
      SELECT_PROMPT,
    );
    expect(container.querySelector("svg.gauge-chart")).toBeNull();
  });
});

describe("renderGaugeGrid sad path (suppressed / empty)", () => {
  it("renders an en-dash value row for an all-null max gauge", () => {
    const container = document.createElement("div");
    const suppressed = buildSeries({
      gauge_name: "max_urls_per_utub",
      kind: "distribution_max",
      description: "Max URLs per UTub",
      samples: [
        buildSample({ value_int: null, value_float: null }),
        buildSample({ value_int: null, value_float: null }),
      ],
    });
    renderGaugeGrid({ container, response: buildResponse([suppressed]) });

    const row = container.querySelector<HTMLElement>(".gauge-row")!;
    expect(row.classList.contains("gauge-row--suppressed")).toBe(true);
    const valueCell = row.querySelector(".gauge-value-cell")!;
    expect(valueCell.textContent).toBe("–");
    expect(valueCell.getAttribute("aria-label")).toBe("Value unavailable");
  });

  it("renders an empty-chart detail when an all-null gauge is selected", () => {
    const container = document.createElement("div");
    const suppressed = buildSeries({
      gauge_name: "max_urls_per_utub",
      description: "Max URLs per UTub",
      samples: [buildSample({ value_int: null, value_float: null })],
    });
    renderGaugeGrid({
      container,
      response: buildResponse([suppressed]),
      selectedGaugeName: "max_urls_per_utub",
    });

    const svg = container.querySelector("svg.gauge-chart")!;
    expect(svg.querySelector(".MetricsEmptyState")).not.toBeNull();
    expect(svg.querySelector("polyline")).toBeNull();
    expect(svg.innerHTML).not.toContain("NaN");
  });

  it("renders an empty-chart detail for an empty samples array", () => {
    const container = document.createElement("div");
    const empty = buildSeries({
      gauge_name: "total_tags",
      description: "Total Tags",
      samples: [],
    });
    renderGaugeGrid({
      container,
      response: buildResponse([empty]),
      selectedGaugeName: "total_tags",
    });

    const svg = container.querySelector("svg.gauge-chart")!;
    expect(svg.querySelector(".MetricsEmptyState")).not.toBeNull();
    expect(svg.querySelector("polyline")).toBeNull();
    expect(svg.querySelectorAll("circle").length).toBe(0);
  });
});

describe("formatGaugeLastValue", () => {
  it("formats the last non-null int sample as a grouped integer", () => {
    expect(
      formatGaugeLastValue({ samples: [buildSample({ value_int: 1234 })] }),
    ).toBe("1,234");
  });

  it("formats the last non-null float sample with fraction digits", () => {
    expect(
      formatGaugeLastValue({
        samples: [buildSample({ value_int: null, value_float: 4 })],
      }),
    ).toBe("4.0");
  });

  it("returns the en-dash placeholder when all samples are null", () => {
    expect(
      formatGaugeLastValue({
        samples: [buildSample({ value_int: null, value_float: null })],
      }),
    ).toBe("–");
  });
});
