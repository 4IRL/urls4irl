/**
 * Renderer tests for the Gauges tab cards (`gauge-card.ts`). The renderer is
 * pure DOM, so no jQuery/XHR mock is needed — only the global APP_CONFIG.strings
 * mock from `test-setup.ts`.
 *
 * Happy path: a full batched response renders one charted `.gauge-card` per
 * gauge with the correct identity, kind chip, formatted last value, and aria
 * hooks. Sad path: a k-anon-suppressed series (every sample null) and an
 * empty-samples series both render an empty-chart card without crashing.
 * Reconcile: updating one gauge replaces only its card.
 */

import type { Schema } from "../../types/api-helpers.d.ts";

import {
  formatGaugeLastValue,
  renderGaugeCard,
  renderGaugeGrid,
} from "../gauge-card.js";

type GaugesTimeseriesResponse = Schema<"GaugesTimeseriesResponseSchema">;
type GaugeSeries = Schema<"GaugeSeries">;
type GaugeSampleSchema = Schema<"GaugeSampleSchema">;

const WINDOW_START = "2026-06-01T00:00:00+00:00";
const WINDOW_END = "2026-06-02T00:00:00+00:00";

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

describe("renderGaugeGrid happy path", () => {
  it("renders one charted card per gauge in response order", () => {
    const container = document.createElement("div");
    renderGaugeGrid({ container, response: buildFullResponse() });

    const cards = container.querySelectorAll<HTMLElement>(".gauge-card");
    expect(cards.length).toBe(16);
    // First card matches the first gauge in the response (declaration order).
    expect(cards[0]!.dataset.gaugeName).toBe("total_users");
    expect(cards[5]!.dataset.gaugeName).toBe("max_urls_per_utub");

    // Each card carries a chart svg with a rendered polyline (a chart, not a
    // value card).
    cards.forEach((card) => {
      const svg = card.querySelector("svg.gauge-chart");
      expect(svg).not.toBeNull();
      expect(svg!.querySelector("polyline")).not.toBeNull();
    });
  });

  it("renders the bridged kind chip and formatted last value", () => {
    const container = document.createElement("div");
    renderGaugeGrid({ container, response: buildFullResponse() });

    const volumeCard = container.querySelector<HTMLElement>(
      '.gauge-card[data-gauge-name="total_users"]',
    )!;
    expect(volumeCard.querySelector(".gauge-kind")!.textContent).toBe("Volume");
    // Last non-null integer sample formatted with thousands grouping.
    expect(volumeCard.querySelector(".gauge-last-value")!.textContent).toBe(
      "7",
    );

    const avgCard = container.querySelector<HTMLElement>(
      '.gauge-card[data-gauge-name="avg_urls_per_utub"]',
    )!;
    expect(avgCard.querySelector(".gauge-kind")!.textContent).toBe(
      "Distribution (avg)",
    );
    // Last float sample formatted with 1–2 fraction digits.
    expect(avgCard.querySelector(".gauge-last-value")!.textContent).toBe(
      "3.25",
    );
  });

  it("sets aria hooks: role=img, labelledby->title, describedby->desc", () => {
    const card = renderGaugeCard({
      entry: buildSeries(),
      window: "day",
      window_start: WINDOW_START,
      window_end: WINDOW_END,
    });

    const svg = card.querySelector("svg.gauge-chart")!;
    expect(svg.getAttribute("role")).toBe("img");
    const labelledBy = svg.getAttribute("aria-labelledby")!;
    const describedBy = svg.getAttribute("aria-describedby")!;
    expect(svg.querySelector("title")).not.toBeNull();
    expect(svg.querySelector("desc")).not.toBeNull();
    expect(labelledBy).toBe(`${svg.getAttribute("id")}-title`);
    expect(describedBy).toBe(`${svg.getAttribute("id")}-desc`);
  });

  it("svg <title> text is the human description, not the snake_case name", () => {
    const card = renderGaugeCard({
      entry: buildSeries({
        gauge_name: "max_urls_per_utub",
        description: "Max URLs per UTub",
      }),
      window: "day",
      window_start: WINDOW_START,
      window_end: WINDOW_END,
    });

    const title = card.querySelector("svg.gauge-chart title")!;
    expect(title.textContent).toBe("Max URLs per UTub");
    expect(title.textContent).not.toBe("max_urls_per_utub");
  });

  it("sets a card-level aria-label of 'description: lastValue' (DD-9)", () => {
    const card = renderGaugeCard({
      entry: buildSeries({
        description: "Total Users",
        samples: [buildSample({ value_int: 42 })],
      }),
      window: "day",
      window_start: WINDOW_START,
      window_end: WINDOW_END,
    });
    expect(card.getAttribute("aria-label")).toBe("Total Users: 42");
  });
});

describe("renderGaugeGrid sad path (suppressed / empty)", () => {
  it("renders an empty-chart suppressed card for an all-null max gauge", () => {
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

    const card = container.querySelector<HTMLElement>(".gauge-card")!;
    expect(card.classList.contains("gauge-card--suppressed")).toBe(true);
    // Empty-chart state: the empty-state <text> renders, no polyline / no NaN.
    const svg = card.querySelector("svg.gauge-chart")!;
    expect(svg.querySelector(".MetricsEmptyState")).not.toBeNull();
    expect(svg.querySelector("polyline")).toBeNull();
    expect(svg.innerHTML).not.toContain("NaN");

    const lastValue = card.querySelector(".gauge-last-value")!;
    expect(lastValue.textContent).toBe("–");
    expect(lastValue.getAttribute("aria-label")).toBe("Value unavailable");
  });

  it("renders an empty-chart placeholder card for an empty samples array", () => {
    const container = document.createElement("div");
    const empty = buildSeries({
      gauge_name: "total_tags",
      description: "Total Tags",
      samples: [],
    });
    renderGaugeGrid({ container, response: buildResponse([empty]) });

    const card = container.querySelector<HTMLElement>(".gauge-card")!;
    expect(card.classList.contains("gauge-card--suppressed")).toBe(true);
    const svg = card.querySelector("svg.gauge-chart")!;
    expect(svg.querySelector(".MetricsEmptyState")).not.toBeNull();
    expect(svg.querySelector("polyline")).toBeNull();
  });

  it("gaugeTimeseriesToChartResponse produces zero buckets for an all-null series", () => {
    // Indirect assertion via the rendered card: an all-null series -> empty
    // chart -> no data points (circles) plotted.
    const card = renderGaugeCard({
      entry: buildSeries({
        samples: [
          buildSample({ value_int: null, value_float: null }),
          buildSample({ value_int: null, value_float: null }),
        ],
      }),
      window: "day",
      window_start: WINDOW_START,
      window_end: WINDOW_END,
    });
    expect(card.querySelectorAll("svg.gauge-chart circle").length).toBe(0);
  });
});

describe("renderGaugeGrid reconcile", () => {
  it("replaces only the updated gauge's card; other cards keep their reference", () => {
    const container = document.createElement("div");
    const seriesA = buildSeries({ gauge_name: "total_users" });
    const seriesB = buildSeries({
      gauge_name: "total_utubs",
      description: "Total UTubs",
    });
    renderGaugeGrid({ container, response: buildResponse([seriesA, seriesB]) });

    const cardARef = container.querySelector(
      '.gauge-card[data-gauge-name="total_users"]',
    );
    const cardBRef = container.querySelector(
      '.gauge-card[data-gauge-name="total_utubs"]',
    );

    // Re-render with the SAME seriesA reference but a NEW seriesB object.
    const seriesBUpdated = buildSeries({
      gauge_name: "total_utubs",
      description: "Total UTubs",
      samples: [buildSample({ value_int: 99 })],
    });
    renderGaugeGrid({
      container,
      response: buildResponse([seriesA, seriesBUpdated]),
    });

    // Card A's element reference is unchanged (same series reference).
    expect(
      container.querySelector('.gauge-card[data-gauge-name="total_users"]'),
    ).toBe(cardARef);
    // Card B was rebuilt (new series object).
    const cardBNew = container.querySelector(
      '.gauge-card[data-gauge-name="total_utubs"]',
    );
    expect(cardBNew).not.toBe(cardBRef);
    expect(cardBNew!.querySelector(".gauge-last-value")!.textContent).toBe(
      "99",
    );
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
