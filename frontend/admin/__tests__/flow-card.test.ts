import type { Schema } from "../../types/api-helpers.d.ts";

import type {
  FlowCardCustom,
  FlowCardState,
  FlowGridEntry,
} from "../flow-card.js";
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
    count_suppressed: false,
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

function buildSuppressedStep(
  overrides: Partial<FlowStepSchema> = {},
): FlowStepSchema {
  return buildStep({
    count: 0,
    pct_of_top: null,
    count_suppressed: true,
    ...overrides,
  });
}

describe("renderFlowCard suppression", () => {
  const ariaText = "Count hidden to protect small groups";

  function renderTwoStep({
    top,
    last,
  }: {
    top: FlowStepSchema;
    last: FlowStepSchema;
  }): HTMLElement {
    return renderFlowCard({
      id: "probe",
      title: "Probe",
      response: { steps: [top, last] },
    });
  }

  it("renders a suppressed step as an announced en-dash with is-suppressed", () => {
    const card = renderTwoStep({
      top: buildStep({ count: 812 }),
      last: buildSuppressedStep({ stream: "domain" }),
    });

    const row = card.querySelectorAll(".funnel-step")[1];
    expect(row.classList.contains("is-suppressed")).toBe(true);
    const count = row.querySelector(".step-count") as HTMLElement;
    expect(count.textContent).toBe("–");
    expect(count.getAttribute("role")).toBe("img");
    expect(count.getAttribute("aria-label")).toBe(ariaText);
    expect(count.title).toBe(ariaText);
  });

  it("leaves a normal step unchanged", () => {
    const card = renderTwoStep({
      top: buildStep({ count: 100 }),
      last: buildStep({ count: 40, pct_of_top: 0.4 }),
    });

    const row = card.querySelectorAll(".funnel-step")[1];
    expect(row.classList.contains("is-suppressed")).toBe(false);
    const count = row.querySelector(".step-count") as HTMLElement;
    expect(count.textContent).toBe("40");
    expect(count.hasAttribute("role")).toBe(false);
  });

  it("shows an en-dash connector with the suppressed aria-label next to a suppressed step", () => {
    const card = renderTwoStep({
      top: buildStep({ count: 812 }),
      last: buildSuppressedStep(),
    });

    const connector = card.querySelector(".funnel-connector") as HTMLElement;
    expect(connector.querySelector(".arrow-dropoff")?.textContent).toBe("–");
    expect(connector.getAttribute("aria-label")).toBe(ariaText);
    expect(connector.getAttribute("aria-label")).not.toContain("drop-off");
  });

  it("renders a suppressed top step as an announced en-dash in the header and aria-label", () => {
    const card = renderTwoStep({
      top: buildSuppressedStep(),
      last: buildStep({ count: 812, pct_of_top: null }),
    });

    const summary = card.querySelector(".flow-summary") as HTMLElement;
    expect(summary.textContent).toBe("812 / – succeeded · – conversion");
    const dash = summary.querySelector("span") as HTMLElement;
    expect(dash.getAttribute("role")).toBe("img");
    expect(dash.getAttribute("aria-label")).toBe(ariaText);
    expect(dash.title).toBe(ariaText);
    expect(card.getAttribute("aria-label")).toBe(
      `Probe: 812 of ${ariaText} succeeded, – conversion`,
    );
    const connector = card.querySelector(".funnel-connector") as HTMLElement;
    expect(connector.querySelector(".arrow-dropoff")?.textContent).toBe("–");
    expect(connector.getAttribute("aria-label")).toBe(ariaText);
  });

  it("renders a suppressed last step without a 0 / N header", () => {
    const card = renderTwoStep({
      top: buildStep({ count: 812 }),
      last: buildSuppressedStep(),
    });

    const summary = card.querySelector(".flow-summary") as HTMLElement;
    expect(summary.textContent).toBe("– / 812 succeeded · – conversion");
    expect(card.getAttribute("aria-label")).toBe(
      `Probe: ${ariaText} of 812 succeeded, – conversion`,
    );
    expect(card.getAttribute("aria-label")).not.toContain("0 / 812");
  });

  it("renders a suppressed breakdown row with the bridged label and is-suppressed", () => {
    const card = renderTwoStep({
      top: buildStep({ count: 100 }),
      last: buildStep({
        count: 80,
        pct_of_top: 0.8,
        breakdown: [
          buildBreakdownRow({
            label: "suppressed",
            count: 3,
            pct_of_step: 0.3,
          }),
          buildBreakdownRow({
            label: "escape_key",
            count: 7,
            pct_of_step: 0.7,
          }),
        ],
      }),
    });

    const pills = card.querySelectorAll(".cause-pill");
    expect(pills[0].classList.contains("is-suppressed")).toBe(true);
    expect(pills[0].querySelector(".cause-label")?.textContent).toBe(
      "suppressed (fewer than 5)",
    );
    expect(pills[0].getAttribute("aria-label")).toBe(
      "suppressed (fewer than 5): 3",
    );
    expect(pills[1].classList.contains("is-suppressed")).toBe(false);
    expect(pills[1].getAttribute("aria-label")).toBe("escape_key: 7");
  });

  it("does not render the empty state for an all-suppressed funnel", () => {
    const card = renderTwoStep({
      top: buildSuppressedStep(),
      last: buildSuppressedStep(),
    });

    expect(card.querySelector(".flow-card-empty")).toBeNull();
    expect(card.querySelectorAll(".funnel-step").length).toBe(2);
  });

  it("renders every bar at full width when pct_of_top is null", () => {
    const card = renderTwoStep({
      top: buildSuppressedStep(),
      last: buildStep({ count: 10, pct_of_top: null }),
    });

    const rows = card.querySelectorAll<HTMLElement>(".funnel-step");
    rows.forEach((row) => {
      expect(row.style.getPropertyValue("--w")).toBe("100%");
    });
  });
});

describe("renderFlowCard", () => {
  it("renders N funnel-step rows and N-1 connectors for a 4-step flow", () => {
    const card = renderFlowCard({
      id: "add_url_to_utub",
      title: "Add URL to UTub",
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
      id: "create_utub",
      title: "Create UTub",
      response,
    });

    expect(card.querySelectorAll(".funnel-step").length).toBe(2);
    expect(card.querySelectorAll(".funnel-connector").length).toBe(1);
  });

  it("colors each step row by stream via the .ui/.api/.domain modifier", () => {
    const card = renderFlowCard({
      id: "add_url_to_utub",
      title: "Add URL to UTub",
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
      id: "add_url_to_utub",
      title: "Add URL to UTub",
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
      id: "add_url_to_utub",
      title: "Add URL to UTub",
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

    const card = renderFlowCard({
      id: "create_utub",
      title: "Create UTub",
      response,
    });

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

    const card = renderFlowCard({
      id: "create_utub",
      title: "Create UTub",
      response,
    });
    expect(card.querySelectorAll(".cause-pill").length).toBe(0);
  });

  it("renders the header summary with succeeded / conversion strings", () => {
    const card = renderFlowCard({
      id: "add_url_to_utub",
      title: "Add URL to UTub",
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
      id: "add_url_to_utub",
      title: "Add URL to UTub",
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

    const card = renderFlowCard({
      id: "create_utub",
      title: "Create UTub",
      response,
    });
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

    const card = renderFlowCard({
      id: "create_utub",
      title: "Create UTub",
      response,
    });
    // Empty-state path still computes the aria-label with the placeholder.
    expect(card.getAttribute("aria-label")).toContain("–");
  });

  it("exposes the full event name on .step-event via aria-label", () => {
    const card = renderFlowCard({
      id: "add_url_to_utub",
      title: "Add URL to UTub",
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

    const card = renderFlowCard({
      id: "create_utub",
      title: "Create UTub",
      response,
    });
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

function responseEntry({
  id,
  response,
}: {
  id: string;
  response: FlowResponseSchema;
}): FlowGridEntry {
  return { id, title: `Title ${id}`, state: { kind: "response", response } };
}

function stateEntry({
  id,
  state,
}: {
  id: string;
  state: FlowCardState;
}): FlowGridEntry {
  return { id, title: `Title ${id}`, state };
}

function flowIdOrder(container: HTMLElement): (string | undefined)[] {
  return Array.from(container.children).map(
    (node) => (node as HTMLElement).dataset.flowId,
  );
}

describe("renderFlowGrid", () => {
  it("tags each card with a data-flow-id matching its flow", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      entries: [
        responseEntry({ id: "create_utub", response: buildEmptyResponse() }),
      ],
    });
    const card = container.querySelector(".flow-card") as HTMLElement;
    expect(card.dataset.flowId).toBe("create_utub");
  });

  it("does NOT detach an already-rendered card when an unrelated flow settles", () => {
    // Flows settle independently (live fan-out), so each settle re-renders the
    // grid; a card whose own response is unchanged must keep its DOM node so
    // focus, scroll and in-flight state survive.
    const container = document.createElement("div");
    const createUtubResponse = buildEmptyResponse();
    renderFlowGrid({
      container,
      entries: [
        responseEntry({ id: "create_utub", response: createUtubResponse }),
      ],
    });
    const firstCard = container.querySelector(
      '.flow-card[data-flow-id="create_utub"]',
    ) as HTMLElement;
    const firstEmptyState = firstCard.querySelector(
      ".flow-card-empty",
    ) as HTMLElement;

    renderFlowGrid({
      container,
      entries: [
        responseEntry({ id: "create_utub", response: createUtubResponse }),
        responseEntry({
          id: "add_url_to_utub",
          response: buildEmptyResponse(),
        }),
        responseEntry({ id: "register", response: buildEmptyResponse() }),
        responseEntry({ id: "login", response: buildEmptyResponse() }),
      ],
    });

    expect(container.contains(firstEmptyState)).toBe(true);
    expect(container.querySelector(".flow-card")).toBe(firstCard);
    expect(container.querySelectorAll(".flow-card").length).toBe(4);
  });

  it("replaces a flow's card in place when that flow's own response changes", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      entries: [
        responseEntry({ id: "create_utub", response: buildEmptyResponse() }),
      ],
    });
    expect(container.querySelector(".flow-card-empty")).not.toBeNull();

    renderFlowGrid({
      container,
      entries: [
        responseEntry({ id: "create_utub", response: buildAddUrlResponse() }),
      ],
    });
    expect(container.querySelectorAll(".flow-card").length).toBe(1);
    expect(container.querySelector(".flow-card-empty")).toBeNull();
    expect(container.querySelectorAll(".funnel-step").length).toBe(4);
  });

  it("preserves entry order when flows settle out of order", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      entries: [responseEntry({ id: "login", response: buildEmptyResponse() })],
    });
    renderFlowGrid({
      container,
      entries: [
        responseEntry({ id: "create_utub", response: buildEmptyResponse() }),
        responseEntry({ id: "login", response: buildEmptyResponse() }),
      ],
    });
    expect(flowIdOrder(container)).toEqual(["create_utub", "login"]);
  });

  it("renders the four built-in cards with a stable DOM snapshot", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      entries: [
        {
          id: "create_utub",
          title: "Create UTub",
          state: { kind: "response", response: buildAddUrlResponse() },
        },
        {
          id: "add_url_to_utub",
          title: "Add URL to UTub",
          state: { kind: "response", response: buildAddUrlResponse() },
        },
        {
          id: "register",
          title: "Register",
          state: { kind: "response", response: buildEmptyResponse() },
        },
        {
          id: "login",
          title: "Login",
          state: { kind: "response", response: buildAddUrlResponse() },
        },
      ],
    });
    expect(container.innerHTML).toMatchSnapshot();
  });

  it("lists only the entries given (flows with no entry are skipped)", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      entries: [
        responseEntry({ id: "register", response: buildEmptyResponse() }),
      ],
    });
    expect(container.querySelectorAll(".flow-card").length).toBe(1);
    expect(
      (container.querySelector(".flow-card") as HTMLElement).dataset.flowId,
    ).toBe("register");
  });

  it("removes a card whose id leaves entries", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      entries: [
        responseEntry({ id: "alpha", response: buildEmptyResponse() }),
        responseEntry({ id: "beta", response: buildEmptyResponse() }),
      ],
    });
    renderFlowGrid({
      container,
      entries: [responseEntry({ id: "beta", response: buildEmptyResponse() })],
    });
    expect(flowIdOrder(container)).toEqual(["beta"]);
  });

  it("removes a node for a removed entry", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      entries: [responseEntry({ id: "alpha", response: buildEmptyResponse() })],
    });
    renderFlowGrid({
      container,
      entries: [stateEntry({ id: "alpha", state: { kind: "removed" } })],
    });
    expect(container.children.length).toBe(0);
  });

  it.each([
    { kind: "loading" },
    { kind: "error" },
    {
      kind: "invalid",
      invalid: { step_index: 1, field: "event_name", reason: "unknown" },
    },
  ] as FlowCardState[])(
    "renders a visible .flow-card for a $kind entry",
    (state) => {
      const container = document.createElement("div");
      renderFlowGrid({
        container,
        entries: [stateEntry({ id: "alpha", state })],
      });
      const card = container.querySelector(".flow-card") as HTMLElement;
      expect(card.tagName).toBe("SECTION");
      expect(card.hidden).toBe(false);
      expect(card.dataset.flowId).toBe("alpha");
      expect(card.dataset.flowState).toBe(state.kind);
      expect(card.getAttribute("tabindex")).toBe("-1");
      expect(container.querySelector(".flow-card-placeholder")).toBeNull();
    },
  );

  it("replaces a placeholder with a card at the same position", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      entries: [
        responseEntry({ id: "alpha", response: buildEmptyResponse() }),
        stateEntry({ id: "beta", state: { kind: "loading" } }),
        responseEntry({ id: "gamma", response: buildEmptyResponse() }),
      ],
    });
    renderFlowGrid({
      container,
      entries: [
        responseEntry({ id: "alpha", response: buildEmptyResponse() }),
        responseEntry({ id: "beta", response: buildEmptyResponse() }),
        responseEntry({ id: "gamma", response: buildEmptyResponse() }),
      ],
    });
    expect(flowIdOrder(container)).toEqual(["alpha", "beta", "gamma"]);
    expect(container.children[1].classList.contains("flow-card")).toBe(true);
  });

  it("reorders existing nodes without recreating them", () => {
    const container = document.createElement("div");
    const alphaResponse = buildEmptyResponse();
    const betaResponse = buildEmptyResponse();
    renderFlowGrid({
      container,
      entries: [
        responseEntry({ id: "alpha", response: alphaResponse }),
        responseEntry({ id: "beta", response: betaResponse }),
      ],
    });
    const alphaNode = container.children[0];
    const betaNode = container.children[1];
    renderFlowGrid({
      container,
      entries: [
        responseEntry({ id: "beta", response: betaResponse }),
        responseEntry({ id: "alpha", response: alphaResponse }),
      ],
    });
    expect(flowIdOrder(container)).toEqual(["beta", "alpha"]);
    expect(container.children[0]).toBe(betaNode);
    expect(container.children[1]).toBe(alphaNode);
  });

  it("renders one node per id when entries share an id (first wins)", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      entries: [
        responseEntry({ id: "alpha", response: buildEmptyResponse() }),
        stateEntry({ id: "alpha", state: { kind: "loading" } }),
      ],
    });
    expect(container.children.length).toBe(1);
    expect(container.children[0].classList.contains("flow-card")).toBe(true);
  });

  it("keeps the same node for an unchanged response (identity)", () => {
    const container = document.createElement("div");
    const response = buildEmptyResponse();
    renderFlowGrid({
      container,
      entries: [responseEntry({ id: "alpha", response })],
    });
    const node = container.firstElementChild;
    renderFlowGrid({
      container,
      entries: [responseEntry({ id: "alpha", response })],
    });
    expect(container.firstElementChild).toBe(node);
  });

  it.each(["loading", "error"] as const)(
    "keeps the node for a repeated %s entry",
    (kind) => {
      const container = document.createElement("div");
      renderFlowGrid({
        container,
        entries: [stateEntry({ id: "alpha", state: { kind } })],
      });
      const node = container.firstElementChild;
      renderFlowGrid({
        container,
        entries: [stateEntry({ id: "alpha", state: { kind } })],
      });
      expect(container.firstElementChild).toBe(node);
    },
  );

  describe("invalid entries compare by field equality", () => {
    const invalidState = ({
      stepIndex,
      field,
      reason,
    }: {
      stepIndex: number | null;
      field: string;
      reason: string;
    }): FlowCardState => ({
      kind: "invalid",
      invalid: { step_index: stepIndex, field, reason },
    });
    const base = { stepIndex: 2, field: "event_name", reason: "unknown" };

    it("keeps the node when every field is equal", () => {
      const container = document.createElement("div");
      renderFlowGrid({
        container,
        entries: [stateEntry({ id: "alpha", state: invalidState(base) })],
      });
      const node = container.firstElementChild;
      renderFlowGrid({
        container,
        entries: [stateEntry({ id: "alpha", state: invalidState(base) })],
      });
      expect(container.firstElementChild).toBe(node);
    });

    it.each([
      { name: "reason", change: { reason: "changed" } },
      { name: "step_index", change: { stepIndex: 3 } },
      { name: "step_index to null", change: { stepIndex: null } },
      { name: "field", change: { field: "label" } },
    ])("replaces the node when $name changes", ({ change }) => {
      const container = document.createElement("div");
      renderFlowGrid({
        container,
        entries: [stateEntry({ id: "alpha", state: invalidState(base) })],
      });
      const node = container.firstElementChild;
      renderFlowGrid({
        container,
        entries: [
          stateEntry({
            id: "alpha",
            state: invalidState({ ...base, ...change }),
          }),
        ],
      });
      expect(container.firstElementChild).not.toBe(node);
    });
  });

  it("replaces the node when the kind changes", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      entries: [stateEntry({ id: "alpha", state: { kind: "loading" } })],
    });
    const node = container.firstElementChild;
    renderFlowGrid({
      container,
      entries: [stateEntry({ id: "alpha", state: { kind: "error" } })],
    });
    expect(container.firstElementChild).not.toBe(node);
    expect((container.firstElementChild as HTMLElement).dataset.flowState).toBe(
      "error",
    );
  });

  it("replaces a response card with a loading card when a response becomes loading", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      entries: [responseEntry({ id: "alpha", response: buildEmptyResponse() })],
    });
    const node = container.firstElementChild;
    renderFlowGrid({
      container,
      entries: [stateEntry({ id: "alpha", state: { kind: "loading" } })],
    });
    expect(container.firstElementChild).not.toBe(node);
    expect((container.firstElementChild as HTMLElement).dataset.flowState).toBe(
      "loading",
    );
    expect(container.querySelectorAll(".flow-card").length).toBe(1);
  });

  it("handles ids containing selector-special characters", () => {
    const container = document.createElement("div");
    const response = buildEmptyResponse();
    const entries = [responseEntry({ id: 'we"ird]id', response })];
    renderFlowGrid({ container, entries });
    const node = container.firstElementChild;
    renderFlowGrid({ container, entries });
    expect(container.firstElementChild).toBe(node);
    expect(container.children.length).toBe(1);
  });
});

describe("renderFlowGrid custom cards, badges and states", () => {
  const CLOSED: FlowCardCustom = {
    confirm: "closed",
    message: null,
    deleteLocked: false,
  };

  function customEntry({
    id,
    state,
    custom,
    title,
  }: {
    id: string;
    state: FlowCardState;
    custom?: FlowCardCustom;
    title?: string;
  }): FlowGridEntry {
    return { id, title: title ?? `Title ${id}`, state, custom };
  }

  function render({ entries }: { entries: FlowGridEntry[] }): HTMLElement {
    const container = document.createElement("div");
    renderFlowGrid({ container, entries });
    return container;
  }

  const loading: FlowCardState = { kind: "loading" };

  it("renders a loading card with an aria-hidden skeleton and a label", () => {
    const card = render({
      entries: [customEntry({ id: "a", state: loading })],
    }).querySelector(".flow-card") as HTMLElement;
    expect(card.dataset.flowState).toBe("loading");
    expect(card.getAttribute("aria-label")).toBe("Title a: loading");
    const skeleton = card.querySelector(".flow-skeleton") as HTMLElement;
    expect(skeleton.getAttribute("aria-hidden")).toBe("true");
    expect(skeleton.children.length).toBe(3);
  });

  it("renders an error card with text and a Retry button", () => {
    const card = render({
      entries: [customEntry({ id: "a", state: { kind: "error" } })],
    }).querySelector(".flow-card") as HTMLElement;
    expect(card.querySelector(".flow-error")?.textContent).toContain(
      "Couldn't load this flow.",
    );
    const retry = card.querySelector(
      "button.flow-retry-btn[data-flow-retry]",
    ) as HTMLButtonElement;
    expect(retry.type).toBe("button");
    expect(retry.textContent).toBe("Retry");
  });

  describe("needs-attention card", () => {
    function invalidCard({
      stepIndex,
      custom,
    }: {
      stepIndex: number | null;
      custom?: FlowCardCustom;
    }): HTMLElement {
      return render({
        entries: [
          customEntry({
            id: "a",
            custom,
            state: {
              kind: "invalid",
              invalid: {
                step_index: stepIndex,
                field: "event_name",
                reason: "event is gone",
              },
            },
          }),
        ],
      }).querySelector(".flow-card") as HTMLElement;
    }

    it("names the 1-based step in the aria-label and visible text", () => {
      const card = invalidCard({ stepIndex: 2, custom: CLOSED });
      const label = card.getAttribute("aria-label") ?? "";
      expect(label).toContain("Needs attention.");
      expect(label).toContain("Step 3: event is gone");
      expect(label.startsWith("Title a (custom): ")).toBe(true);
      expect(card.querySelector(".flow-attention")?.textContent).toContain(
        "Step 3: event is gone",
      );
    });

    it("omits the step number when step_index is null", () => {
      const card = invalidCard({ stepIndex: null });
      const label = card.getAttribute("aria-label") ?? "";
      expect(label).toContain("event is gone");
      expect(label).not.toContain("Step");
      expect(label.startsWith("Title a: ")).toBe(true);
    });

    it("renders no glyph element and never renders Retry or a funnel", () => {
      const card = invalidCard({ stepIndex: 0 });
      expect(card.querySelector(".flow-attention > span")).toBeNull();
      expect(card.querySelector(".flow-retry-btn")).toBeNull();
      expect(card.querySelector(".funnel")).toBeNull();
    });

    it("custom closed renders Custom badge and Delete, still no Retry", () => {
      const card = invalidCard({ stepIndex: 0, custom: CLOSED });
      expect(card.querySelector(".flow-badge.custom")?.textContent).toBe(
        "Custom",
      );
      expect(card.querySelector(".flow-delete-btn")).not.toBeNull();
      expect(card.querySelector(".flow-retry-btn")).toBeNull();
    });

    it("custom with confirm open renders the confirm group", () => {
      const card = invalidCard({
        stepIndex: 0,
        custom: { ...CLOSED, confirm: "open" },
      });
      expect(card.querySelector(".flow-badge.custom")).not.toBeNull();
      expect(card.querySelector(".flow-confirm")).not.toBeNull();
      expect(card.querySelector(".flow-delete-btn")).toBeNull();
    });
  });

  it("built-in cards show the Built-in badge and never Delete", () => {
    for (const state of [
      loading,
      { kind: "error" },
      {
        kind: "invalid",
        invalid: { step_index: 0, field: "f", reason: "bad" },
      },
      { kind: "response", response: buildEmptyResponse() },
    ] as FlowCardState[]) {
      const card = render({
        entries: [customEntry({ id: "a", state })],
      }).querySelector(".flow-card") as HTMLElement;
      expect(card.querySelector(".flow-badge")?.textContent).toBe("Built-in");
      expect(card.querySelector(".flow-badge.custom")).toBeNull();
      expect(card.querySelector(".flow-delete-btn")).toBeNull();
      expect(card.querySelector(".flow-confirm")).toBeNull();
    }
  });

  it("custom closed renders a labelled Delete button", () => {
    const card = render({
      entries: [customEntry({ id: "a", state: loading, custom: CLOSED })],
    }).querySelector(".flow-card") as HTMLElement;
    const button = card.querySelector(
      "button.flow-delete-btn[data-flow-delete]",
    ) as HTMLButtonElement;
    expect(button.getAttribute("aria-label")).toBe("Delete flow Title a");
    expect(
      button.querySelector("svg.bi-trash")?.getAttribute("aria-hidden"),
    ).toBe("true");
    expect(button.hasAttribute("aria-disabled")).toBe(false);
    expect(card.querySelector(".flow-confirm")).toBeNull();
  });

  it("every custom state renders a labelled Edit button before Delete", () => {
    const states: FlowCardState[] = [
      loading,
      { kind: "error" },
      { kind: "response", response: buildAddUrlResponse() },
    ];
    for (const state of states) {
      const card = render({
        entries: [customEntry({ id: "a", state, custom: CLOSED })],
      }).querySelector(".flow-card") as HTMLElement;
      const edit = card.querySelector(
        "button.flow-edit-btn[data-flow-edit]",
      ) as HTMLButtonElement;
      expect(edit.getAttribute("aria-label")).toBe("Edit flow Title a");
      expect(edit.hasAttribute("aria-disabled")).toBe(false);
      expect(edit.nextElementSibling).toBe(
        card.querySelector(".flow-delete-btn"),
      );
    }
  });

  it("builtin cards and open confirms have no Edit button", () => {
    const builtin = render({
      entries: [{ id: "a", title: "Built in", state: loading }],
    });
    expect(builtin.querySelector("[data-flow-edit]")).toBeNull();
    const confirming = render({
      entries: [
        customEntry({
          id: "a",
          state: loading,
          custom: { ...CLOSED, confirm: "open" },
        }),
      ],
    });
    expect(confirming.querySelector("[data-flow-edit]")).toBeNull();
  });

  it("locked Edit is aria-disabled and points at the same reason span", () => {
    const container = render({
      entries: [
        customEntry({
          id: "a",
          state: loading,
          custom: { ...CLOSED, deleteLocked: true },
        }),
      ],
    });
    const edit = container.querySelector("[data-flow-edit]") as HTMLElement;
    const remove = container.querySelector("[data-flow-delete]") as HTMLElement;
    expect(edit.getAttribute("aria-disabled")).toBe("true");
    expect(edit.getAttribute("aria-describedby")).toBe(
      remove.getAttribute("aria-describedby"),
    );
    expect(
      container.querySelectorAll(`#${edit.getAttribute("aria-describedby")}`),
    ).toHaveLength(1);
  });

  it("custom response card gets the (custom) aria-label suffix", () => {
    const card = render({
      entries: [
        customEntry({
          id: "a",
          custom: CLOSED,
          state: { kind: "response", response: buildAddUrlResponse() },
        }),
      ],
    }).querySelector(".flow-card") as HTMLElement;
    expect(card.getAttribute("aria-label")).toMatch(/^Title a \(custom\): /);
    expect(card.querySelector(".flow-delete-btn")).not.toBeNull();
  });

  it("open confirm renders a group labelled by its prompt and no Delete", () => {
    const card = render({
      entries: [
        customEntry({
          id: "a",
          state: loading,
          custom: { ...CLOSED, confirm: "open" },
        }),
      ],
    }).querySelector(".flow-card") as HTMLElement;
    const group = card.querySelector("[data-flow-confirm]") as HTMLElement;
    expect(group.getAttribute("role")).toBe("group");
    const promptElement = card.querySelector(
      `#${group.getAttribute("aria-labelledby")}`,
    ) as HTMLElement;
    expect(promptElement.textContent).toBe(
      "Delete “Title a”? This cannot be undone.",
    );
    expect(card.querySelector(".flow-delete-btn")).toBeNull();
    const confirm = card.querySelector("[data-flow-confirm-delete]");
    expect(confirm?.textContent).toBe("Delete");
    expect(confirm?.hasAttribute("aria-disabled")).toBe(false);
    expect(card.querySelector("[data-flow-confirm-cancel]")).not.toBeNull();
  });

  it("deleting makes both confirm buttons aria-disabled, not disabled", () => {
    const card = render({
      entries: [
        customEntry({
          id: "a",
          state: loading,
          custom: { ...CLOSED, confirm: "deleting" },
        }),
      ],
    }).querySelector(".flow-card") as HTMLElement;
    const confirm = card.querySelector(
      "[data-flow-confirm-delete]",
    ) as HTMLButtonElement;
    const cancel = card.querySelector(
      "[data-flow-confirm-cancel]",
    ) as HTMLButtonElement;
    expect(confirm.textContent).toBe("Deleting…");
    for (const button of [confirm, cancel]) {
      expect(button.getAttribute("aria-disabled")).toBe("true");
      expect(button.disabled).toBe(false);
    }
  });

  it("locked Delete is aria-disabled and described by a hidden span", () => {
    const container = render({
      entries: [
        customEntry({
          id: "a",
          state: loading,
          custom: { ...CLOSED, deleteLocked: true },
        }),
      ],
    });
    const button = container.querySelector(".flow-delete-btn") as HTMLElement;
    expect(button.getAttribute("aria-disabled")).toBe("true");
    const hint = container.querySelector(
      `#${button.getAttribute("aria-describedby")}`,
    ) as HTMLElement;
    expect(hint.className).toContain("visually-hidden");
    expect(hint.textContent).toBe("Another flow is being deleted.");

    const unlocked = render({
      entries: [customEntry({ id: "a", state: loading, custom: CLOSED })],
    });
    expect(unlocked.querySelector(".visually-hidden")).toBeNull();
    expect(
      unlocked
        .querySelector(".flow-delete-btn")
        ?.hasAttribute("aria-describedby"),
    ).toBe(false);
  });

  it("renders custom.message under the header", () => {
    const card = render({
      entries: [
        customEntry({
          id: "a",
          state: loading,
          custom: {
            ...CLOSED,
            message: "Couldn't delete this flow. Try again.",
          },
        }),
      ],
    }).querySelector(".flow-card") as HTMLElement;
    expect(card.querySelector(".flow-card-message")?.textContent).toBe(
      "Couldn't delete this flow. Try again.",
    );
  });

  it("renders custom.message in every state and none when null", () => {
    const states: FlowCardState[] = [
      { kind: "error" },
      {
        kind: "invalid",
        invalid: { step_index: 0, field: "f", reason: "bad" },
      },
      { kind: "response", response: buildEmptyResponse() },
    ];
    for (const state of states) {
      const withMessage = render({
        entries: [
          customEntry({
            id: "a",
            state,
            custom: { ...CLOSED, message: "Nope." },
          }),
        ],
      });
      expect(withMessage.querySelector(".flow-card-message")?.textContent).toBe(
        "Nope.",
      );
      const without = render({
        entries: [customEntry({ id: "a", state, custom: CLOSED })],
      });
      expect(without.querySelector(".flow-card-message")).toBeNull();
    }
  });

  it("changing only custom (confirm or deleteLocked) replaces that card alone", () => {
    const container = document.createElement("div");
    const build = (
      first: FlowCardCustom,
      second: FlowCardCustom,
    ): FlowGridEntry[] => [
      customEntry({ id: "a", state: loading, custom: first }),
      customEntry({ id: "b", state: loading, custom: second }),
    ];
    renderFlowGrid({ container, entries: build(CLOSED, CLOSED) });
    const [firstNode, secondNode] = Array.from(container.children);

    renderFlowGrid({
      container,
      entries: build({ ...CLOSED, confirm: "open" }, CLOSED),
    });
    expect(container.children[0]).not.toBe(firstNode);
    expect(container.children[1]).toBe(secondNode);

    const openNode = container.children[0];
    renderFlowGrid({
      container,
      entries: build(
        { ...CLOSED, confirm: "open" },
        { ...CLOSED, deleteLocked: true },
      ),
    });
    expect(container.children[0]).toBe(openNode);
    expect(container.children[1]).not.toBe(secondNode);
  });

  it("keeps the node when custom is unchanged by value", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      entries: [
        customEntry({ id: "a", state: loading, custom: { ...CLOSED } }),
      ],
    });
    const node = container.firstElementChild;
    renderFlowGrid({
      container,
      entries: [
        customEntry({ id: "a", state: loading, custom: { ...CLOSED } }),
      ],
    });
    expect(container.firstElementChild).toBe(node);
  });

  it("changing only the title replaces that card", () => {
    const container = document.createElement("div");
    renderFlowGrid({
      container,
      entries: [customEntry({ id: "a", state: loading, title: "One" })],
    });
    const node = container.firstElementChild;
    renderFlowGrid({
      container,
      entries: [customEntry({ id: "a", state: loading, title: "Two" })],
    });
    expect(container.firstElementChild).not.toBe(node);
    expect(container.querySelector(".flow-title")?.textContent).toContain(
      "Two",
    );
  });

  it("sets a 64-char name through textContent (no HTML injection)", () => {
    const name = `<img src=x onerror=alert(1)>${"n".repeat(36)}`;
    expect(name.length).toBe(64);
    const container = render({
      entries: [
        customEntry({
          id: "a",
          title: name,
          state: loading,
          custom: { ...CLOSED, confirm: "open" },
        }),
      ],
    });
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector(".flow-title")?.textContent).toBe(
      `Custom ${name}`,
    );
    expect(
      container.querySelector(".flow-confirm-prompt")?.textContent,
    ).toContain(name);
  });

  it("gives every state's section tabindex -1", () => {
    const container = render({
      entries: [
        customEntry({ id: "a", state: loading }),
        customEntry({ id: "b", state: { kind: "error" } }),
        customEntry({
          id: "c",
          state: {
            kind: "invalid",
            invalid: { step_index: null, field: "__root__", reason: "bad" },
          },
        }),
        customEntry({
          id: "d",
          state: { kind: "response", response: buildEmptyResponse() },
        }),
      ],
    });
    const cards = container.querySelectorAll(".flow-card");
    expect(cards.length).toBe(4);
    for (const card of Array.from(cards)) {
      expect(card.getAttribute("tabindex")).toBe("-1");
    }
  });
});
