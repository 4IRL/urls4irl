/**
 * Delete with an in-place confirm on the Flows grid: open/cancel/Escape, the
 * single DELETE, every outcome (200, 404, 429, other, hidden-tab), the deleting
 * card kept across list refetches, takeover refreshes and focus restore.
 *
 * Every request stub is DEFERRED (settled by the test); `abort()` mirrors
 * jqXHR (`fail` then `always`, synchronously). The real `flow-card.js` renders.
 */

const {
  fetchSummarySpy,
  fetchTopEventsSpy,
  fetchGroupedTimeseriesSpy,
  fetchGaugesTimeseriesSpy,
  fetchFlowSpy,
  fetchMetricFlowsSpy,
  deleteMetricFlowSpy,
} = vi.hoisted(() => ({
  fetchSummarySpy: vi.fn(),
  fetchTopEventsSpy: vi.fn(),
  fetchGroupedTimeseriesSpy: vi.fn(),
  fetchGaugesTimeseriesSpy: vi.fn(),
  fetchFlowSpy: vi.fn(),
  fetchMetricFlowsSpy: vi.fn(),
  deleteMetricFlowSpy: vi.fn(),
}));

vi.mock("../metrics-query-client.js", () => ({
  fetchSummary: fetchSummarySpy,
  fetchTopEvents: fetchTopEventsSpy,
  fetchTimeseries: vi.fn(),
  fetchGroupedTimeseries: fetchGroupedTimeseriesSpy,
  fetchGaugesTimeseries: fetchGaugesTimeseriesSpy,
  fetchFlow: fetchFlowSpy,
  fetchMetricFlows: fetchMetricFlowsSpy,
  deleteMetricFlow: deleteMetricFlowSpy,
}));

vi.mock("../render-summary.js", () => ({ renderSummary: vi.fn() }));
vi.mock("../render-top-table.js", () => ({ renderTopTable: vi.fn() }));

import { FLOW_IDS, FLOW_METADATA } from "../../types/metrics-flows.js";
import {
  _resetMetricsDashboardForTests,
  initMetricsDashboard,
} from "../metrics-dashboard.js";
import { makeListEntry } from "./helpers/flow-list-mock.js";

const DASHBOARD_HTML = `
  <main id="MetricsDashboard" aria-busy="false">
    <button id="MetricsRefreshNowBtn" type="button"></button>
    <button class="MetricsWindowButton" data-window="day" aria-pressed="true"></button>
    <button class="MetricsWindowButton" data-window="week" aria-pressed="false"></button>
    <section id="MetricsSummary"><div id="MetricsSummaryGrid"></div></section>
    <section id="MetricsPanelApi">
      <table id="MetricsTopTableApi"><tbody></tbody></table>
    </section>
    <section id="MetricsPanelUi">
      <table id="MetricsTopTableUi"><tbody></tbody></table>
    </section>
    <section id="MetricsPanelDomain">
      <table id="MetricsTopTableDomain"><tbody></tbody></table>
    </section>
    <div id="MetricsTablist" role="tablist">
      <button id="MetricsTabApi"   role="tab" aria-selected="true"  aria-controls="MetricsPanelApi"   tabindex="0"  data-tab="api"></button>
      <button id="MetricsTabFlows" role="tab" aria-selected="false" aria-controls="MetricsPanelFlows" tabindex="-1" data-tab="flows"></button>
    </div>
    <section id="MetricsPanelFlows" role="tabpanel" tabindex="0" hidden>
      <span class="flows-loading-spinner" aria-hidden="true"></span>
      <span id="MetricsPanelFlowsAnnouncement" class="visually-hidden" aria-live="polite"></span>
      <span id="MetricsFlowsActionAnnouncement" class="visually-hidden" aria-live="polite"></span>
      <div class="flows-toolbar">
        <h2 id="MetricsFlowsHeading" class="flows-heading" tabindex="-1">Flow funnels</h2>
        <span id="MetricsFlowsCount" class="flows-count"></span>
        <span id="MetricsFlowsHint" class="flows-hint" hidden></span>
        <span id="MetricsFlowsNotice" class="flows-notice" hidden></span>
      </div>
      <div id="MetricsFlowGrid" class="flow-grid"></div>
    </section>
    <div id="MetricsErrorBanner" class="hidden"></div>
  </main>
`;

const POLL_INTERVAL_MS = 60_000;
const BUILTIN_IDS: string[] = Object.values(FLOW_IDS);
const CUSTOM_ONE = "custom_1";
const CUSTOM_TWO = "custom_2";

interface Deferred {
  key: string;
  xhr: JQuery.jqXHR;
  abort: ReturnType<typeof vi.fn>;
  isSettled: () => boolean;
  resolve: (response?: unknown) => void;
  reject: (options?: {
    status?: number;
    readyState?: number;
    statusText?: string;
  }) => void;
}

function okFlowResponse() {
  const step = {
    stream: "ui",
    label: "Open form",
    event_name: "ui_url_create_open",
    count: 10,
    pct_of_top: 1,
    breakdown: null,
  };
  return {
    steps: [step, { ...step, label: "Done", count: 5, pct_of_top: 0.5 }],
  };
}

// `settleOnAbort: false` models a request whose `abort()` does not settle it,
// so a later settle reaches the handlers and only identity guards stop it.
function makeDeferred({
  key,
  settleOnAbort = true,
}: {
  key: string;
  settleOnAbort?: boolean;
}): Deferred {
  const doneCallbacks: Array<(response: unknown) => void> = [];
  const failCallbacks: Array<(xhr: unknown) => void> = [];
  const alwaysCallbacks: Array<() => void> = [];
  let settled = false;
  const fake = {
    status: 0,
    readyState: 1,
    statusText: "",
    responseJSON: undefined as unknown,
    _429Handled: false,
    done: (callback: (response: unknown) => void) => {
      doneCallbacks.push(callback);
      return fake;
    },
    fail: (callback: (xhr: unknown) => void) => {
      failCallbacks.push(callback);
      return fake;
    },
    always: (callback: () => void) => {
      alwaysCallbacks.push(callback);
      return fake;
    },
    abort: vi.fn(() => {
      // A real jqXHR ignores abort() once it has settled.
      if (settled || !settleOnAbort) return;
      settled = true;
      fake.status = 0;
      fake.readyState = 0;
      fake.statusText = "abort";
      failCallbacks.forEach((callback) => callback(fake));
      alwaysCallbacks.forEach((callback) => callback());
    }),
  };
  return {
    key,
    xhr: fake as unknown as JQuery.jqXHR,
    abort: fake.abort,
    isSettled: () => settled,
    resolve: (response = okFlowResponse()) => {
      if (settled) return;
      settled = true;
      fake.status = 200;
      fake.readyState = 4;
      doneCallbacks.forEach((callback) => callback(response));
      alwaysCallbacks.forEach((callback) => callback());
    },
    reject: ({ status = 500, readyState = 4, statusText = "error" } = {}) => {
      if (settled) return;
      settled = true;
      fake.status = status;
      fake.readyState = readyState;
      fake.statusText = statusText;
      failCallbacks.forEach((callback) => callback(fake));
      alwaysCallbacks.forEach((callback) => callback());
    },
  };
}

function flowResponseWithCount({ count }: { count: number }) {
  const response = okFlowResponse();
  return {
    steps: response.steps.map((step) => ({ ...step, count })),
  };
}

function makeSettlingXhr(): JQuery.jqXHR {
  const chainable = {
    done: vi.fn().mockReturnThis(),
    fail: vi.fn().mockReturnThis(),
    always: vi.fn().mockImplementation((callback: () => void) => {
      callback();
      return chainable;
    }),
    abort: () => {},
  };
  return chainable as unknown as JQuery.jqXHR;
}

function listResponse({ customs = [] }: { customs?: string[] } = {}) {
  return {
    flows: [
      ...BUILTIN_IDS.map((id) =>
        makeListEntry({
          id,
          display_name:
            FLOW_METADATA[id as keyof typeof FLOW_METADATA].displayName,
        }),
      ),
      ...customs.map((id) =>
        makeListEntry({
          id,
          display_name: `Name of ${id}`,
          is_builtin: false,
        }),
      ),
    ],
  };
}

describe("metrics-dashboard flows grid: delete with in-place confirm", () => {
  let flowDeferreds: Deferred[] = [];
  let listDeferreds: Deferred[] = [];
  let deleteDeferreds: Deferred[] = [];

  beforeEach(() => {
    document.body.innerHTML = DASHBOARD_HTML;
    flowDeferreds = [];
    listDeferreds = [];
    deleteDeferreds = [];
    for (const spy of [
      fetchSummarySpy,
      fetchTopEventsSpy,
      fetchGroupedTimeseriesSpy,
      fetchGaugesTimeseriesSpy,
    ]) {
      spy.mockReset();
      spy.mockImplementation(() => makeSettlingXhr());
    }
    fetchFlowSpy.mockReset();
    fetchFlowSpy.mockImplementation(({ flowId }: { flowId: string }) => {
      const deferred = makeDeferred({ key: flowId });
      flowDeferreds.push(deferred);
      return deferred.xhr;
    });
    fetchMetricFlowsSpy.mockReset();
    fetchMetricFlowsSpy.mockImplementation(() => {
      const deferred = makeDeferred({ key: "list" });
      listDeferreds.push(deferred);
      return deferred.xhr;
    });
    deleteMetricFlowSpy.mockReset();
    deleteMetricFlowSpy.mockImplementation(({ flowId }: { flowId: string }) => {
      const deferred = makeDeferred({ key: flowId });
      deleteDeferreds.push(deferred);
      return deferred.xhr;
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    _resetMetricsDashboardForTests();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  function grid(): HTMLElement {
    return document.getElementById("MetricsFlowGrid") as HTMLElement;
  }
  function heading(): HTMLElement {
    return document.getElementById("MetricsFlowsHeading") as HTMLElement;
  }
  function countText(): string {
    return (document.getElementById("MetricsFlowsCount") as HTMLElement)
      .textContent as string;
  }
  function notice(): HTMLElement {
    return document.getElementById("MetricsFlowsNotice") as HTMLElement;
  }
  function actionAnnouncement(): string {
    return document.getElementById("MetricsFlowsActionAnnouncement")
      ?.textContent as string;
  }
  // The panel carries `aria-busy="true"` only while busy (absent otherwise).
  function panelBusy(): string {
    return document
      .getElementById("MetricsPanelFlows")
      ?.getAttribute("aria-busy") === "true"
      ? "true"
      : "false";
  }
  function cards(): HTMLElement[] {
    return Array.from(grid().querySelectorAll<HTMLElement>(".flow-card"));
  }
  function card({ id }: { id: string }): HTMLElement | undefined {
    return cards().find((node) => node.dataset.flowId === id);
  }
  function control({
    id,
    attribute,
  }: {
    id: string;
    attribute: string;
  }): HTMLElement {
    return card({ id })?.querySelector(`[${attribute}]`) as HTMLElement;
  }
  function deleteButton({ id }: { id: string }): HTMLElement {
    return control({ id, attribute: "data-flow-delete" });
  }
  function cancelButton({ id }: { id: string }): HTMLElement {
    return control({ id, attribute: "data-flow-confirm-cancel" });
  }
  function confirmButton({ id }: { id: string }): HTMLElement {
    return control({ id, attribute: "data-flow-confirm-delete" });
  }
  function latestList(): Deferred {
    return listDeferreds[listDeferreds.length - 1];
  }
  function latestDelete(): Deferred {
    return deleteDeferreds[deleteDeferreds.length - 1];
  }
  function clickTab({ id }: { id: string }): void {
    (document.getElementById(id) as HTMLButtonElement).click();
  }
  function settleAllFlows(): void {
    for (let index = 0; index < flowDeferreds.length; index++) {
      if (!flowDeferreds[index].isSettled()) flowDeferreds[index].resolve();
    }
  }
  function openFlowsWithList({
    customs = [CUSTOM_ONE, CUSTOM_TWO],
    settle = true,
  }: { customs?: string[]; settle?: boolean } = {}): void {
    initMetricsDashboard();
    clickTab({ id: "MetricsTabFlows" });
    latestList().resolve(listResponse({ customs }));
    if (settle) {
      settleAllFlows();
    }
  }
  function startDelete({ id }: { id: string }): void {
    deleteButton({ id }).click();
    confirmButton({ id }).click();
  }
  function pressEscape({ target }: { target: HTMLElement }): void {
    target.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Escape", bubbles: true }),
    );
  }
  function tick(): void {
    vi.advanceTimersByTime(1);
  }
  function loadedRegion(): HTMLElement {
    return document.getElementById(
      "MetricsPanelFlowsAnnouncement",
    ) as HTMLElement;
  }
  // The load announcement may hold text from the initial load: clear it
  // before the action under test.
  function clearLoadedRegion(): void {
    loadedRegion().textContent = "";
  }
  function focusOutside(): HTMLElement {
    const outside = document.createElement("button");
    document.body.appendChild(outside);
    outside.focus();
    return outside;
  }
  function blurToBody(): void {
    (document.activeElement as HTMLElement).blur();
  }
  function listRetryButton(): HTMLElement {
    return grid().querySelector("[data-flow-list-retry]") as HTMLElement;
  }
  // Resolve every outstanding /flow request (the queue admits more as these
  // settle) with a response whose count marks the window it was fetched for.
  function settleAllFlowsWithCount({ count }: { count: number }): void {
    for (let index = 0; index < flowDeferreds.length; index++) {
      if (!flowDeferreds[index].isSettled()) {
        flowDeferreds[index].resolve(flowResponseWithCount({ count }));
      }
    }
  }
  // Poll tick: with Flows active this starts a `load` list request.
  function startLoadInFlight(): Deferred {
    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    return latestList();
  }

  it("Delete opens the confirm with focus on Cancel", () => {
    openFlowsWithList();
    deleteButton({ id: CUSTOM_ONE }).click();
    expect(confirmButton({ id: CUSTOM_ONE })).toBeTruthy();
    expect(document.activeElement).toBe(cancelButton({ id: CUSTOM_ONE }));
  });

  it("opening a second confirm closes the first", () => {
    openFlowsWithList();
    deleteButton({ id: CUSTOM_ONE }).click();
    deleteButton({ id: CUSTOM_TWO }).click();
    expect(grid().querySelectorAll("[data-flow-confirm]")).toHaveLength(1);
    expect(
      card({ id: CUSTOM_TWO })?.querySelector("[data-flow-confirm]"),
    ).not.toBeNull();
  });

  it("Cancel and Escape close the confirm and refocus Delete; Escape does not bubble", () => {
    openFlowsWithList();
    deleteButton({ id: CUSTOM_ONE }).click();
    cancelButton({ id: CUSTOM_ONE }).click();
    expect(document.activeElement).toBe(deleteButton({ id: CUSTOM_ONE }));
    expect(deleteMetricFlowSpy).not.toHaveBeenCalled();

    deleteButton({ id: CUSTOM_ONE }).click();
    const bubbled = vi.fn();
    document.addEventListener("keydown", bubbled);
    pressEscape({ target: cancelButton({ id: CUSTOM_ONE }) });
    document.removeEventListener("keydown", bubbled);
    expect(grid().querySelector("[data-flow-confirm]")).toBeNull();
    expect(document.activeElement).toBe(deleteButton({ id: CUSTOM_ONE }));
    expect(bubbled).not.toHaveBeenCalled();
  });

  it("Escape outside an open confirm is ignored", () => {
    openFlowsWithList();
    const bubbled = vi.fn();
    document.addEventListener("keydown", bubbled);
    pressEscape({ target: deleteButton({ id: CUSTOM_ONE }) });
    document.removeEventListener("keydown", bubbled);
    expect(bubbled).toHaveBeenCalledTimes(1);
  });

  it("Confirm sends one DELETE; while deleting both buttons are aria-disabled and a second click sends nothing", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    expect(deleteMetricFlowSpy).toHaveBeenCalledTimes(1);
    expect(deleteMetricFlowSpy).toHaveBeenCalledWith({ flowId: CUSTOM_ONE });
    expect(
      confirmButton({ id: CUSTOM_ONE }).getAttribute("aria-disabled"),
    ).toBe("true");
    expect(cancelButton({ id: CUSTOM_ONE }).getAttribute("aria-disabled")).toBe(
      "true",
    );

    const listRequests = fetchMetricFlowsSpy.mock.calls.length;
    confirmButton({ id: CUSTOM_ONE }).click();
    cancelButton({ id: CUSTOM_ONE }).click();
    expect(deleteMetricFlowSpy).toHaveBeenCalledTimes(1);
    expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(listRequests);
    expect(confirmButton({ id: CUSTOM_ONE })).toBeTruthy();
    expect(
      confirmButton({ id: CUSTOM_ONE }).getAttribute("aria-disabled"),
    ).toBe("true");
    expect(cancelButton({ id: CUSTOM_ONE }).getAttribute("aria-disabled")).toBe(
      "true",
    );
  });

  it("Escape while deleting is ignored: the confirm stays and the key still bubbles", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    const bubbled = vi.fn();
    document.addEventListener("keydown", bubbled);
    pressEscape({ target: cancelButton({ id: CUSTOM_ONE }) });
    document.removeEventListener("keydown", bubbled);
    expect(confirmButton({ id: CUSTOM_ONE })).toBeTruthy();
    expect(
      confirmButton({ id: CUSTOM_ONE }).getAttribute("aria-disabled"),
    ).toBe("true");
    expect(bubbled).toHaveBeenCalledTimes(1);
    expect(deleteMetricFlowSpy).toHaveBeenCalledTimes(1);
  });

  it("while one card is deleting, sibling Delete buttons are locked and a late settle leaves the sibling alone", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    const sibling = deleteButton({ id: CUSTOM_TWO });
    expect(sibling.getAttribute("aria-disabled")).toBe("true");
    sibling.click();
    expect(deleteMetricFlowSpy).toHaveBeenCalledTimes(1);
    expect(grid().querySelectorAll("[data-flow-confirm]")).toHaveLength(1);
    expect(
      card({ id: CUSTOM_ONE })?.querySelector("[data-flow-confirm]"),
    ).not.toBeNull();
    expect(
      confirmButton({ id: CUSTOM_ONE }).getAttribute("aria-disabled"),
    ).toBe("true");
    expect(cancelButton({ id: CUSTOM_ONE }).getAttribute("aria-disabled")).toBe(
      "true",
    );

    latestDelete().resolve({});
    expect(card({ id: CUSTOM_ONE })).toBeUndefined();
    expect(card({ id: CUSTOM_TWO })).toBeDefined();
    expect(deleteButton({ id: CUSTOM_TWO }).getAttribute("aria-disabled")).toBe(
      null,
    );
  });

  it("200: card removed, count drops, focus on the heading, announced once, list refetched", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    const listRequests = fetchMetricFlowsSpy.mock.calls.length;
    latestDelete().resolve({});
    tick();

    expect(card({ id: CUSTOM_ONE })).toBeUndefined();
    expect(countText()).toBe("4 built-in · 1 custom (of 20)");
    expect(document.activeElement).toBe(heading());
    expect(actionAnnouncement()).toBe("Flow “Name of custom_1” deleted.");
    expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(listRequests + 1);
  });

  it("200 does not move focus that is elsewhere", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    const outside = focusOutside();
    latestDelete().resolve({});
    expect(document.activeElement).toBe(outside);
    expect(card({ id: CUSTOM_ONE })).toBeUndefined();
  });

  it.each([200, 404])(
    "%i moves focus to the heading when focus is on body",
    (status) => {
      openFlowsWithList();
      startDelete({ id: CUSTOM_ONE });
      blurToBody();
      expect(document.activeElement).toBe(document.body);
      if (status === 200) {
        latestDelete().resolve({});
      } else {
        latestDelete().reject({ status });
      }
      expect(document.activeElement).toBe(heading());
    },
  );

  it("404 and 429 leave focus alone when it is elsewhere", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    const outside = focusOutside();
    latestDelete().reject({ status: 404 });
    tick();
    expect(document.activeElement).toBe(outside);
    expect(notice().hidden).toBe(false);
    expect(actionAnnouncement()).toBe(notice().textContent);

    startDelete({ id: CUSTOM_TWO });
    outside.focus();
    latestDelete().reject({ status: 429 });
    tick();
    expect(document.activeElement).toBe(outside);
    expect(card({ id: CUSTOM_TWO })?.textContent).toContain(
      "Too many requests",
    );
    expect(actionAnnouncement()).toContain("Too many requests");
  });

  it("a failure moves focus to the card's Delete when focus is on body", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    blurToBody();
    latestDelete().reject({ status: 500 });
    expect(document.activeElement).toBe(deleteButton({ id: CUSTOM_ONE }));
  });

  it("200 aborts the card's in-flight /flow request and a late response cannot resurrect it", () => {
    fetchFlowSpy.mockReset();
    const customOneFlow = makeDeferred({
      key: CUSTOM_ONE,
      settleOnAbort: false,
    });
    fetchFlowSpy.mockImplementation(({ flowId }: { flowId: string }) => {
      if (flowId === CUSTOM_ONE) {
        flowDeferreds.push(customOneFlow);
        return customOneFlow.xhr;
      }
      const deferred = makeDeferred({ key: flowId });
      flowDeferreds.push(deferred);
      return deferred.xhr;
    });
    openFlowsWithList({ settle: false });
    // Settle the four built-ins so the queue puts both customs in flight.
    for (const id of BUILTIN_IDS) {
      flowDeferreds.find((entry) => entry.key === id)?.resolve();
    }
    expect(customOneFlow.abort).not.toHaveBeenCalled();
    expect(
      fetchFlowSpy.mock.calls.some(
        (call) => (call[0] as { flowId: string }).flowId === CUSTOM_ONE,
      ),
    ).toBe(true);

    startDelete({ id: CUSTOM_ONE });
    latestDelete().resolve({});
    expect(customOneFlow.abort).toHaveBeenCalled();
    expect(card({ id: CUSTOM_ONE })).toBeUndefined();

    customOneFlow.resolve();
    latestList().resolve(listResponse({ customs: [CUSTOM_TWO] }));
    settleAllFlows();
    expect(card({ id: CUSTOM_ONE })).toBeUndefined();
    expect(card({ id: CUSTOM_TWO })).toBeDefined();
  });

  it("404: card removed, already-deleted notice and announcement, focus on the heading", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    latestDelete().reject({ status: 404 });
    tick();

    expect(card({ id: CUSTOM_ONE })).toBeUndefined();
    expect(notice().hidden).toBe(false);
    expect(notice().textContent).toContain("Name of custom_1");
    expect(actionAnnouncement()).toBe(notice().textContent);
    expect(document.activeElement).toBe(heading());
  });

  it("429: card stays with the rate-limit message, focus returns to Delete, announced", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    latestDelete().reject({ status: 429 });
    tick();

    expect(card({ id: CUSTOM_ONE })?.textContent).toContain(
      "Too many requests",
    );
    expect(document.activeElement).toBe(deleteButton({ id: CUSTOM_ONE }));
    expect(actionAnnouncement()).toContain("Too many requests");
    expect(deleteButton({ id: CUSTOM_TWO }).getAttribute("aria-disabled")).toBe(
      null,
    );
  });

  it("500 and timeout: card stays with the generic failure message", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    latestDelete().reject({ status: 500 });
    tick();
    expect(card({ id: CUSTOM_ONE })?.textContent).toContain(
      "Couldn't delete this flow",
    );
    expect(actionAnnouncement()).toContain("Couldn't delete this flow");

    startDelete({ id: CUSTOM_ONE });
    latestDelete().reject({
      status: 0,
      readyState: 0,
      statusText: "timeout",
    });
    tick();
    expect(card({ id: CUSTOM_ONE })?.textContent).toContain(
      "Couldn't delete this flow",
    );
    expect(actionAnnouncement()).toContain("Couldn't delete this flow");

    startDelete({ id: CUSTOM_ONE });
    latestDelete().reject({ status: 400 });
    tick();
    expect(card({ id: CUSTOM_ONE })?.textContent).toContain(
      "Couldn't delete this flow",
    );
    expect(actionAnnouncement()).toContain("Couldn't delete this flow");
  });

  it("failure leaves focus alone when it is elsewhere, and the message clears at the next confirm open", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    const outside = focusOutside();
    latestDelete().reject({ status: 500 });
    expect(document.activeElement).toBe(outside);

    deleteButton({ id: CUSTOM_ONE }).click();
    expect(card({ id: CUSTOM_ONE })?.textContent).not.toContain(
      "Couldn't delete this flow",
    );
  });

  it("a 404 notice is cleared when the next confirm opens", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    latestDelete().reject({ status: 404 });
    expect(notice().hidden).toBe(false);

    deleteButton({ id: CUSTOM_TWO }).click();
    expect(notice().hidden).toBe(true);
    expect(notice().textContent).toBe("");
  });

  it("a card message is dropped once its card leaves the list, not revived when it returns", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    latestDelete().reject({ status: 500 });
    expect(card({ id: CUSTOM_ONE })?.textContent).toContain(
      "Couldn't delete this flow",
    );

    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    latestList().resolve(listResponse({ customs: [CUSTOM_TWO] }));
    settleAllFlows();
    expect(card({ id: CUSTOM_ONE })).toBeUndefined();

    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    latestList().resolve(listResponse({ customs: [CUSTOM_ONE, CUSTOM_TWO] }));
    settleAllFlows();
    expect(card({ id: CUSTOM_ONE })).toBeDefined();
    expect(card({ id: CUSTOM_ONE })?.textContent).not.toContain(
      "Couldn't delete this flow",
    );
  });

  it("a failure whose card is gone from a refetched list falls back to the heading", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    latestList().resolve(listResponse({ customs: [CUSTOM_TWO] }));
    expect(card({ id: CUSTOM_ONE })).toBeDefined();

    latestDelete().reject({ status: 500 });
    expect(card({ id: CUSTOM_ONE })).toBeUndefined();
    expect(document.activeElement).toBe(heading());
  });

  it("a deleting card absent from a refetched list stays until the DELETE settles: one announcement, no notice", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    latestList().resolve(listResponse({ customs: [CUSTOM_TWO] }));
    settleAllFlows();

    expect(card({ id: CUSTOM_ONE })).toBeDefined();
    expect(countText()).toBe("4 built-in · 1 custom (of 20)");
    expect(notice().hidden).toBe(true);

    latestDelete().resolve({});
    tick();
    expect(card({ id: CUSTOM_ONE })).toBeUndefined();
    expect(notice().hidden).toBe(true);
    expect(actionAnnouncement()).toBe("Flow “Name of custom_1” deleted.");
  });

  it("an open confirm survives the poll and a sibling settle, and a list failure after a good load", () => {
    openFlowsWithList({ settle: false });
    deleteButton({ id: CUSTOM_ONE }).click();
    flowDeferreds[0].resolve();
    expect(document.activeElement).toBe(cancelButton({ id: CUSTOM_ONE }));

    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    latestList().reject({ status: 500 });
    expect(card({ id: CUSTOM_ONE })).toBeDefined();
    expect(
      card({ id: CUSTOM_ONE })?.querySelector("[data-flow-confirm]"),
    ).not.toBeNull();
    expect(document.activeElement).toBe(cancelButton({ id: CUSTOM_ONE }));
  });

  it("an open confirm whose flow a refetched list lacks becomes the already-deleted notice with focus on the heading", () => {
    openFlowsWithList();
    deleteButton({ id: CUSTOM_ONE }).click();
    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    latestList().resolve(listResponse({ customs: [CUSTOM_TWO] }));
    tick();

    expect(card({ id: CUSTOM_ONE })).toBeUndefined();
    expect(notice().hidden).toBe(false);
    expect(notice().textContent).toContain("Name of custom_1");
    expect(actionAnnouncement()).toBe(notice().textContent);
    expect(document.activeElement).toBe(heading());
  });

  it("an open confirm whose flow a refetched list lacks leaves focus alone when it is elsewhere", () => {
    openFlowsWithList();
    deleteButton({ id: CUSTOM_ONE }).click();
    const outside = focusOutside();
    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    latestList().resolve(listResponse({ customs: [CUSTOM_TWO] }));
    tick();

    expect(card({ id: CUSTOM_ONE })).toBeUndefined();
    expect(notice().hidden).toBe(false);
    expect(actionAnnouncement()).toBe(notice().textContent);
    expect(document.activeElement).toBe(outside);
  });

  it("leaving Flows clears an open confirm; returning shows the card closed", () => {
    openFlowsWithList();
    deleteButton({ id: CUSTOM_ONE }).click();
    clickTab({ id: "MetricsTabApi" });
    clickTab({ id: "MetricsTabFlows" });
    expect(grid().querySelector("[data-flow-confirm]")).toBeNull();
    expect(deleteButton({ id: CUSTOM_ONE })).toBeTruthy();
  });

  it("leaving Flows clears the card messages and the notice that exist at that moment", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    latestDelete().reject({ status: 500 });
    startDelete({ id: CUSTOM_TWO });
    latestDelete().reject({ status: 404 });
    expect(card({ id: CUSTOM_ONE })?.textContent).toContain(
      "Couldn't delete this flow",
    );
    expect(notice().hidden).toBe(false);

    clickTab({ id: "MetricsTabApi" });
    expect(notice().hidden).toBe(true);
    clickTab({ id: "MetricsTabFlows" });
    expect(card({ id: CUSTOM_ONE })?.textContent).not.toContain(
      "Couldn't delete this flow",
    );
    expect(notice().hidden).toBe(true);
  });

  it("a deleting card is still deleting when Flows is re-entered before its DELETE settles", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    clickTab({ id: "MetricsTabApi" });
    clickTab({ id: "MetricsTabFlows" });
    expect(deleteMetricFlowSpy).toHaveBeenCalledTimes(1);
    expect(
      confirmButton({ id: CUSTOM_ONE }).getAttribute("aria-disabled"),
    ).toBe("true");
    expect(cancelButton({ id: CUSTOM_ONE }).getAttribute("aria-disabled")).toBe(
      "true",
    );
    expect(deleteButton({ id: CUSTOM_TWO }).getAttribute("aria-disabled")).toBe(
      "true",
    );

    latestDelete().resolve({});
    expect(card({ id: CUSTOM_ONE })).toBeUndefined();
  });

  it("a DELETE outcome that lands while Flows is hidden removes the card with no list request, focus move, notice or announcement", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    clickTab({ id: "MetricsTabApi" });
    expect(
      card({ id: CUSTOM_ONE })?.querySelector("[data-flow-confirm]"),
    ).not.toBeNull();
    const listRequests = fetchMetricFlowsSpy.mock.calls.length;
    const focusBefore = document.activeElement;

    latestDelete().resolve({});
    tick();
    expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(listRequests);
    expect(card({ id: CUSTOM_ONE })).toBeUndefined();
    expect(document.activeElement).toBe(focusBefore);
    expect(notice().hidden).toBe(true);
    expect(actionAnnouncement()).toBe("");
    expect(panelBusy()).toBe("false");

    clickTab({ id: "MetricsTabFlows" });
    expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(listRequests + 1);
  });

  it("a hidden-tab DELETE failure moves no focus and makes no announcement, and leaves no stale message on return", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    clickTab({ id: "MetricsTabApi" });
    const focusBefore = document.activeElement;
    const listRequests = fetchMetricFlowsSpy.mock.calls.length;
    latestDelete().reject({ status: 500 });
    tick();

    expect(document.activeElement).toBe(focusBefore);
    expect(actionAnnouncement()).toBe("");
    expect(notice().hidden).toBe(true);
    expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(listRequests);
    clickTab({ id: "MetricsTabFlows" });
    expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(listRequests);
    expect(card({ id: CUSTOM_ONE })?.textContent).not.toContain(
      "Couldn't delete this flow",
    );
    expect(deleteButton({ id: CUSTOM_ONE })).toBeTruthy();

    deleteButton({ id: CUSTOM_ONE }).click();
    expect(card({ id: CUSTOM_ONE })?.textContent).not.toContain(
      "Couldn't delete this flow",
    );
  });

  it.each(["resolve", "reject"] as const)(
    "a DELETE that %ss after the test reset is ignored by the identity guard",
    (outcome) => {
      // abort() does not settle this request, so only the guard can stop it.
      const stale = makeDeferred({ key: CUSTOM_ONE, settleOnAbort: false });
      deleteMetricFlowSpy.mockImplementation(() => stale.xhr);
      openFlowsWithList();
      startDelete({ id: CUSTOM_ONE });
      _resetMetricsDashboardForTests();
      expect(stale.abort).toHaveBeenCalled();
      expect(stale.isSettled()).toBe(false);
      document.body.innerHTML = DASHBOARD_HTML;
      const listRequests = fetchMetricFlowsSpy.mock.calls.length;

      expect(() => {
        if (outcome === "resolve") {
          stale.resolve({});
        } else {
          stale.reject({ status: 500 });
        }
      }).not.toThrow();
      tick();
      expect(stale.isSettled()).toBe(true);
      expect(actionAnnouncement()).toBe("");
      expect(notice().hidden).toBe(true);
      expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(listRequests);
      expect(cards()).toHaveLength(0);
    },
  );

  it("a list in flight when a delete succeeds is aborted; the card never comes back and busy ends false", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    const staleList = latestList();
    expect(panelBusy()).toBe("true");
    (
      document.getElementById("MetricsPanelFlowsAnnouncement") as HTMLElement
    ).textContent = "";

    latestDelete().resolve({});
    expect(staleList.abort).toHaveBeenCalled();
    expect(
      document.getElementById("MetricsPanelFlowsAnnouncement")?.textContent,
    ).toBe("");
    expect(panelBusy()).toBe("true");
    expect(card({ id: CUSTOM_ONE })).toBeUndefined();

    latestList().resolve(listResponse({ customs: [CUSTOM_TWO] }));
    settleAllFlows();
    expect(card({ id: CUSTOM_ONE })).toBeUndefined();
    expect(panelBusy()).toBe("false");
    expect(
      document.getElementById("MetricsPanelFlowsAnnouncement")?.textContent,
    ).toBe("Flow funnels updated.");
  });

  it("a takeover refresh re-requests every listed id and ends with busy cleared and one announcement", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    startLoadInFlight();
    clearLoadedRegion();
    latestDelete().resolve({});
    const before = flowDeferreds.length;
    latestList().resolve(listResponse({ customs: [CUSTOM_TWO] }));
    // The queue admits at most 4 at once: the four built-ins restart first.
    const firstBatch = flowDeferreds.slice(before).map((entry) => entry.key);
    expect(firstBatch).toEqual(BUILTIN_IDS);
    expect(panelBusy()).toBe("true");
    expect(loadedRegion().textContent).toBe("");

    settleAllFlows();
    const requested = flowDeferreds.slice(before).map((entry) => entry.key);
    expect(requested).toEqual([...BUILTIN_IDS, CUSTOM_TWO]);
    expect(panelBusy()).toBe("false");
    expect(loadedRegion().textContent).toBe("Flow funnels updated.");
    tick();
    expect(actionAnnouncement()).toBe("Flow “Name of custom_1” deleted.");
  });

  it("a takeover refresh failure applies the load-failure handling", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    startLoadInFlight();
    clearLoadedRegion();
    latestDelete().resolve({});
    const before = flowDeferreds.length;
    latestList().reject({ status: 500 });

    expect(grid().querySelector(".flows-list-error")).not.toBeNull();
    expect(
      document
        .getElementById("MetricsErrorBanner")
        ?.classList.contains("hidden"),
    ).toBe(false);
    expect(listRetryButton()).toBeTruthy();
    expect(listRetryButton().getAttribute("aria-disabled")).toBe(null);
    // Fan-out over the stale list's ids (custom_1 already removed).
    expect(flowDeferreds.slice(before).map((entry) => entry.key)).toEqual(
      BUILTIN_IDS,
    );
    settleAllFlows();
    expect(card({ id: CUSTOM_TWO })).toBeDefined();
    expect(panelBusy()).toBe("false");

    const listRequests = fetchMetricFlowsSpy.mock.calls.length;
    listRetryButton().click();
    expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(listRequests + 1);
    expect(panelBusy()).toBe("true");
    latestList().resolve(listResponse({ customs: [CUSTOM_TWO] }));
    settleAllFlows();
    expect(panelBusy()).toBe("false");
    expect(grid().querySelector(".flows-list-error")).toBeNull();
  });

  it("a delete while a load is in flight is a takeover: busy stays on, then clears with a single announcement", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    const load = startLoadInFlight();
    clearLoadedRegion();
    expect(panelBusy()).toBe("true");

    latestDelete().resolve({});
    expect(load.abort).toHaveBeenCalled();
    expect(panelBusy()).toBe("true");
    expect(loadedRegion().textContent).toBe("");
    const refresh = latestList();
    expect(refresh).not.toBe(load);

    refresh.resolve(listResponse({ customs: [CUSTOM_TWO] }));
    expect(panelBusy()).toBe("true");
    settleAllFlows();
    expect(panelBusy()).toBe("false");
    expect(loadedRegion().textContent).toBe("Flow funnels updated.");
    tick();
    expect(actionAnnouncement()).toBe("Flow “Name of custom_1” deleted.");
    expect(card({ id: CUSTOM_ONE })).toBeUndefined();
  });

  it("two deletes back to back during a load: the second refresh inherits busy, one announcement at the end", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    startLoadInFlight();
    clearLoadedRegion();
    latestDelete().resolve({});
    const firstRefresh = latestList();
    expect(panelBusy()).toBe("true");

    startDelete({ id: CUSTOM_TWO });
    latestDelete().resolve({});
    tick();
    expect(firstRefresh.abort).toHaveBeenCalled();
    const secondRefresh = latestList();
    expect(secondRefresh).not.toBe(firstRefresh);
    expect(panelBusy()).toBe("true");
    expect(loadedRegion().textContent).toBe("");
    expect(actionAnnouncement()).toBe("Flow “Name of custom_2” deleted.");

    secondRefresh.resolve(listResponse({ customs: [] }));
    expect(panelBusy()).toBe("true");
    settleAllFlows();
    expect(panelBusy()).toBe("false");
    expect(loadedRegion().textContent).toBe("Flow funnels updated.");
    expect(cards().map((node) => node.dataset.flowId)).toEqual(BUILTIN_IDS);
  });

  it("a takeover that refetches an empty list announces exactly once and clears busy", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    startLoadInFlight();
    clearLoadedRegion();
    latestDelete().resolve({});

    latestList().resolve({ flows: [] });
    expect(panelBusy()).toBe("false");
    expect(loadedRegion().textContent).toBe("Flow funnels updated.");
    expect(cards()).toHaveLength(0);
    // Nothing further settles, so the text cannot be re-announced.
    clearLoadedRegion();
    settleAllFlows();
    tick();
    expect(loadedRegion().textContent).toBe("");
    expect(panelBusy()).toBe("false");
  });

  it("a window change, then a delete during the new load: the takeover re-requests every id for the new window", () => {
    openFlowsWithList();
    (document.querySelector('[data-window="week"]') as HTMLElement).click();
    const load = latestList();
    expect(load.isSettled()).toBe(false);
    // Old-window data is still cached and rendered.
    expect(card({ id: CUSTOM_TWO })?.textContent).toContain("5 / 10 succeeded");

    startDelete({ id: CUSTOM_ONE });
    latestDelete().resolve({});
    expect(load.abort).toHaveBeenCalled();
    const before = fetchFlowSpy.mock.calls.length;
    latestList().resolve(listResponse({ customs: [CUSTOM_TWO] }));
    settleAllFlowsWithCount({ count: 77 });

    const calls = fetchFlowSpy.mock.calls.slice(before).map((call) => {
      const args = call[0] as { flowId: string; window: string };
      return `${args.flowId}:${args.window}`;
    });
    expect([...calls].sort()).toEqual(
      [...BUILTIN_IDS, CUSTOM_TWO].map((id) => `${id}:week`).sort(),
    );
    expect(card({ id: CUSTOM_TWO })?.textContent).toContain(
      "77 / 77 succeeded",
    );
    expect(panelBusy()).toBe("false");
  });

  it("a /flow 404 refresh that supersedes the delete's refresh aborts it and settles plainly", () => {
    openFlowsWithList({ settle: false });
    for (const id of BUILTIN_IDS) {
      flowDeferreds.find((entry) => entry.key === id)?.resolve();
    }
    startDelete({ id: CUSTOM_ONE });
    latestDelete().resolve({});
    const deleteRefresh = latestList();
    expect(deleteRefresh.isSettled()).toBe(false);

    flowDeferreds
      .find((entry) => entry.key === CUSTOM_TWO)
      ?.reject({
        status: 404,
      });
    expect(deleteRefresh.abort).toHaveBeenCalled();
    const notFoundRefresh = latestList();
    expect(notFoundRefresh).not.toBe(deleteRefresh);
    expect(card({ id: CUSTOM_TWO })).toBeUndefined();

    notFoundRefresh.resolve(listResponse({ customs: [] }));
    settleAllFlows();
    expect(panelBusy()).toBe("false");
    expect(cards().map((node) => node.dataset.flowId)).toEqual(BUILTIN_IDS);
  });

  it("a takeover aborted by leaving Flows clears busy silently", () => {
    openFlowsWithList();
    startDelete({ id: CUSTOM_ONE });
    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    const loadedRegion = document.getElementById(
      "MetricsPanelFlowsAnnouncement",
    ) as HTMLElement;
    loadedRegion.textContent = "";
    latestDelete().resolve({});
    expect(panelBusy()).toBe("true");
    clickTab({ id: "MetricsTabApi" });
    expect(panelBusy()).toBe("false");
    expect(loadedRegion.textContent).toBe("");
  });

  describe("list-Retry success focus (DD-24)", () => {
    function openFailedList(): void {
      initMetricsDashboard();
      clickTab({ id: "MetricsTabFlows" });
      latestList().reject({ status: 500 });
      expect(listRetryButton()).toBeTruthy();
    }

    it("moves focus to the heading when focus is still on the Retry button", () => {
      openFailedList();
      listRetryButton().click();
      listRetryButton().focus();
      latestList().resolve(listResponse());
      expect(document.activeElement).toBe(heading());
    });

    it("moves focus to the heading when focus fell to body", () => {
      openFailedList();
      listRetryButton().click();
      blurToBody();
      latestList().resolve(listResponse());
      expect(document.activeElement).toBe(heading());
    });

    it("leaves focus alone when it is elsewhere", () => {
      openFailedList();
      listRetryButton().click();
      const outside = focusOutside();
      latestList().resolve(listResponse());
      expect(document.activeElement).toBe(outside);
    });
  });

  describe("focus restore across renders", () => {
    it("keeps focus on a Delete button when a sibling settles", () => {
      openFlowsWithList({ settle: false });
      deleteButton({ id: CUSTOM_TWO }).focus();
      flowDeferreds[0].resolve();
      expect(document.activeElement).toBe(deleteButton({ id: CUSTOM_TWO }));
    });

    it("keeps focus on Cancel and on Confirm when a sibling settles", () => {
      openFlowsWithList({ settle: false });
      deleteButton({ id: CUSTOM_ONE }).click();
      flowDeferreds[0].resolve();
      expect(document.activeElement).toBe(cancelButton({ id: CUSTOM_ONE }));

      confirmButton({ id: CUSTOM_ONE }).focus();
      flowDeferreds[1].resolve();
      expect(document.activeElement).toBe(confirmButton({ id: CUSTOM_ONE }));
    });

    it("keeps focus on a card's Retry button when its card is rebuilt", () => {
      openFlowsWithList({ settle: false });
      flowDeferreds
        .find((entry) => entry.key === BUILTIN_IDS[0])
        ?.reject({
          status: 500,
        });
      const retry = control({
        id: BUILTIN_IDS[0],
        attribute: "data-flow-retry",
      });
      retry.focus();
      flowDeferreds.find((entry) => entry.key === BUILTIN_IDS[1])?.resolve();
      expect(document.activeElement?.hasAttribute("data-flow-retry")).toBe(
        true,
      );
      expect(document.activeElement).toBe(
        control({ id: BUILTIN_IDS[0], attribute: "data-flow-retry" }),
      );
      expect(
        document.activeElement?.closest<HTMLElement>(".flow-card")?.dataset
          .flowId,
      ).toBe(BUILTIN_IDS[0]);
    });

    it("keeps focus on a Delete button across a list refetch rebuild", () => {
      openFlowsWithList();
      deleteButton({ id: CUSTOM_TWO }).focus();
      vi.advanceTimersByTime(POLL_INTERVAL_MS);
      latestList().resolve(listResponse({ customs: [CUSTOM_ONE, CUSTOM_TWO] }));
      settleAllFlows();
      expect(document.activeElement).toBe(deleteButton({ id: CUSTOM_TWO }));
    });

    it("falls back to the card section when the focused control is gone but the card stays", () => {
      openFlowsWithList();
      startDelete({ id: CUSTOM_ONE });
      confirmButton({ id: CUSTOM_ONE }).focus();
      // A page-replacing (handled) 429 only re-renders: no post-wait focus
      // move, and the card is rebuilt without a Confirm button.
      Object.assign(latestDelete().xhr, { _429Handled: true });
      latestDelete().reject({ status: 429 });
      expect(confirmButton({ id: CUSTOM_ONE })).toBeFalsy();
      expect(document.activeElement).toBe(card({ id: CUSTOM_ONE }));
    });

    it("refocuses a locked Delete rebuilt by the lock toggle", () => {
      openFlowsWithList();
      deleteButton({ id: CUSTOM_ONE }).click();
      deleteButton({ id: CUSTOM_TWO }).focus();
      confirmButton({ id: CUSTOM_ONE }).click();
      expect(document.activeElement).toBe(deleteButton({ id: CUSTOM_TWO }));
      expect(
        deleteButton({ id: CUSTOM_TWO }).getAttribute("aria-disabled"),
      ).toBe("true");
    });

    it("falls back to the heading when the focused card is gone", () => {
      openFlowsWithList();
      deleteButton({ id: CUSTOM_ONE }).click();
      vi.advanceTimersByTime(POLL_INTERVAL_MS);
      latestList().resolve(listResponse({ customs: [CUSTOM_TWO] }));
      expect(document.activeElement).toBe(heading());
    });
  });
});
