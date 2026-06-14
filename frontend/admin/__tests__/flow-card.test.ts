import type { Schema } from "../../types/api-helpers.d.ts";
import type { FlowId } from "../../types/metrics-flows.js";

import { renderFlowCard, renderFlowGrid } from "../flow-card.js";

type FlowResponseSchema = Schema<"FlowResponseSchema">;
type FlowStepSchema = Schema<"FlowStepSchema">;
type FlowBreakdownRow = Schema<"FlowBreakdownRow">;

function buildStep(overrides: Partial<FlowStepSchema> = {}): FlowStepSchema {
  return {
    stream: "ui",
    label: "Open form",
    event_name: "ui_url_create_open",
    count: 100,
    pct_of_top: 1.0,
    breakdown: null,
    ...overrides,
  };
}

function buildBreakdownRow(
  overrides: Partial<FlowBreakdownRow> = {},
): FlowBreakdownRow {
  return {
    label: "escape_key",
    count: 10,
    pct_of_step: 1.0,
    ...overrides,
  };
}

/** A realistic 4-step add-url funnel response. */
function buildAddUrlResponse(): FlowResponseSchema {
  return {
    steps: [
      buildStep({
        stream: "ui",
        label: "Open URL form",
        event_name: "ui_url_create_open",
        count: 200,
        pct_of_top: 1.0,
      }),
      buildStep({
        stream: "ui",
        label: "Submit",
        event_name: "ui_form_submit",
        count: 160,
        pct_of_top: 0.8,
        breakdown: [
          buildBreakdownRow({
            label: "escape_key",
            count: 30,
            pct_of_step: 0.75,
          }),
          buildBreakdownRow({
            label: "outside_click",
            count: 10,
            pct_of_step: 0.25,
          }),
        ],
      }),
      buildStep({
        stream: "api",
        label: "POST .../urls",
        event_name: "POST .../urls",
        count: 150,
        pct_of_top: 0.75,
      }),
      buildStep({
        stream: "domain",
        label: "URL added",
        event_name: "url_added_to_utub",
        count: 140,
        pct_of_top: 0.7,
        breakdown: [
          buildBreakdownRow({
            label: "invalid_url",
            count: 8,
            pct_of_step: 0.8,
          }),
          buildBreakdownRow({
            label: "url_already_in_utub",
            count: 2,
            pct_of_step: 0.2,
          }),
        ],
      }),
    ],
  };
}

describe("renderFlowCard", () => {
  it("renders N funnel-step rows and N-1 connectors for a 4-step flow", () => {
    const card = renderFlowCard({
      flowId: "add_url_to_utub",
      response: buildAddUrlResponse(),
    });

    expect(card.querySelectorAll(".funnel-step").length).toBe(4);
    expect(card.querySelectorAll(".funnel-connector").length).toBe(3);
  });

  it("loops over the response step list (2-step synthetic flow => 2 steps + 1 connector)", () => {
    // A synthetic 2-step shape that matches no real FLOWS entry — proves the
    // renderer does NOT assume exactly 4 steps.
    const response: FlowResponseSchema = {
      steps: [
        buildStep({ label: "Step 1", count: 50, pct_of_top: 1.0 }),
        buildStep({
          stream: "domain",
          label: "Step 2",
          event_name: "synthetic_done",
          count: 40,
          pct_of_top: 0.8,
        }),
      ],
    };

    const card = renderFlowCard({
      flowId: "create_utub",
      response,
    });

    expect(card.querySelectorAll(".funnel-step").length).toBe(2);
    expect(card.querySelectorAll(".funnel-connector").length).toBe(1);
  });

  it("colors each step row by stream via the .ui/.api/.domain modifier", () => {
    const card = renderFlowCard({
      flowId: "add_url_to_utub",
      response: buildAddUrlResponse(),
    });

    const steps = card.querySelectorAll(".funnel-step");
    expect(steps[0].classList.contains("ui")).toBe(true);
    expect(steps[1].classList.contains("ui")).toBe(true);
    expect(steps[2].classList.contains("api")).toBe(true);
    expect(steps[3].classList.contains("domain")).toBe(true);
  });

  it("renders per-cause cause-pill chips with the cancel/reject tint", () => {
    const card = renderFlowCard({
      flowId: "add_url_to_utub",
      response: buildAddUrlResponse(),
    });

    // The submit-step connector (preceding a ui step) carries cancel pills;
    // the domain-step connector carries reject pills.
    const cancelPills = card.querySelectorAll(".cause-pill.cancel");
    const rejectPills = card.querySelectorAll(".cause-pill.reject");
    expect(cancelPills.length).toBe(2);
    expect(rejectPills.length).toBe(2);
    expect(cancelPills[0].querySelector(".cause-label")?.textContent).toBe(
      "escape_key",
    );
  });

  it("writes --w on cause pills from pct_of_step", () => {
    const card = renderFlowCard({
      flowId: "add_url_to_utub",
      response: buildAddUrlResponse(),
    });
    const firstPill = card.querySelector(".cause-pill") as HTMLElement;
    expect(firstPill.style.getPropertyValue("--w")).toBe("75%");
  });

  it("DD-6: skips the cause-pill block when a step's breakdown is null", () => {
    // All steps have null breakdowns — only aggregate connectors should show.
    const response: FlowResponseSchema = {
      steps: [
        buildStep({ label: "Open", count: 100, pct_of_top: 1.0 }),
        buildStep({
          stream: "domain",
          label: "Done",
          event_name: "done",
          count: 80,
          pct_of_top: 0.8,
          breakdown: null,
        }),
      ],
    };

    const card = renderFlowCard({ flowId: "create_utub", response });

    expect(card.querySelectorAll(".funnel-connector").length).toBe(1);
    expect(card.querySelectorAll(".cause-pill").length).toBe(0);
    // The aggregate connector still renders its arrow + dropoff summary.
    expect(card.querySelector(".funnel-connector .arrow")).not.toBeNull();
  });

  it("DD-6: skips the cause-pill block when a step's breakdown is an empty array", () => {
    const response: FlowResponseSchema = {
      steps: [
        buildStep({ label: "Open", count: 100, pct_of_top: 1.0 }),
        buildStep({
          stream: "domain",
          label: "Done",
          event_name: "done",
          count: 80,
          pct_of_top: 0.8,
          breakdown: [],
        }),
      ],
    };

    const card = renderFlowCard({ flowId: "create_utub", response });
    expect(card.querySelectorAll(".cause-pill").length).toBe(0);
  });

  it("renders the header summary with succeeded / conversion strings", () => {
    const card = renderFlowCard({
      flowId: "add_url_to_utub",
      response: buildAddUrlResponse(),
    });
    const summary = card.querySelector(".flow-summary")?.textContent ?? "";
    expect(summary).toContain("140");
    expect(summary).toContain("200");
    expect(summary).toContain("succeeded");
    expect(summary).toContain("70%");
    expect(summary).toContain("conversion");
  });

  it("sets a screen-reader aria-label on the card", () => {
    const card = renderFlowCard({
      flowId: "add_url_to_utub",
      response: buildAddUrlResponse(),
    });
    const label = card.getAttribute("aria-label") ?? "";
    expect(label).toContain("Add URL to UTub");
    expect(label).toContain("140 of 200");
    expect(label).toContain("70%");
  });

  it("renders the focusable empty-state when all step counts are zero", () => {
    const response: FlowResponseSchema = {
      steps: [
        buildStep({ count: 0, pct_of_top: null }),
        buildStep({
          stream: "domain",
          label: "Done",
          event_name: "done",
          count: 0,
          pct_of_top: null,
        }),
      ],
    };

    const card = renderFlowCard({ flowId: "create_utub", response });
    const empty = card.querySelector(".flow-card-empty") as HTMLElement | null;
    expect(empty).not.toBeNull();
    expect(empty?.getAttribute("tabindex")).toBe("0");
    expect(empty?.textContent).toBe(
      "No funnel activity recorded in the selected window.",
    );
    expect(card.querySelectorAll(".funnel-step").length).toBe(0);
  });

  it("substitutes the en-dash placeholder when pct_of_top is null (zero-top window)", () => {
    const response: FlowResponseSchema = {
      steps: [
        buildStep({ count: 0, pct_of_top: null }),
        buildStep({
          stream: "domain",
          label: "Done",
          event_name: "done",
          count: 0,
          pct_of_top: null,
        }),
      ],
    };

    const card = renderFlowCard({ flowId: "create_utub", response });
    // Empty-state path still computes the aria-label with the placeholder.
    expect(card.getAttribute("aria-label")).toContain("–");
  });

  it("<2-step guard: renders empty-state, warns with flow id, and stays focusable", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const response: FlowResponseSchema = {
      steps: [buildStep({ label: "Lonely", count: 5, pct_of_top: 1.0 })],
    };

    const flowId: FlowId = "login";
    const card = renderFlowCard({ flowId, response });

    const empty = card.querySelector(".flow-card-empty") as HTMLElement | null;
    expect(empty).not.toBeNull();
    expect(empty?.getAttribute("tabindex")).toBe("0");
    expect(empty?.textContent).toBe(
      "No funnel activity recorded in the selected window.",
    );
    expect(warnSpy).toHaveBeenCalledWith(
      "metrics-flows: response contained fewer than 2 steps for flow",
      flowId,
      response,
    );
    warnSpy.mockRestore();
  });

  it("exposes the full event name on .step-event via aria-label", () => {
    const card = renderFlowCard({
      flowId: "add_url_to_utub",
      response: buildAddUrlResponse(),
    });
    const eventSpan = card.querySelector(".step-event") as HTMLElement;
    expect(eventSpan.getAttribute("aria-label")).toBe("ui_url_create_open");
  });

  it("sets aria-label on connectors with the continued count even when breakdown is null", () => {
    const response: FlowResponseSchema = {
      steps: [
        buildStep({ label: "Open", count: 100, pct_of_top: 1.0 }),
        buildStep({
          stream: "domain",
          label: "Done",
          event_name: "done",
          count: 80,
          pct_of_top: 0.8,
          breakdown: null,
        }),
      ],
    };

    const card = renderFlowCard({ flowId: "create_utub", response });
    const connector = card.querySelector(".funnel-connector") as HTMLElement;
    expect(connector.getAttribute("aria-label")).toContain("20");
  });
});

/** A zero-data (all step counts zero) response that renders the empty state. */
function buildEmptyResponse(): FlowResponseSchema {
  return {
    steps: [
      buildStep({ count: 0, pct_of_top: null }),
      buildStep({
        stream: "domain",
        label: "Done",
        event_name: "done",
        count: 0,
        pct_of_top: null,
      }),
    ],
  };
}

describe("renderFlowGrid", () => {
  it("tags each card with a data-flow-id matching its flow", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      responsesByFlowId: { create_utub: buildEmptyResponse() },
    });
    const card = container.querySelector(".flow-card") as HTMLElement;
    expect(card.dataset.flowId).toBe("create_utub");
  });

  it("does NOT detach an already-rendered card when an unrelated flow settles", () => {
    // Mirrors the live fan-out: the four `/flow` XHRs settle one at a time,
    // re-invoking renderFlowGrid with a growing cache. Each settle reassigns
    // exactly one cache entry, so an already-rendered flow keeps the SAME
    // response object across calls. Such a card must survive later settles so a
    // held element reference (e.g. a Selenium assertion on the empty-state
    // node) does not go stale.
    const container = document.createElement("div");
    // One stable object per flow, mirroring entries in the live `_flowCache`.
    const createUtubResponse = buildEmptyResponse();
    const addUrlResponse = buildEmptyResponse();
    const registerResponse = buildEmptyResponse();
    const loginResponse = buildEmptyResponse();

    renderFlowGrid({
      container,
      responsesByFlowId: { create_utub: createUtubResponse },
    });
    const firstCard = container.querySelector(
      '.flow-card[data-flow-id="create_utub"]',
    ) as HTMLElement;
    const firstEmptyState = firstCard.querySelector(
      ".flow-card-empty",
    ) as HTMLElement;

    renderFlowGrid({
      container,
      responsesByFlowId: {
        create_utub: createUtubResponse,
        add_url_to_utub: addUrlResponse,
        register: registerResponse,
        login: loginResponse,
      },
    });

    // Same node object — never torn out and rebuilt — so it stays attached.
    expect(container.contains(firstEmptyState)).toBe(true);
    expect(container.querySelectorAll(".flow-card").length).toBe(4);
  });

  it("replaces a flow's card in place when that flow's own response changes", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      responsesByFlowId: { create_utub: buildEmptyResponse() },
    });
    expect(container.querySelector(".flow-card-empty")).not.toBeNull();

    renderFlowGrid({
      container,
      responsesByFlowId: { create_utub: buildAddUrlResponse() },
    });
    // The card was replaced with the funnel render; still exactly one card.
    expect(container.querySelectorAll(".flow-card").length).toBe(1);
    expect(container.querySelector(".flow-card-empty")).toBeNull();
    expect(container.querySelectorAll(".funnel-step").length).toBe(4);
  });

  it("preserves FLOW_METADATA order even when flows settle out of order", () => {
    const container = document.createElement("div");
    // login settles first, then create_utub — the grid must still order
    // create_utub before login.
    renderFlowGrid({
      container,
      responsesByFlowId: { login: buildEmptyResponse() },
    });
    renderFlowGrid({
      container,
      responsesByFlowId: {
        create_utub: buildEmptyResponse(),
        login: buildEmptyResponse(),
      },
    });
    const order = Array.from(container.querySelectorAll(".flow-card")).map(
      (card) => (card as HTMLElement).dataset.flowId,
    );
    expect(order).toEqual(["create_utub", "login"]);
  });

  it("skips flows with no cached response", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      responsesByFlowId: { register: buildEmptyResponse() },
    });
    expect(container.querySelectorAll(".flow-card").length).toBe(1);
    expect(
      (container.querySelector(".flow-card") as HTMLElement).dataset.flowId,
    ).toBe("register");
  });
});
