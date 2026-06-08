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

  it("renders four summary cards (Total + API + UI + Domain) in fixed order", () => {
    const response = buildSummaryResponse([
      { category: "api", current: 100, previous: 50 },
      { category: "ui", current: 200, previous: 150 },
      { category: "domain", current: 30, previous: 30 },
    ]);
    renderSummary({ root, response });

    const cards = root.querySelectorAll(".summary-card");
    expect(cards.length).toBe(4);
    const labels = Array.from(cards).map(
      (card) => card.querySelector(".label")?.textContent,
    );
    expect(labels).toEqual([
      "Total Events",
      "API hits",
      "UI events",
      "Domain actions",
    ]);
  });

  it("computes the Total card as the sum of all by_category.current", () => {
    const response = buildSummaryResponse([
      { category: "api", current: 100, previous: 50 },
      { category: "ui", current: 200, previous: 150 },
      { category: "domain", current: 30, previous: 30 },
    ]);
    renderSummary({ root, response });

    const totalCard = root.querySelector(".summary-card");
    expect(totalCard?.querySelector(".value")?.textContent).toBe(
      (330).toLocaleString(),
    );
  });

  it("renders an up-arrow delta with the absolute percent and ' vs prev' suffix", () => {
    const response = buildSummaryResponse([
      { category: "ui", current: 1500, previous: 1000 },
    ]);
    renderSummary({ root, response });

    const uiCard = root.querySelectorAll(".summary-card")[2];
    const delta = uiCard.querySelector(".delta");
    expect(delta?.textContent).toBe("▲ 50.0% vs prev");
    expect(delta?.classList.contains("up")).toBe(true);
  });

  it("renders a down-arrow delta and the 'down' class for a decrease", () => {
    const response = buildSummaryResponse([
      { category: "api", current: 80, previous: 100 },
    ]);
    renderSummary({ root, response });

    const apiCard = root.querySelectorAll(".summary-card")[1];
    const delta = apiCard.querySelector(".delta");
    expect(delta?.textContent).toBe("▼ 20.0% vs prev");
    expect(delta?.classList.contains("down")).toBe(true);
  });

  it("falls back to the unavailable placeholder when previous is zero", () => {
    const response = buildSummaryResponse([
      { category: "domain", current: 42, previous: 0 },
    ]);
    renderSummary({ root, response });

    const domainCard = root.querySelectorAll(".summary-card")[3];
    const value = domainCard.querySelector(".value");
    const delta = domainCard.querySelector(".delta");
    expect(value?.textContent).toBe("42");
    expect(delta?.textContent).toBe("— vs prev");
    expect(delta?.classList.contains("none")).toBe(true);
  });

  it("treats a missing category row as zero current and previous", () => {
    const response = buildSummaryResponse([
      { category: "ui", current: 5, previous: 1 },
    ]);
    renderSummary({ root, response });

    const apiCard = root.querySelectorAll(".summary-card")[1];
    expect(apiCard.querySelector(".value")?.textContent).toBe("0");
    expect(apiCard.querySelector(".delta")?.textContent).toBe("— vs prev");
  });

  it("clears prior content before rendering (no append on re-render)", () => {
    const responseA = buildSummaryResponse([
      { category: "ui", current: 100, previous: 50 },
    ]);
    const responseB = buildSummaryResponse([
      { category: "ui", current: 200, previous: 100 },
    ]);

    renderSummary({ root, response: responseA });
    renderSummary({ root, response: responseB });

    expect(root.querySelectorAll(".summary-card").length).toBe(4);
    const uiCard = root.querySelectorAll(".summary-card")[2];
    expect(uiCard.querySelector(".value")?.textContent).toBe(
      (200).toLocaleString(),
    );
  });
});
