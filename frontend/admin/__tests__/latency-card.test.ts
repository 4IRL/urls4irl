/**
 * Renderer tests for the Backend Performance (Latency) tab (`latency-card.ts`).
 * Pure DOM renderer — only the global APP_CONFIG.strings mock from
 * `test-setup.ts` is needed.
 *
 * Happy path: a populated percentile response renders one `.latency-row` per
 * endpoint with formatted p50/p95/p99 + sample count.
 * Sad path: a zero-row response renders the HTML empty-state row; a filter that
 * excludes all rows renders the no-match row.
 * No-selection: with `selectedEndpoint = null`, the detail container shows the
 * `<p class="latency-detail-prompt">` and no `<svg>`.
 * On-select: `renderLatencyDetailChart` replaces the prompt with an `<svg>`.
 */

import type { Schema } from "../../types/api-helpers.d.ts";

import { APP_CONFIG } from "../../lib/config.js";
import {
  renderLatencyDetailChart,
  renderLatencyPanel,
} from "../latency-card.js";

type LatencyPercentilesResponse = Schema<"LatencyPercentilesResponseSchema">;
type LatencyPercentileRow = Schema<"LatencyPercentileRow">;
type LatencyTimeseriesResponse = Schema<"LatencyTimeseriesResponseSchema">;

const WINDOW_START = "2026-06-01T00:00:00+00:00";
const WINDOW_END = "2026-06-02T00:00:00+00:00";

function buildRow(
  overrides: Partial<LatencyPercentileRow> = {},
): LatencyPercentileRow {
  return {
    endpoint: "utubs.get_utub",
    method: "GET",
    p50: 12.4,
    p95: 48.9,
    p99: 95.1,
    sample_count: 42,
    ...overrides,
  };
}

function buildResponse(
  rows: LatencyPercentileRow[],
): LatencyPercentilesResponse {
  return {
    window: "day",
    window_start: WINDOW_START,
    window_end: WINDOW_END,
    rows,
  };
}

function buildTimeseries(): LatencyTimeseriesResponse {
  return {
    window: "day",
    window_start: WINDOW_START,
    window_end: WINDOW_END,
    endpoint: "utubs.get_utub",
    method: "GET",
    buckets: [
      {
        bucket: "2026-06-01T00:00:00+00:00",
        p50: 10,
        p95: 50,
        p99: 100,
        sample_count: 5,
      },
      {
        bucket: "2026-06-01T01:00:00+00:00",
        p50: 20,
        p95: 60,
        p99: 120,
        sample_count: 8,
      },
    ],
  };
}

function buildRoots(): { table: HTMLTableElement; detail: HTMLElement } {
  const table = document.createElement("table");
  table.appendChild(document.createElement("thead"));
  table.appendChild(document.createElement("tbody"));
  const detail = document.createElement("div");
  return { table, detail };
}

describe("renderLatencyPanel (happy path)", () => {
  it("renders one row per endpoint with formatted percentiles + samples", () => {
    const { table, detail } = buildRoots();
    renderLatencyPanel({
      tableRoot: table,
      detailRoot: detail,
      response: buildResponse([
        buildRow({ endpoint: "utubs.get_utub", p50: 12.4 }),
        buildRow({
          endpoint: "urls.add_url",
          method: "POST",
          p50: 88.6,
          p95: 210.2,
          p99: 410.9,
          sample_count: 17,
        }),
      ]),
    });

    const headers = Array.from(
      table.querySelectorAll<HTMLElement>("thead th"),
    ).map((th) => th.textContent);
    expect(headers).toEqual([
      "Endpoint",
      "p50 (ms)",
      "p95 (ms)",
      "p99 (ms)",
      "Samples",
    ]);

    const rows = table.querySelectorAll<HTMLElement>(".latency-row");
    expect(rows.length).toBe(2);
    expect(rows[0]!.dataset.endpoint).toBe("utubs.get_utub");

    const firstCells = rows[0]!.querySelectorAll("td");
    expect(firstCells[0]!.textContent).toBe("GET utubs.get_utub");
    expect(firstCells[1]!.textContent).toBe("12");
    expect(firstCells[2]!.textContent).toBe("49");
    expect(firstCells[3]!.textContent).toBe("95");
    expect(firstCells[4]!.textContent).toBe("42");
  });

  it("labels each value cell with its column header + unit via data-label (mobile card layout)", () => {
    const { table, detail } = buildRoots();
    renderLatencyPanel({
      tableRoot: table,
      detailRoot: detail,
      response: buildResponse([buildRow()]),
    });

    const row = table.querySelector<HTMLElement>(".latency-row")!;
    const metricCells = row.querySelectorAll<HTMLElement>("td.metric");
    expect(Array.from(metricCells).map((cell) => cell.dataset.label)).toEqual([
      "p50 (ms)",
      "p95 (ms)",
      "p99 (ms)",
    ]);

    const samplesCell = row.querySelector<HTMLElement>("td.samples")!;
    expect(samplesCell.dataset.label).toBe("Samples");

    // The endpoint cell is the card heading on mobile — no inline data-label.
    const endpointCell = row.querySelector<HTMLElement>("td.endpoint")!;
    expect(endpointCell.dataset.label).toBeUndefined();
  });

  it("makes each row a focusable button widget with a summary aria-label", () => {
    const { table, detail } = buildRoots();
    renderLatencyPanel({
      tableRoot: table,
      detailRoot: detail,
      response: buildResponse([buildRow()]),
    });

    const row = table.querySelector<HTMLElement>(".latency-row")!;
    expect(row.getAttribute("role")).toBe("button");
    expect(row.tabIndex).toBe(0);
    expect(row.getAttribute("aria-label")).toBe(
      "GET utubs.get_utub: p50 12 ms, p95 49 ms, p99 95 ms",
    );
  });

  it("marks the selected row with aria-current", () => {
    const { table, detail } = buildRoots();
    renderLatencyPanel({
      tableRoot: table,
      detailRoot: detail,
      response: buildResponse([
        buildRow({ endpoint: "utubs.get_utub", method: "GET" }),
        buildRow({ endpoint: "urls.add_url", method: "POST" }),
      ]),
      selectedEndpoint: "urls.add_url",
      selectedMethod: "POST",
    });

    const selected = table.querySelector<HTMLElement>(
      ".latency-row--selected",
    )!;
    expect(selected.dataset.endpoint).toBe("urls.add_url");
    expect(selected.getAttribute("aria-current")).toBe("true");
    expect(table.querySelectorAll(".latency-row--selected").length).toBe(1);
  });

  it("renders the en-dash placeholder with suppressed aria for a null percentile", () => {
    const { table, detail } = buildRoots();
    renderLatencyPanel({
      tableRoot: table,
      detailRoot: detail,
      response: buildResponse([buildRow({ p99: null })]),
    });

    const cells = table.querySelectorAll<HTMLElement>(".latency-row td.metric");
    const p99Cell = cells[2]!;
    expect(p99Cell.textContent).toBe("–");
    expect(p99Cell.getAttribute("aria-label")).toBe("Value unavailable");
  });
});

describe("renderLatencyPanel (sad path)", () => {
  it("renders the HTML empty-state row for a zero-row response", () => {
    const { table, detail } = buildRoots();
    renderLatencyPanel({
      tableRoot: table,
      detailRoot: detail,
      response: buildResponse([]),
    });

    expect(table.querySelectorAll(".latency-row").length).toBe(0);
    const emptyRow = table.querySelector(".MetricsLatencyEmptyRow td")!;
    expect(emptyRow.getAttribute("colspan")).toBe("5");
    expect(emptyRow.textContent).toBe(APP_CONFIG.strings.METRICS_LATENCY_EMPTY);
  });

  it("renders the no-match row when the filter excludes every row", () => {
    const { table, detail } = buildRoots();
    renderLatencyPanel({
      tableRoot: table,
      detailRoot: detail,
      response: buildResponse([buildRow()]),
      filterQuery: "no_such_endpoint",
    });

    expect(table.querySelectorAll(".latency-row").length).toBe(0);
    expect(table.querySelector(".MetricsLatencyEmptyRow td")!.textContent).toBe(
      APP_CONFIG.strings.METRICS_TOP_EMPTY_NO_MATCHES,
    );
  });
});

describe("renderLatencyPanel no-selection state", () => {
  it("shows the prompt and no chart when no endpoint is selected", () => {
    const { table, detail } = buildRoots();
    renderLatencyPanel({
      tableRoot: table,
      detailRoot: detail,
      response: buildResponse([buildRow()]),
      selectedEndpoint: null,
    });

    const prompt = detail.querySelector<HTMLElement>(".latency-detail-prompt")!;
    expect(prompt).not.toBeNull();
    expect(prompt.textContent).toBe(
      APP_CONFIG.strings.METRICS_LATENCY_SELECT_PROMPT,
    );
    expect(detail.querySelector("svg")).toBeNull();
  });
});

describe("renderLatencyDetailChart on-select", () => {
  it("replaces the prompt with an SVG chart for the selected endpoint", () => {
    const { table, detail } = buildRoots();
    // Start in the no-selection state — prompt visible.
    renderLatencyPanel({
      tableRoot: table,
      detailRoot: detail,
      response: buildResponse([buildRow()]),
      selectedEndpoint: null,
    });
    expect(detail.querySelector(".latency-detail-prompt")).not.toBeNull();

    renderLatencyDetailChart({
      container: detail,
      response: buildTimeseries(),
    });

    expect(detail.querySelector(".latency-detail-prompt")).toBeNull();
    const svg = detail.querySelector("svg.latency-chart")!;
    expect(svg).not.toBeNull();
    expect(svg.querySelectorAll("polyline").length).toBe(3);
  });
});
