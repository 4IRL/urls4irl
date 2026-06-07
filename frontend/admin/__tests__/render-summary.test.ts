import type { Schema } from "../../types/api-helpers.d.ts";

import { renderSummary } from "../render-summary.js";

type SummaryResponseSchema = Schema<"SummaryResponseSchema">;

function buildSummaryResponse(
  by_category: SummaryResponseSchema["by_category"],
): SummaryResponseSchema {
  return {
    window: "day",
    window_start: "2026-06-06T00:00:00Z",
    window_end: "2026-06-07T00:00:00Z",
    previous_window_start: "2026-06-05T00:00:00Z",
    previous_window_end: "2026-06-06T00:00:00Z",
    last_flush_at: "2026-06-07T12:00:00Z",
    by_category,
  };
}

describe("renderSummary", () => {
  let root: HTMLElement;

  beforeEach(() => {
    root = document.createElement("div");
    document.body.appendChild(root);
  });

  afterEach(() => {
    root.remove();
  });

  it("renders the current count with thousands separators and percent change vs previous", () => {
    const response = buildSummaryResponse([
      { category: "ui", current: 1500, previous: 1000 },
    ]);
    renderSummary({ root, response, category: "ui" });

    const countElement = root.querySelector(".MetricsSummaryCount");
    const changeElement = root.querySelector(".MetricsSummaryChange");
    expect(countElement?.textContent).toBe((1500).toLocaleString());
    expect(changeElement?.textContent).toBe("+50.0%");
  });

  it("renders a negative percent change with a leading minus", () => {
    const response = buildSummaryResponse([
      { category: "api", current: 80, previous: 100 },
    ]);
    renderSummary({ root, response, category: "api" });

    const changeElement = root.querySelector(".MetricsSummaryChange");
    expect(changeElement?.textContent).toBe("-20.0%");
  });

  it("falls back to a placeholder when previous is zero (no divide-by-zero)", () => {
    const response = buildSummaryResponse([
      { category: "domain", current: 42, previous: 0 },
    ]);
    renderSummary({ root, response, category: "domain" });

    const countElement = root.querySelector(".MetricsSummaryCount");
    const changeElement = root.querySelector(".MetricsSummaryChange");
    expect(countElement?.textContent).toBe("42");
    expect(changeElement?.textContent).toBe("—");
  });

  it("treats a missing category row as zero current and previous", () => {
    const response = buildSummaryResponse([
      { category: "ui", current: 5, previous: 1 },
    ]);
    renderSummary({ root, response, category: "domain" });

    const countElement = root.querySelector(".MetricsSummaryCount");
    const changeElement = root.querySelector(".MetricsSummaryChange");
    expect(countElement?.textContent).toBe("0");
    expect(changeElement?.textContent).toBe("—");
  });

  it("clears prior content before rendering (no append on re-render)", () => {
    const responseA = buildSummaryResponse([
      { category: "ui", current: 100, previous: 50 },
    ]);
    const responseB = buildSummaryResponse([
      { category: "ui", current: 200, previous: 100 },
    ]);

    renderSummary({ root, response: responseA, category: "ui" });
    renderSummary({ root, response: responseB, category: "ui" });

    expect(root.querySelectorAll(".MetricsSummaryCount").length).toBe(1);
    expect(root.querySelector(".MetricsSummaryCount")?.textContent).toBe(
      (200).toLocaleString(),
    );
  });
});
