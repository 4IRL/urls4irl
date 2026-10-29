/**
 * Flows grid driven by the admin list endpoint: toolbar, list-failure
 * fallback, request ownership of the single list slot, per-card Retry,
 * timeout handling and silent `/flow` 404 removal.
 *
 * Every `fetchMetricFlows` / `fetchFlow` stub is DEFERRED (settled by the
 * test) and its `abort()` mirrors jqXHR: `fail` then `always`, synchronously.
 * The real `flow-card.js` renders, so assertions read the actual DOM.
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

const ANNOUNCEMENT_TEXT = "Flow funnels updated.";
const POLL_INTERVAL_MS = 60_000;
const BUILTIN_IDS: string[] = Object.values(FLOW_IDS);
const [ID_A, ID_B, ID_C] = BUILTIN_IDS;
const CUSTOM_ONE = "custom_1";
const CUSTOM_TWO = "custom_2";

interface Deferred {
  key: string;
  xhr: JQuery.jqXHR;
  abort: ReturnType<typeof vi.fn>;
  isSettled: () => boolean;
  resolve: (response?: unknown) => void;
  resolveLate: (response?: unknown) => void;
  reject: (options?: {
    status?: number;
    readyState?: number;
    statusText?: string;
    responseJSON?: unknown;
    _429Handled?: boolean;
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

function makeDeferred({ key }: { key: string }): Deferred {
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
    // Delivers a response that arrives after abort() (a race a real browser
    // can produce); bypasses the double-settle guard on purpose.
    resolveLate: (response = okFlowResponse()) => {
      fake.status = 200;
      fake.readyState = 4;
      doneCallbacks.forEach((callback) => callback(response));
      alwaysCallbacks.forEach((callback) => callback());
    },
    reject: ({
      status = 500,
      readyState = 4,
      statusText = "error",
      responseJSON,
      _429Handled = false,
    } = {}) => {
      if (settled) return;
      settled = true;
      fake._429Handled = _429Handled;
      fake.status = status;
      fake.readyState = readyState;
      fake.statusText = statusText;
      fake.responseJSON = responseJSON;
      failCallbacks.forEach((callback) => callback(fake));
      alwaysCallbacks.forEach((callback) => callback());
    },
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

function listResponse({
  customs = [],
  extra = [],
}: {
  customs?: string[];
  extra?: ReturnType<typeof makeListEntry>[];
} = {}) {
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
      ...extra,
    ],
  };
}

describe("metrics-dashboard flows grid (list-driven)", () => {
  let flowDeferreds: Deferred[] = [];
  let listDeferreds: Deferred[] = [];

  beforeEach(() => {
    document.body.innerHTML = DASHBOARD_HTML;
    flowDeferreds = [];
    listDeferreds = [];
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
    vi.useFakeTimers();
  });

  afterEach(() => {
    _resetMetricsDashboardForTests();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  function panel(): HTMLElement {
    return document.getElementById("MetricsPanelFlows") as HTMLElement;
  }
  function grid(): HTMLElement {
    return document.getElementById("MetricsFlowGrid") as HTMLElement;
  }
  function countText(): string {
    return (document.getElementById("MetricsFlowsCount") as HTMLElement)
      .textContent as string;
  }
  function hint(): HTMLElement {
    return document.getElementById("MetricsFlowsHint") as HTMLElement;
  }
  function heading(): HTMLElement {
    return document.getElementById("MetricsFlowsHeading") as HTMLElement;
  }
  function announcement(): string {
    return document.getElementById("MetricsPanelFlowsAnnouncement")
      ?.textContent as string;
  }
  // Counts writes to the announcement live region from now on (synchronously,
  // via takeRecords), so "announces exactly once" is observable.
  function watchAnnouncementWrites(): () => number {
    const observer = new MutationObserver(() => {});
    observer.observe(
      document.getElementById("MetricsPanelFlowsAnnouncement") as HTMLElement,
      { childList: true, characterData: true, subtree: true },
    );
    return () => observer.takeRecords().length;
  }
  function bannerShown(): boolean {
    return !document
      .getElementById("MetricsErrorBanner")
      ?.classList.contains("hidden");
  }
  function cards(): HTMLElement[] {
    return Array.from(grid().querySelectorAll<HTMLElement>(".flow-card"));
  }
  function card({ id }: { id: string }): HTMLElement | undefined {
    return cards().find((node) => node.dataset.flowId === id);
  }
  function stateOf({ id }: { id: string }): string | undefined {
    return card({ id })?.dataset.flowState;
  }
  function listError(): HTMLElement | null {
    return grid().querySelector<HTMLElement>(".flows-list-error");
  }
  function listRetry(): HTMLElement {
    return grid().querySelector<HTMLElement>(
      "[data-flow-list-retry]",
    ) as HTMLElement;
  }
  function latestFlow({ id }: { id: string }): Deferred {
    const matches = flowDeferreds.filter((entry) => entry.key === id);
    return matches[matches.length - 1];
  }
  function latestList(): Deferred {
    return listDeferreds[listDeferreds.length - 1];
  }
  function clickTab({ id }: { id: string }): void {
    (document.getElementById(id) as HTMLButtonElement).click();
  }
  function openFlows(): void {
    initMetricsDashboard();
    clickTab({ id: "MetricsTabFlows" });
  }
  function openFlowsWithList({
    customs = [CUSTOM_ONE, CUSTOM_TWO],
  }: { customs?: string[] } = {}): void {
    openFlows();
    latestList().resolve(listResponse({ customs }));
  }
  // Resolves every unsettled request, including ones admitted by the queue as
  // earlier ones settle (the array grows while iterating).
  function settleAllFlows(): void {
    for (let index = 0; index < flowDeferreds.length; index++) {
      if (!flowDeferreds[index].isSettled()) flowDeferreds[index].resolve();
    }
  }
  // At most 4 `/flow` requests run at once, so custom flows are requested only
  // after built-ins settle. Resolve the four built-ins to admit them.
  function settleBuiltins(): void {
    for (const id of BUILTIN_IDS) {
      latestFlow({ id }).resolve();
    }
  }

  it("opening Flows issues one list request, then one /flow per listed id with custom titles", () => {
    openFlows();
    expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(1);
    expect(fetchFlowSpy).not.toHaveBeenCalled();

    latestList().resolve(listResponse({ customs: [CUSTOM_ONE, CUSTOM_TWO] }));

    expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(1);
    expect(fetchFlowSpy).toHaveBeenCalledTimes(4);
    expect(cards().map((node) => node.dataset.flowId)).toEqual([
      ...BUILTIN_IDS,
      CUSTOM_ONE,
      CUSTOM_TWO,
    ]);
    expect(card({ id: CUSTOM_ONE })?.textContent).toContain(
      `Name of ${CUSTOM_ONE}`,
    );
    expect(
      card({ id: CUSTOM_ONE })?.querySelector(".flow-badge.custom"),
    ).not.toBeNull();
  });

  it("toolbar: loading text, then the count with the cap, and the hint only with zero custom", () => {
    openFlows();
    expect(countText()).toBe("Loading flows…");
    expect(hint().hidden).toBe(true);

    latestList().resolve(listResponse({ customs: [CUSTOM_ONE, CUSTOM_TWO] }));
    expect(countText()).toBe("4 built-in · 2 custom (of 20)");
    expect(hint().hidden).toBe(true);
  });

  it("toolbar shows the hint when the list has no custom flows", () => {
    openFlowsWithList({ customs: [] });
    expect(countText()).toBe("4 built-in · 0 custom (of 20)");
    expect(hint().hidden).toBe(false);
    expect(hint().textContent).not.toBe("");
  });

  it("while the first list is pending the four built-ins render as loading skeletons", () => {
    openFlows();
    expect(cards().map((node) => node.dataset.flowState)).toEqual([
      "loading",
      "loading",
      "loading",
      "loading",
    ]);
  });

  it("built-in nodes are kept when the first list arrives (no remove/re-add)", () => {
    openFlows();
    const before = cards();
    latestList().resolve(listResponse({ customs: [CUSTOM_ONE] }));
    const after = cards();
    before.forEach((node, index) => expect(after[index]).toBe(node));
    expect(after).toHaveLength(5);
  });

  it("built-in nodes keep identity when a later list resolves after a first-list failure", () => {
    openFlows();
    latestList().reject({ status: 500 });
    settleBuiltins();
    const before = cards();
    vi.advanceTimersByTime(POLL_INTERVAL_MS);
    latestList().resolve(listResponse({ customs: [CUSTOM_ONE] }));
    const after = cards();
    before.forEach((node, index) => expect(after[index]).toBe(node));
  });

  it("a list-seeded invalid entry renders needs-attention before /flow resolves and keeps its text after the 422", () => {
    openFlows();
    latestList().resolve(
      listResponse({
        extra: [
          makeListEntry({
            id: CUSTOM_ONE,
            is_builtin: false,
            errors: { "steps.1.event_name": ["unknown"] },
            first_invalid: {
              step_index: 1,
              field: "event_name",
              reason: "Unknown event.",
            },
          }),
        ],
      }),
    );
    expect(stateOf({ id: CUSTOM_ONE })).toBe("invalid");
    expect(
      card({ id: CUSTOM_ONE })?.querySelector(".flow-retry-btn"),
    ).toBeNull();
    const before = card({ id: CUSTOM_ONE })?.textContent;
    expect(before).toContain("Step 2: Unknown event.");

    settleBuiltins();
    latestFlow({ id: CUSTOM_ONE }).reject({
      status: 422,
      responseJSON: {
        error: "flow_invalid",
        invalid: {
          step_index: 1,
          field: "event_name",
          reason: "Unknown event.",
        },
      },
    });
    expect(stateOf({ id: CUSTOM_ONE })).toBe("invalid");
    expect(card({ id: CUSTOM_ONE })?.textContent).toBe(before);
  });

  it("a list-seeded invalid entry with a null first_invalid falls back to the help text without a step number", () => {
    openFlows();
    latestList().resolve(
      listResponse({
        extra: [
          makeListEntry({
            id: CUSTOM_ONE,
            is_builtin: false,
            errors: { "": ["broken"] },
            first_invalid: null,
          }),
        ],
      }),
    );
    expect(stateOf({ id: CUSTOM_ONE })).toBe("invalid");
    expect(card({ id: CUSTOM_ONE })?.textContent).not.toContain("Step ");
  });

  it("a /flow 200 after a list-seeded invalid replaces it with the funnel card", () => {
    openFlows();
    latestList().resolve(
      listResponse({
        extra: [
          makeListEntry({
            id: CUSTOM_ONE,
            is_builtin: false,
            errors: { "steps.0.event_name": ["unknown"] },
            first_invalid: { step_index: 0, field: "event_name", reason: "x" },
          }),
        ],
      }),
    );
    expect(stateOf({ id: CUSTOM_ONE })).toBe("invalid");
    settleBuiltins();
    latestFlow({ id: CUSTOM_ONE }).resolve();
    expect(stateOf({ id: CUSTOM_ONE })).toBe("response");
  });

  describe("list failure", () => {
    it("first failure falls back to the four built-ins with the banner, the count and an inline Retry", () => {
      openFlows();
      latestList().reject({ status: 500 });

      expect(bannerShown()).toBe(true);
      expect(countText()).toBe("4 built-in");
      expect(cards().map((node) => node.dataset.flowId)).toEqual(BUILTIN_IDS);
      expect(fetchFlowSpy).toHaveBeenCalledTimes(4);
      expect(listError()).not.toBeNull();
      expect(listRetry().textContent).toBe("Retry");
      expect(listError()?.classList.contains("flow-card")).toBe(false);
    });

    it("a list timeout is a failure too", () => {
      openFlows();
      latestList().reject({
        status: 0,
        readyState: 0,
        statusText: "timeout",
      });
      expect(listError()).not.toBeNull();
      expect(bannerShown()).toBe(true);
    });

    it("Retry keeps the error node, disables itself as Retrying, ignores a second click, and focus stays on it", () => {
      openFlows();
      latestList().reject({ status: 500 });
      const errorNode = listError();
      const retry = listRetry();
      retry.focus();

      retry.click();
      expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(2);
      expect(listError()).toBe(errorNode);
      expect(listRetry().getAttribute("aria-disabled")).toBe("true");
      expect(listRetry().textContent).toBe("Retrying…");
      expect(document.activeElement).toBe(retry);

      listRetry().click();
      expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(2);

      // Failing again restores the enabled text on the same node.
      latestList().reject({ status: 500 });
      expect(listError()).toBe(errorNode);
      expect(listRetry().hasAttribute("aria-disabled")).toBe(false);
      expect(listRetry().textContent).toBe("Retry");
      expect(document.activeElement).toBe(retry);
    });

    it("Retry success removes the node, shows custom cards and focuses the heading", () => {
      openFlows();
      latestList().reject({ status: 500 });
      listRetry().focus();
      listRetry().click();

      latestList().resolve(listResponse({ customs: [CUSTOM_ONE] }));

      expect(listError()).toBeNull();
      expect(card({ id: CUSTOM_ONE })).toBeDefined();
      expect(countText()).toBe("4 built-in · 1 custom (of 20)");
      expect(document.activeElement).toBe(heading());
    });

    it("Retry success does not steal focus that moved elsewhere", () => {
      openFlows();
      latestList().reject({ status: 500 });
      listRetry().click();
      const other = document.getElementById("MetricsTabApi") as HTMLElement;
      other.focus();

      latestList().resolve(listResponse());

      expect(document.activeElement).toBe(other);
    });

    it("a poll failure after a good load keeps the custom cards, the last count and shows the inline error", () => {
      openFlowsWithList();
      settleAllFlows();
      expect(card({ id: CUSTOM_ONE })).toBeDefined();

      vi.advanceTimersByTime(POLL_INTERVAL_MS);
      expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(2);
      latestList().reject({ status: 500 });
      expect(bannerShown()).toBe(true);
      settleBuiltins();

      expect(card({ id: CUSTOM_ONE })).toBeDefined();
      expect(card({ id: CUSTOM_TWO })).toBeDefined();
      expect(countText()).toBe("4 built-in · 2 custom (of 20)");
      expect(listError()).not.toBeNull();
      // Fan-out over the stale list: custom ids are re-requested.
      expect(
        flowDeferreds.filter((entry) => entry.key === CUSTOM_ONE),
      ).toHaveLength(2);
    });

    it("after a failure the fallback fan-out leaves busy to onIdle and announces exactly once", () => {
      openFlows();
      const writes = watchAnnouncementWrites();
      latestList().reject({ status: 500 });
      expect(panel().getAttribute("aria-busy")).toBe("true");
      settleAllFlows();
      expect(panel().hasAttribute("aria-busy")).toBe(false);
      expect(announcement()).toBe(ANNOUNCEMENT_TEXT);
      expect(writes()).toBe(1);
    });

    it("the list-failure banner survives successful /flow settles that follow it", () => {
      openFlows();
      latestList().reject({ status: 500 });
      expect(bannerShown()).toBe(true);
      settleAllFlows();
      expect(stateOf({ id: ID_A })).toBe("response");
      expect(bannerShown()).toBe(true);
      expect(listError()).not.toBeNull();
    });

    it("a handled 429 list failure suppresses the banner but keeps the inline error and the built-in fallback", () => {
      openFlows();
      latestList().reject({ status: 429, _429Handled: true });
      expect(bannerShown()).toBe(false);
      expect(listError()).not.toBeNull();
      expect(cards().map((node) => node.dataset.flowId)).toEqual(BUILTIN_IDS);
    });

    it("a JSON 429 with _429Handled falsy is still a list failure", () => {
      openFlows();
      latestList().reject({ status: 429 });
      expect(listError()).not.toBeNull();
      expect(bannerShown()).toBe(true);
    });

    it("a stored 422 beats the list-seeded text", () => {
      openFlows();
      latestList().resolve(
        listResponse({
          extra: [
            makeListEntry({
              id: CUSTOM_ONE,
              is_builtin: false,
              errors: { "steps.0.event_name": ["unknown"] },
              first_invalid: {
                step_index: 0,
                field: "event_name",
                reason: "Seeded reason.",
              },
            }),
          ],
        }),
      );
      settleBuiltins();
      latestFlow({ id: CUSTOM_ONE }).reject({
        status: 422,
        responseJSON: {
          error: "flow_invalid",
          invalid: {
            step_index: 0,
            field: "event_name",
            reason: "Stored reason.",
          },
        },
      });
      expect(card({ id: CUSTOM_ONE })?.textContent).toContain("Stored reason.");
      expect(card({ id: CUSTOM_ONE })?.textContent).not.toContain(
        "Seeded reason.",
      );
    });
  });

  describe("revisit gate and abort sites", () => {
    it("an aborted load re-requests once on return; a resolved list is not re-requested", () => {
      openFlows();
      clickTab({ id: "MetricsTabApi" });
      // Leaving mid-load aborted it (idle): returning re-requests once.
      expect(listDeferreds[0].abort).toHaveBeenCalled();
      clickTab({ id: "MetricsTabFlows" });
      expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(2);

      latestList().resolve(listResponse());
      clickTab({ id: "MetricsTabApi" });
      clickTab({ id: "MetricsTabFlows" });
      expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(2);
    });

    it("leaving Flows mid-load clears busy silently and a response that would have arrived starts no fan-out", () => {
      openFlows();
      expect(panel().getAttribute("aria-busy")).toBe("true");
      clickTab({ id: "MetricsTabApi" });

      expect(panel().hasAttribute("aria-busy")).toBe(false);
      expect(announcement()).toBe("");
      expect(fetchFlowSpy).not.toHaveBeenCalled();

      // The aborted response arriving late starts no fan-out.
      listDeferreds[0].resolveLate(listResponse({ customs: [CUSTOM_ONE] }));
      expect(fetchFlowSpy).not.toHaveBeenCalled();
      expect(panel().hasAttribute("aria-busy")).toBe(false);

      // Returning re-requests the list once and fans out after it resolves.
      clickTab({ id: "MetricsTabFlows" });
      expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(2);
      expect(fetchFlowSpy).not.toHaveBeenCalled();
      latestList().resolve(listResponse());
      expect(fetchFlowSpy).toHaveBeenCalledTimes(4);
    });

    it("leaving and returning after a failed first list sends no request and keeps the inline error", () => {
      openFlows();
      latestList().reject({ status: 500 });
      fetchMetricFlowsSpy.mockClear();

      clickTab({ id: "MetricsTabApi" });
      clickTab({ id: "MetricsTabFlows" });

      expect(fetchMetricFlowsSpy).not.toHaveBeenCalled();
      expect(listError()).not.toBeNull();
    });

    it("a window change while Flows is hidden marks the list stale: returning requests it once", () => {
      openFlowsWithList();
      settleAllFlows();
      clickTab({ id: "MetricsTabApi" });
      fetchMetricFlowsSpy.mockClear();

      (
        document.querySelector(
          '.MetricsWindowButton[data-window="week"]',
        ) as HTMLButtonElement
      ).click();
      expect(fetchMetricFlowsSpy).not.toHaveBeenCalled();

      clickTab({ id: "MetricsTabFlows" });
      expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(1);
      // The retained list still rendered while the new one loads.
      expect(card({ id: CUSTOM_ONE })).toBeDefined();
    });

    it("a poll tick while Flows is hidden sends no list request and returning sends one", () => {
      openFlowsWithList();
      settleAllFlows();
      clickTab({ id: "MetricsTabApi" });
      fetchMetricFlowsSpy.mockClear();

      vi.advanceTimersByTime(POLL_INTERVAL_MS);
      expect(fetchMetricFlowsSpy).not.toHaveBeenCalled();
      clickTab({ id: "MetricsTabFlows" });
      expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(1);
    });

    it("an abort whose fail fires synchronously causes no status or busy write from that settle", () => {
      openFlows();
      const first = latestList();
      vi.advanceTimersByTime(POLL_INTERVAL_MS);
      // The poll's load aborted the first request; its synchronous fail must
      // not have flagged an error or cleared the new request's busy.
      expect(first.abort).toHaveBeenCalled();
      expect(listError()).toBeNull();
      expect(bannerShown()).toBe(false);
      expect(panel().getAttribute("aria-busy")).toBe("true");

      // No status was written by the stale settle: the second load completes
      // normally and a revisit sends no further list request.
      latestList().resolve(listResponse());
      expect(listError()).toBeNull();
      expect(countText()).toBe("4 built-in · 0 custom (of 20)");
      fetchMetricFlowsSpy.mockClear();
      clickTab({ id: "MetricsTabApi" });
      clickTab({ id: "MetricsTabFlows" });
      expect(fetchMetricFlowsSpy).not.toHaveBeenCalled();
    });

    it("a poll's load aborts the older one and only the newest response lands", () => {
      openFlows();
      const first = latestList();
      vi.advanceTimersByTime(POLL_INTERVAL_MS);
      const second = latestList();
      second.resolve(listResponse({ customs: [CUSTOM_TWO] }));
      first.resolveLate(listResponse({ customs: [CUSTOM_ONE] }));

      expect(card({ id: CUSTOM_TWO })).toBeDefined();
      expect(card({ id: CUSTOM_ONE })).toBeUndefined();
    });

    it("an empty list announces exactly once and clears busy", () => {
      openFlows();
      const writes = watchAnnouncementWrites();
      latestList().resolve({ flows: [] });

      expect(panel().hasAttribute("aria-busy")).toBe(false);
      expect(announcement()).toBe(ANNOUNCEMENT_TEXT);
      expect(writes()).toBe(1);
      expect(cards()).toHaveLength(0);
    });

    it("a listed id with no cache or state renders as loading and the activation catch-up enqueues exactly it", () => {
      openFlowsWithList({ customs: [CUSTOM_ONE] });
      // A silent abort leaves the id with neither a cache entry nor a state.
      latestFlow({ id: ID_B }).reject({
        status: 0,
        readyState: 0,
        statusText: "abort",
      });
      settleAllFlows();
      expect(stateOf({ id: ID_B })).toBe("loading");
      expect(panel().hasAttribute("aria-busy")).toBe(false);
      fetchFlowSpy.mockClear();

      clickTab({ id: "MetricsTabApi" });
      clickTab({ id: "MetricsTabFlows" });

      expect(fetchFlowSpy).toHaveBeenCalledTimes(1);
      expect(fetchFlowSpy.mock.calls[0][0].flowId).toBe(ID_B);
      expect(panel().getAttribute("aria-busy")).toBe("true");
    });

    it("a loaded and complete list: a revisit enqueues nothing and sets no busy", () => {
      openFlowsWithList({ customs: [CUSTOM_ONE] });
      settleAllFlows();
      fetchFlowSpy.mockClear();

      clickTab({ id: "MetricsTabApi" });
      clickTab({ id: "MetricsTabFlows" });
      expect(fetchFlowSpy).not.toHaveBeenCalled();
      expect(panel().hasAttribute("aria-busy")).toBe(false);
    });

    it("more listed ids than the cap: settling one admits the next in list order", () => {
      openFlows();
      latestList().resolve(listResponse({ customs: [CUSTOM_ONE, CUSTOM_TWO] }));
      expect(fetchFlowSpy).toHaveBeenCalledTimes(4);
      latestFlow({ id: ID_C }).resolve();
      expect(fetchFlowSpy).toHaveBeenCalledTimes(5);
      expect(fetchFlowSpy.mock.calls[4][0].flowId).toBe(CUSTOM_ONE);
      latestFlow({ id: ID_A }).resolve();
      expect(fetchFlowSpy.mock.calls[5][0].flowId).toBe(CUSTOM_TWO);
    });

    it("the card order is the order the list returns, not built-ins first", () => {
      openFlows();
      latestList().resolve({
        flows: [
          makeListEntry({ id: CUSTOM_ONE, is_builtin: false }),
          makeListEntry({ id: ID_B }),
          makeListEntry({ id: ID_A }),
        ],
      });
      expect(cards().map((node) => node.dataset.flowId)).toEqual([
        CUSTOM_ONE,
        ID_B,
        ID_A,
      ]);
    });
  });

  describe("/flow outcomes", () => {
    it("a 404 for a custom id removes the card, refetches the list once and shows no banner", () => {
      openFlowsWithList();
      fetchMetricFlowsSpy.mockClear();

      settleBuiltins();
      latestFlow({ id: CUSTOM_ONE }).reject({ status: 404 });

      expect(card({ id: CUSTOM_ONE })).toBeUndefined();
      expect(bannerShown()).toBe(false);
      expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(1);

      // The refresh drops the id; others untouched.
      latestList().resolve(listResponse({ customs: [CUSTOM_TWO] }));
      expect(card({ id: CUSTOM_ONE })).toBeUndefined();
      expect(card({ id: CUSTOM_TWO })).toBeDefined();
      expect(countText()).toBe("4 built-in · 1 custom (of 20)");
    });

    it("a 404 for a built-in id shows the error card and the banner", () => {
      openFlowsWithList();
      fetchMetricFlowsSpy.mockClear();

      latestFlow({ id: ID_A }).reject({ status: 404 });

      expect(stateOf({ id: ID_A })).toBe("error");
      expect(bannerShown()).toBe(true);
      expect(fetchMetricFlowsSpy).not.toHaveBeenCalled();
    });

    it("a custom 404 while Flows is hidden removes the card locally with no list request; returning requests once", () => {
      openFlowsWithList();
      settleBuiltins();
      clickTab({ id: "MetricsTabApi" });
      fetchMetricFlowsSpy.mockClear();
      const inFlight = latestFlow({ id: CUSTOM_ONE });
      // The queue is not aborted on leave, so the request can still settle.
      inFlight.reject({ status: 404 });

      expect(fetchMetricFlowsSpy).not.toHaveBeenCalled();
      expect(bannerShown()).toBe(false);

      clickTab({ id: "MetricsTabFlows" });
      expect(card({ id: CUSTOM_ONE })).toBeUndefined();
      expect(fetchMetricFlowsSpy).toHaveBeenCalledTimes(1);
    });

    it("a /flow timeout renders the error card with Retry and the banner", () => {
      openFlowsWithList();
      latestFlow({ id: ID_A }).reject({
        status: 0,
        readyState: 0,
        statusText: "timeout",
      });
      expect(stateOf({ id: ID_A })).toBe("error");
      expect(
        card({ id: ID_A })?.querySelector("[data-flow-retry]"),
      ).not.toBeNull();
      expect(bannerShown()).toBe(true);
    });

    it("an aborted /flow request (readyState 0) shows no banner and no error state", () => {
      openFlowsWithList();
      latestFlow({ id: ID_B }).reject({
        status: 0,
        readyState: 0,
        statusText: "abort",
      });
      expect(bannerShown()).toBe(false);
      expect(stateOf({ id: ID_B })).toBe("loading");
    });
  });

  describe("plain list refresh", () => {
    // A custom 404 while Flows is active triggers the plain refresh.
    function triggerRefresh(): void {
      settleBuiltins();
      latestFlow({ id: CUSTOM_ONE }).reject({ status: 404 });
    }

    it("a refresh discovering a new id loads only that id without aborting others", () => {
      openFlowsWithList({ customs: [CUSTOM_ONE] });
      settleBuiltins();
      latestFlow({ id: CUSTOM_ONE }).reject({ status: 404 });
      const refreshList = latestList();
      fetchFlowSpy.mockClear();

      refreshList.resolve(listResponse({ customs: [CUSTOM_TWO] }));

      expect(fetchFlowSpy).toHaveBeenCalledTimes(1);
      expect(fetchFlowSpy.mock.calls[0][0].flowId).toBe(CUSTOM_TWO);
      expect(panel().getAttribute("aria-busy")).toBe("true");
      for (const id of BUILTIN_IDS) {
        expect(latestFlow({ id }).abort).not.toHaveBeenCalled();
      }
      latestFlow({ id: CUSTOM_TWO }).resolve();
      expect(panel().hasAttribute("aria-busy")).toBe(false);
    });

    it("a dropped id has its in-flight request aborted and a late response cannot resurrect it", () => {
      openFlowsWithList({ customs: [CUSTOM_ONE, CUSTOM_TWO] });
      settleBuiltins();
      // CUSTOM_ONE 404s; CUSTOM_TWO is still in flight when the refresh drops it.
      latestFlow({ id: CUSTOM_ONE }).reject({ status: 404 });
      const inFlight = latestFlow({ id: CUSTOM_TWO });
      expect(inFlight.isSettled()).toBe(false);

      latestList().resolve(listResponse());

      expect(inFlight.abort).toHaveBeenCalled();
      inFlight.resolveLate();
      expect(card({ id: CUSTOM_TWO })).toBeUndefined();
      expect(countText()).toBe("4 built-in · 0 custom (of 20)");
    });

    it("a refresh failure leaves cards, status and list as they are", () => {
      openFlowsWithList();
      triggerRefresh();
      latestList().reject({ status: 500 });

      expect(card({ id: CUSTOM_TWO })).toBeDefined();
      expect(countText()).toBe("4 built-in · 1 custom (of 20)");
      expect(listError()).toBeNull();
      expect(bannerShown()).toBe(false);
      // Status stayed loaded: a revisit sends no list request.
      fetchMetricFlowsSpy.mockClear();
      clickTab({ id: "MetricsTabApi" });
      clickTab({ id: "MetricsTabFlows" });
      expect(fetchMetricFlowsSpy).not.toHaveBeenCalled();
    });

    it("leaving Flows mid-refresh aborts the refresh and leaves the status loaded", () => {
      openFlowsWithList();
      triggerRefresh();
      const refresh = latestList();
      fetchMetricFlowsSpy.mockClear();
      clickTab({ id: "MetricsTabApi" });
      expect(refresh.abort).toHaveBeenCalled();
      clickTab({ id: "MetricsTabFlows" });

      // Status stayed loaded (not idle): no list request on return.
      expect(fetchMetricFlowsSpy).not.toHaveBeenCalled();
      expect(listError()).toBeNull();
      expect(card({ id: CUSTOM_TWO })).toBeDefined();
    });

    it("a newer refresh aborts an older one and the older response never replaces the newer list", () => {
      openFlowsWithList({ customs: [CUSTOM_ONE, CUSTOM_TWO] });
      settleBuiltins();
      latestFlow({ id: CUSTOM_ONE }).reject({ status: 404 });
      const older = latestList();
      latestFlow({ id: CUSTOM_TWO }).reject({ status: 404 });
      const newer = latestList();
      expect(newer).not.toBe(older);
      expect(older.abort).toHaveBeenCalled();

      newer.resolve(listResponse());
      older.resolveLate(listResponse({ customs: [CUSTOM_ONE, CUSTOM_TWO] }));
      expect(card({ id: CUSTOM_ONE })).toBeUndefined();
      expect(card({ id: CUSTOM_TWO })).toBeUndefined();
    });

    it("a refresh during a load sends nothing", () => {
      openFlowsWithList();
      settleBuiltins();
      // Poll starts a load, then a custom 404 arrives while it is in flight.
      vi.advanceTimersByTime(POLL_INTERVAL_MS);
      const count = fetchMetricFlowsSpy.mock.calls.length;
      latestFlow({ id: CUSTOM_ONE }).reject({ status: 404 });
      expect(fetchMetricFlowsSpy.mock.calls.length).toBe(count);
    });

    it("a failed list stays failed across leave and return with a good list: no request, error kept", () => {
      openFlowsWithList();
      settleAllFlows();
      vi.advanceTimersByTime(POLL_INTERVAL_MS);
      latestList().reject({ status: 500 });
      fetchMetricFlowsSpy.mockClear();

      clickTab({ id: "MetricsTabApi" });
      clickTab({ id: "MetricsTabFlows" });

      expect(fetchMetricFlowsSpy).not.toHaveBeenCalled();
      expect(listError()).not.toBeNull();
      expect(card({ id: CUSTOM_ONE })).toBeDefined();
    });

    it("an off-tab window change aborts an in-flight list", () => {
      openFlows();
      const first = latestList();
      clickTab({ id: "MetricsTabApi" });
      (
        document.querySelector(
          '.MetricsWindowButton[data-window="week"]',
        ) as HTMLButtonElement
      ).click();
      expect(first.abort).toHaveBeenCalled();
      expect(panel().hasAttribute("aria-busy")).toBe(false);
    });

    it("reset aborts the in-flight list and leaves busy cleared", () => {
      openFlows();
      const first = latestList();
      _resetMetricsDashboardForTests();
      expect(first.abort).toHaveBeenCalled();
      expect(panel().hasAttribute("aria-busy")).toBe(false);
    });
  });

  describe("per-card Retry", () => {
    it("re-requests only that id, keeps busy until it settles and leaves focus on the card section", () => {
      openFlowsWithList();
      latestFlow({ id: ID_A }).reject({ status: 500 });
      settleAllFlows();
      expect(panel().hasAttribute("aria-busy")).toBe(false);
      fetchFlowSpy.mockClear();

      const retry = card({ id: ID_A })?.querySelector<HTMLElement>(
        "[data-flow-retry]",
      ) as HTMLElement;
      retry.click();

      expect(fetchFlowSpy).toHaveBeenCalledTimes(1);
      expect(fetchFlowSpy.mock.calls[0][0].flowId).toBe(ID_A);
      expect(panel().getAttribute("aria-busy")).toBe("true");
      expect(stateOf({ id: ID_A })).toBe("loading");
      expect(document.activeElement).toBe(card({ id: ID_A }));

      latestFlow({ id: ID_A }).resolve();
      expect(stateOf({ id: ID_A })).toBe("response");
      // Focus was still on the card section: the replacement is refocused.
      expect(document.activeElement).toBe(card({ id: ID_A }));
      expect(panel().hasAttribute("aria-busy")).toBe(false);
    });

    it("does not steal focus when a sibling settles while focus is elsewhere", () => {
      openFlowsWithList();
      const other = document.getElementById("MetricsTabApi") as HTMLElement;
      other.focus();
      latestFlow({ id: ID_B }).resolve();
      expect(document.activeElement).toBe(other);
    });

    it("a focused card section stays focused when a sibling settles", () => {
      openFlowsWithList();
      const section = card({ id: ID_A }) as HTMLElement;
      section.focus();
      latestFlow({ id: ID_B }).resolve();
      expect(document.activeElement).toBe(section);
    });

    it("a card Retry settling while a load is in flight leaves aria-busy true and does not announce", () => {
      openFlowsWithList();
      latestFlow({ id: ID_A }).reject({ status: 500 });
      settleAllFlows();
      vi.advanceTimersByTime(POLL_INTERVAL_MS);
      // The poll's list load is held in flight and owns busy.
      (
        card({ id: ID_A })?.querySelector("[data-flow-retry]") as HTMLElement
      ).click();
      // The earlier load left its announcement behind: clear it, then watch.
      (
        document.getElementById("MetricsPanelFlowsAnnouncement") as HTMLElement
      ).textContent = "";
      const writes = watchAnnouncementWrites();
      latestFlow({ id: ID_A }).resolve();

      expect(panel().getAttribute("aria-busy")).toBe("true");
      expect(announcement()).toBe("");
      expect(writes()).toBe(0);

      // The list settles, its fan-out runs, and one announcement follows the last settle.
      latestList().resolve(listResponse({ customs: [CUSTOM_ONE, CUSTOM_TWO] }));
      expect(panel().getAttribute("aria-busy")).toBe("true");
      settleAllFlows();
      expect(panel().hasAttribute("aria-busy")).toBe(false);
      expect(announcement()).toBe(ANNOUNCEMENT_TEXT);
      expect(writes()).toBe(1);
    });
  });

  it("the id set follows the list: unlisted built-ins are not invented once a list resolved", () => {
    openFlows();
    latestList().resolve({
      flows: [makeListEntry({ id: ID_A }), makeListEntry({ id: ID_B })],
    });
    expect(cards().map((node) => node.dataset.flowId)).toEqual([ID_A, ID_B]);
    expect(fetchFlowSpy.mock.calls.map((call) => call[0].flowId)).toEqual([
      ID_A,
      ID_B,
    ]);
  });
});
