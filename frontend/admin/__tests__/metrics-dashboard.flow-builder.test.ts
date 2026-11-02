/**
 * The builder instance on the dashboard: opening pauses Flows loads, panel
 * busy, the failure banner, the "loaded" announcement and Refresh; each close
 * reason has its own tail. Driven through `_openFlowBuilderForTests` and
 * `_closeFlowBuilderForTests`.
 *
 * Every request stub is DEFERRED (settled by the test); `abort()` mirrors
 * jqXHR (`fail` then `always`, synchronously). happy-dom does not enforce
 * `inert`, so real focus behavior is proven in the functional suite.
 */

const {
  fetchSummarySpy,
  fetchTopEventsSpy,
  fetchGroupedTimeseriesSpy,
  fetchGaugesTimeseriesSpy,
  fetchFlowSpy,
  fetchMetricFlowsSpy,
  deleteMetricFlowSpy,
  fetchMetricFlowCatalogSpy,
} = vi.hoisted(() => ({
  fetchSummarySpy: vi.fn(),
  fetchTopEventsSpy: vi.fn(),
  fetchGroupedTimeseriesSpy: vi.fn(),
  fetchGaugesTimeseriesSpy: vi.fn(),
  fetchFlowSpy: vi.fn(),
  fetchMetricFlowsSpy: vi.fn(),
  deleteMetricFlowSpy: vi.fn(),
  fetchMetricFlowCatalogSpy: vi.fn(),
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
  createMetricFlow: vi.fn(),
  updateMetricFlow: vi.fn(),
  fetchMetricFlowCatalog: fetchMetricFlowCatalogSpy,
}));

vi.mock("../render-summary.js", () => ({ renderSummary: vi.fn() }));
vi.mock("../render-top-table.js", () => ({ renderTopTable: vi.fn() }));

import { FLOW_IDS, FLOW_METADATA } from "../../types/metrics-flows.js";
import {
  _closeFlowBuilderForTests,
  _openFlowBuilderForTests,
  _resetMetricsDashboardForTests,
  initMetricsDashboard,
} from "../metrics-dashboard.js";
import { createMetricFlow, updateMetricFlow } from "../metrics-query-client.js";
import { makeListEntry } from "./helpers/flow-list-mock.js";

const DASHBOARD_HTML = `
  <main id="MetricsDashboard" aria-busy="false">
    <header>
      <button id="MetricsRefreshNowBtn" type="button"></button>
    </header>
    <p id="MetricsRefreshPausedHint" hidden>Paused while editing</p>
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
      <div id="MetricsFlowBuilderMount" hidden></div>
      <div class="flows-toolbar">
        <h2 id="MetricsFlowsHeading" class="flows-heading" tabindex="-1">Flow funnels</h2>
        <span id="MetricsFlowsCount" class="flows-count"></span>
        <span id="MetricsFlowsHint" class="flows-hint" hidden></span>
        <span id="MetricsFlowsNotice" class="flows-notice" hidden></span>
        <span class="flow-new-group">
          <span id="MetricsFlowNewReason" class="flow-new-reason" hidden></span>
          <button type="button" id="MetricsFlowNewBtn" class="flow-new-btn">+ New flow</button>
        </span>
      </div>
      <div id="MetricsFlowGrid" class="flow-grid"></div>
    </section>
    <div id="MetricsErrorBanner" class="hidden"></div>
  </main>
`;

const POLL_INTERVAL_MS = 60_000;
const BUILTIN_IDS: string[] = Object.values(FLOW_IDS);
const CUSTOM_ONE = "custom_1";

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
      if (settled) return;
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

describe("metrics-dashboard flow builder: pause, Refresh and close tails", () => {
  let flowDeferreds: Deferred[] = [];
  let listDeferreds: Deferred[] = [];
  let deleteDeferreds: Deferred[] = [];
  let catalogDeferreds: Deferred[] = [];

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
    fetchMetricFlowCatalogSpy.mockReset();
    catalogDeferreds = [];
    fetchMetricFlowCatalogSpy.mockImplementation(() => {
      const deferred = makeDeferred({ key: "catalog" });
      catalogDeferreds.push(deferred);
      return deferred.xhr;
    });
    vi.useFakeTimers();
  });

  afterEach(() => {
    _resetMetricsDashboardForTests();
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  function byId(id: string): HTMLElement {
    return document.getElementById(id) as HTMLElement;
  }
  function grid(): HTMLElement {
    return byId("MetricsFlowGrid");
  }
  function mount(): HTMLElement {
    return byId("MetricsFlowBuilderMount");
  }
  function toolbar(): HTMLElement {
    return document.querySelector(".flows-toolbar") as HTMLElement;
  }
  function refreshButton(): HTMLElement {
    return byId("MetricsRefreshNowBtn");
  }
  function hint(): HTMLElement {
    return byId("MetricsRefreshPausedHint");
  }
  function banner(): HTMLElement {
    return byId("MetricsErrorBanner");
  }
  function panelBusy(): boolean {
    return byId("MetricsPanelFlows").getAttribute("aria-busy") === "true";
  }
  function loadedText(): string {
    return byId("MetricsPanelFlowsAnnouncement").textContent as string;
  }
  function cards(): HTMLElement[] {
    return Array.from(grid().querySelectorAll<HTMLElement>(".flow-card"));
  }
  function card({ id }: { id: string }): HTMLElement | undefined {
    return cards().find((node) => node.dataset.flowId === id);
  }
  function latestList(): Deferred {
    return listDeferreds[listDeferreds.length - 1];
  }
  function clickTab({ id }: { id: string }): void {
    byId(id).click();
  }
  function settleAllFlows(): void {
    for (let index = 0; index < flowDeferreds.length; index++) {
      if (!flowDeferreds[index].isSettled()) flowDeferreds[index].resolve();
    }
  }
  function openFlowsWithList({
    customs = [],
    settle = true,
  }: { customs?: string[]; settle?: boolean } = {}): void {
    initMetricsDashboard();
    clickTab({ id: "MetricsTabFlows" });
    latestList().resolve(listResponse({ customs }));
    if (settle) {
      settleAllFlows();
    }
  }
  function openBuilder(): void {
    _openFlowBuilderForTests({ mode: "create" });
  }
  function pollTick(): void {
    vi.advanceTimersByTime(POLL_INTERVAL_MS);
  }
  function flowCallsFrom({ index }: { index: number }) {
    return fetchFlowSpy.mock.calls
      .slice(index)
      .map(([args]) => args as { flowId: string; window: string });
  }
  // Open with the loads settled, then hold a fresh fan-out behind the pause:
  // a poll tick while open starts a `load` whose resolve queues every id.
  function openWithHeldFanOut({
    customs = [],
  }: { customs?: string[] } = {}): void {
    openFlowsWithList({ customs });
    openBuilder();
    pollTick();
    latestList().resolve(listResponse({ customs }));
  }

  it("keeps the builder closed and the mount hidden until opened", () => {
    openFlowsWithList();
    expect(mount().hidden).toBe(true);
    expect(toolbar().hidden).toBe(false);
    expect(grid().hidden).toBe(false);
    expect(hint().hidden).toBe(true);
    expect(refreshButton().hasAttribute("data-builder-paused")).toBe(false);
  });

  it("open swaps the toolbar and grid for the builder and clears panel busy", () => {
    openFlowsWithList({ settle: false });
    expect(panelBusy()).toBe(true);
    openBuilder();
    expect(mount().hidden).toBe(false);
    expect(toolbar().hidden).toBe(true);
    expect(grid().hidden).toBe(true);
    expect(panelBusy()).toBe(false);
  });

  it("a poll tick and a window change while open leave busy false and issue no /flow request", () => {
    openFlowsWithList();
    openBuilder();
    const before = fetchFlowSpy.mock.calls.length;
    pollTick();
    latestList().resolve(listResponse());
    expect(panelBusy()).toBe(false);
    (
      document.querySelector('[data-window="week"]') as HTMLButtonElement
    ).click();
    latestList().resolve(listResponse());
    expect(panelBusy()).toBe(false);
    expect(fetchFlowSpy.mock.calls.length).toBe(before);
  });

  it("a window change while open replaces the held queue; only the latest window loads on return", () => {
    openFlowsWithList();
    openBuilder();
    const before = fetchFlowSpy.mock.calls.length;
    (
      document.querySelector('[data-window="week"]') as HTMLButtonElement
    ).click();
    latestList().resolve(listResponse());
    (
      document.querySelector('[data-window="day"]') as HTMLButtonElement
    ).click();
    latestList().resolve(listResponse());
    expect(fetchFlowSpy.mock.calls.length).toBe(before);

    _closeFlowBuilderForTests({ reason: "cancel" });
    const calls = flowCallsFrom({ index: before });
    expect(calls.length).toBe(BUILTIN_IDS.length);
    expect(calls.every((call) => call.window === "day")).toBe(true);
    expect(calls.map((call) => call.flowId).sort()).toEqual(
      [...BUILTIN_IDS].sort(),
    );
  });

  it("a list failure while open raises no banner and leaves the builder alone", () => {
    openFlowsWithList();
    openBuilder();
    pollTick();
    expect(latestList().isSettled()).toBe(false);
    latestList().reject({ status: 500 });
    expect(banner().classList.contains("hidden")).toBe(true);
    expect(mount().hidden).toBe(false);
    expect(panelBusy()).toBe(false);
  });

  it("positive control: the same list failure with the builder closed shows the banner", () => {
    openFlowsWithList();
    pollTick();
    expect(latestList().isSettled()).toBe(false);
    latestList().reject({ status: 500 });
    expect(banner().classList.contains("hidden")).toBe(false);
  });

  it("a /flow in flight at open that fails during the pause records the card error without a banner", () => {
    openFlowsWithList({ settle: false });
    const failing = flowDeferreds[0];
    openBuilder();
    failing.reject({ status: 500 });
    expect(banner().classList.contains("hidden")).toBe(true);

    _closeFlowBuilderForTests({ reason: "cancel" });
    expect(banner().classList.contains("hidden")).toBe(true);
    expect(
      card({ id: failing.key })?.querySelector("[data-flow-retry]"),
    ).not.toBe(null);
  });

  it("opening while a list load is in flight clears busy but the load's settle still starts the held fan-out", () => {
    openFlowsWithList();
    pollTick();
    const load = latestList();
    expect(panelBusy()).toBe(true);
    openBuilder();
    expect(panelBusy()).toBe(false);

    const before = fetchFlowSpy.mock.calls.length;
    load.resolve(listResponse());
    expect(fetchFlowSpy.mock.calls.length).toBe(before);
    expect(panelBusy()).toBe(false);

    _closeFlowBuilderForTests({ reason: "cancel" });
    expect(flowCallsFrom({ index: before }).length).toBe(BUILTIN_IDS.length);
  });

  it("opening with loads in flight shows no 'loaded' announcement; return sets busy and announces at the end", () => {
    openFlowsWithList({ settle: false });
    byId("MetricsPanelFlowsAnnouncement").textContent = "";
    openBuilder();
    settleAllFlows();
    expect(panelBusy()).toBe(false);
    expect(loadedText()).toBe("");

    pollTick();
    latestList().resolve(listResponse());
    _closeFlowBuilderForTests({ reason: "cancel" });
    expect(panelBusy()).toBe(true);
    expect(loadedText()).toBe("");
    settleAllFlows();
    expect(panelBusy()).toBe(false);
    expect(loadedText()).not.toBe("");
  });

  it("open clears a pending delete confirm and card messages", () => {
    openFlowsWithList({ customs: [CUSTOM_ONE] });
    (
      card({ id: CUSTOM_ONE })?.querySelector(
        "[data-flow-delete]",
      ) as HTMLElement
    ).click();
    expect(grid().querySelector("[data-flow-confirm]")).not.toBeNull();
    openBuilder();
    _closeFlowBuilderForTests({ reason: "cancel" });
    expect(grid().querySelector("[data-flow-confirm]")).toBeNull();
  });

  it("open clears a card message", () => {
    openFlowsWithList({ customs: [CUSTOM_ONE] });
    (
      card({ id: CUSTOM_ONE })?.querySelector(
        "[data-flow-delete]",
      ) as HTMLElement
    ).click();
    (
      card({ id: CUSTOM_ONE })?.querySelector(
        "[data-flow-confirm-delete]",
      ) as HTMLElement
    ).click();
    deleteDeferreds[deleteDeferreds.length - 1].reject({ status: 500 });
    const message = "Couldn't delete this flow. Try again.";
    expect(card({ id: CUSTOM_ONE })?.textContent).toContain(message);
    openBuilder();
    _closeFlowBuilderForTests({ reason: "cancel" });
    settleAllFlows();
    expect(card({ id: CUSTOM_ONE })?.textContent).not.toContain(message);
  });

  describe("close tails by reason", () => {
    it.each(["saved", "deleted", "missing"] as const)(
      "'%s' only unpauses and unhides: no render, refresh, drain or /flow request",
      (reason) => {
        openWithHeldFanOut({ customs: [CUSTOM_ONE] });
        const flowCalls = fetchFlowSpy.mock.calls.length;
        const listCalls = fetchMetricFlowsSpy.mock.calls.length;
        _closeFlowBuilderForTests({ reason });
        expect(mount().hidden).toBe(true);
        expect(toolbar().hidden).toBe(false);
        expect(grid().hidden).toBe(false);
        expect(fetchFlowSpy.mock.calls.length).toBe(flowCalls);
        expect(fetchMetricFlowsSpy.mock.calls.length).toBe(listCalls);
        expect(panelBusy()).toBe(false);
      },
    );

    it("'cancel' renders, refreshes once, drains the held ids and sets busy again", () => {
      openWithHeldFanOut({ customs: [CUSTOM_ONE] });
      const flowCalls = fetchFlowSpy.mock.calls.length;
      const listCalls = fetchMetricFlowsSpy.mock.calls.length;
      _closeFlowBuilderForTests({ reason: "cancel" });
      expect(grid().hidden).toBe(false);
      expect(fetchMetricFlowsSpy.mock.calls.length).toBe(listCalls + 1);
      const drained = flowCallsFrom({ index: flowCalls });
      expect(drained.length).toBe(BUILTIN_IDS.length);
      expect(drained.map((call) => call.flowId).sort()).toEqual(
        [...BUILTIN_IDS].sort(),
      );
      expect(panelBusy()).toBe(true);
    });

    it("'tab-accept' aborts the whole queue, issues no request and leaves the list idle for a full fan-out", () => {
      openWithHeldFanOut();
      const flowCalls = fetchFlowSpy.mock.calls.length;
      const listCalls = fetchMetricFlowsSpy.mock.calls.length;
      _closeFlowBuilderForTests({ reason: "tab-accept" });
      expect(fetchFlowSpy.mock.calls.length).toBe(flowCalls);
      expect(fetchMetricFlowsSpy.mock.calls.length).toBe(listCalls);
      expect(panelBusy()).toBe(false);
      expect(refreshButton().hasAttribute("data-builder-paused")).toBe(false);
      expect(refreshButton().getAttribute("aria-disabled")).not.toBe("true");
      expect(hint().hidden).toBe(true);

      clickTab({ id: "MetricsTabApi" });
      clickTab({ id: "MetricsTabFlows" });
      expect(fetchMetricFlowsSpy.mock.calls.length).toBe(listCalls + 1);
    });

    it("'tab-accept' aborts a /flow in flight and the discarded queue never reloads on return", () => {
      openFlowsWithList({ settle: false });
      const inFlight = flowDeferreds.filter((entry) => !entry.isSettled());
      expect(inFlight.length).toBeGreaterThan(0);
      openBuilder();
      pollTick();
      latestList().resolve(listResponse());
      _closeFlowBuilderForTests({ reason: "tab-accept" });
      for (const entry of inFlight) {
        expect(entry.abort).toHaveBeenCalled();
      }

      clickTab({ id: "MetricsTabApi" });
      clickTab({ id: "MetricsTabFlows" });
      const before = fetchFlowSpy.mock.calls.length;
      latestList().resolve(listResponse());
      const calls = flowCallsFrom({ index: before });
      expect(calls.length).toBe(BUILTIN_IDS.length);
      expect(calls.map((call) => call.flowId).sort()).toEqual(
        [...BUILTIN_IDS].sort(),
      );
    });
  });

  describe("tab-change gate", () => {
    function resolveCatalog(): void {
      catalogDeferreds[catalogDeferreds.length - 1].resolve({
        event_groups: [
          {
            category: "ui",
            events: [
              {
                event_name: "modal_open",
                description: "",
                category: "ui",
                step_allowed: true,
                dims: [],
              },
            ],
          },
        ],
        api_endpoints: [],
      });
    }
    function dirtyDraft(): void {
      resolveCatalog();
      const input = mount().querySelector(
        '[data-field="display_name"]',
      ) as HTMLInputElement;
      input.value = "Changed";
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
    function confirmButton({
      which,
    }: {
      which: "confirm" | "safe";
    }): HTMLButtonElement {
      return mount().querySelector(
        `[data-confirm="${which}"]`,
      ) as HTMLButtonElement;
    }
    function selectedTab(): string | null {
      return byId("MetricsTabApi").getAttribute("aria-selected");
    }
    async function flush(): Promise<void> {
      for (let tick = 0; tick < 5; tick++) {
        await Promise.resolve();
      }
    }
    function keydown({ key }: { key: string }): KeyboardEvent {
      const event = new KeyboardEvent("keydown", {
        key,
        bubbles: true,
        cancelable: true,
      });
      byId("MetricsTabFlows").dispatchEvent(event);
      return event;
    }

    it("a dirty draft prompts first and moves nothing until answered", async () => {
      openFlowsWithList();
      openBuilder();
      dirtyDraft();
      byId("MetricsTabApi").focus();
      clickTab({ id: "MetricsTabApi" });
      await flush();
      expect(confirmButton({ which: "safe" })).not.toBeNull();
      expect(selectedTab()).toBe("false");
      expect(byId("MetricsTabFlows").getAttribute("aria-selected")).toBe(
        "true",
      );
      expect(byId("MetricsPanelFlows").hidden).toBe(false);
    });

    it("decline keeps the tab, the builder and returns focus to the origin tab", async () => {
      openFlowsWithList();
      openBuilder();
      dirtyDraft();
      clickTab({ id: "MetricsTabApi" });
      await flush();
      confirmButton({ which: "safe" }).click();
      await flush();
      expect(selectedTab()).toBe("false");
      expect(mount().hidden).toBe(false);
      expect(document.activeElement).toBe(byId("MetricsTabApi"));
    });

    it("accept switches the tab, closes the builder and the grid returns on Flows", async () => {
      openFlowsWithList();
      openBuilder();
      dirtyDraft();
      clickTab({ id: "MetricsTabApi" });
      await flush();
      confirmButton({ which: "confirm" }).click();
      await flush();
      expect(selectedTab()).toBe("true");
      expect(mount().hidden).toBe(true);
      clickTab({ id: "MetricsTabFlows" });
      expect(grid().hidden).toBe(false);
    });

    it("accept with held ids issues no request away from Flows and loads all on return", async () => {
      openWithHeldFanOut();
      dirtyDraft();
      const before = fetchFlowSpy.mock.calls.length;
      clickTab({ id: "MetricsTabApi" });
      await flush();
      confirmButton({ which: "confirm" }).click();
      await flush();
      expect(fetchFlowSpy.mock.calls.length).toBe(before);
      clickTab({ id: "MetricsTabFlows" });
      latestList().resolve(listResponse());
      const calls = flowCallsFrom({ index: before });
      expect(calls.map((call) => call.flowId).sort()).toEqual(
        [...BUILTIN_IDS].sort(),
      );
    });

    it("accept with one load in flight plus held ids: the aborted load is re-issued on return, held ids do not drain", async () => {
      openFlowsWithList({ settle: false });
      const inFlight = flowDeferreds.filter((entry) => !entry.isSettled());
      expect(inFlight.length).toBeGreaterThan(0);
      openBuilder();
      pollTick();
      latestList().resolve(listResponse());
      dirtyDraft();
      const before = fetchFlowSpy.mock.calls.length;
      clickTab({ id: "MetricsTabApi" });
      await flush();
      confirmButton({ which: "confirm" }).click();
      await flush();
      for (const entry of inFlight) {
        expect(entry.abort).toHaveBeenCalled();
      }
      inFlight[0].resolve();
      expect(fetchFlowSpy.mock.calls.length).toBe(before);
      clickTab({ id: "MetricsTabFlows" });
      latestList().resolve(listResponse());
      const calls = flowCallsFrom({ index: before });
      expect(calls.map((call) => call.flowId).sort()).toEqual(
        [...BUILTIN_IDS].sort(),
      );
    });

    it("a clean draft switches with no prompt", async () => {
      openFlowsWithList();
      openBuilder();
      clickTab({ id: "MetricsTabApi" });
      await flush();
      expect(mount().querySelector("[data-confirm]")).toBeNull();
      expect(selectedTab()).toBe("true");
      expect(mount().hidden).toBe(true);
    });

    it("a window change with a dirty draft keeps the draft and shows no prompt", async () => {
      openFlowsWithList();
      openBuilder();
      dirtyDraft();
      const otherWindow = document.querySelector(
        ".MetricsWindowButton:not([aria-pressed='true'])",
      ) as HTMLElement;
      expect(otherWindow).not.toBeNull();
      otherWindow.click();
      await flush();
      expect(mount().querySelector("[data-confirm]")).toBeNull();
      expect(mount().hidden).toBe(false);
      expect(
        (
          mount().querySelector(
            '[data-field="display_name"]',
          ) as HTMLInputElement
        ).value,
      ).toBe("Changed");
    });

    it.each(["ArrowLeft", "ArrowRight", "Home", "End"])(
      "keyboard: %s with a dirty draft prompts and does not move selection or focus",
      async (key) => {
        openFlowsWithList();
        openBuilder();
        dirtyDraft();
        byId("MetricsTabFlows").focus();
        const event = keydown({ key });
        expect(event.defaultPrevented).toBe(true);
        expect(selectedTab()).toBe("false");
        await flush();
        expect(confirmButton({ which: "safe" })).not.toBeNull();
        expect(selectedTab()).toBe("false");
        expect(byId("MetricsTabFlows").getAttribute("aria-selected")).toBe(
          "true",
        );
        expect(mount().hidden).toBe(false);
      },
    );

    it("a tab change during a Save does nothing and keeps the form", async () => {
      openFlowsWithList({ customs: ["custom_1"] });
      const saveDeferred = makeDeferred({ key: "save" });
      vi.mocked(updateMetricFlow).mockReturnValue(saveDeferred.xhr as never);
      _openFlowBuilderForTests({
        mode: "edit",
        entry: {
          id: "custom_1",
          display_name: "My flow",
          is_builtin: false,
          definition: {
            steps: [
              { stream: "ui", label: "One", event_name: "modal_open" },
              { stream: "ui", label: "Two", event_name: "modal_open" },
            ],
          },
          errors: {},
          first_invalid: null,
        } as never,
      });
      dirtyDraft();
      (mount().querySelector("form") as HTMLFormElement).requestSubmit();
      expect(updateMetricFlow).toHaveBeenCalled();
      clickTab({ id: "MetricsTabApi" });
      await flush();
      expect(selectedTab()).toBe("false");
      expect(mount().hidden).toBe(false);
      expect(mount().querySelector("[data-confirm]")).toBeNull();
      expect(
        (
          mount().querySelector(
            '[data-field="display_name"]',
          ) as HTMLInputElement
        ).value,
      ).toBe("Changed");
    });

    it("keyboard: decline refocuses the originating tab; accept lands on the target tab", async () => {
      openFlowsWithList();
      openBuilder();
      dirtyDraft();
      byId("MetricsTabFlows").focus();
      keydown({ key: "Home" });
      await flush();
      confirmButton({ which: "safe" }).click();
      await flush();
      expect(document.activeElement).toBe(byId("MetricsTabFlows"));
      expect(mount().hidden).toBe(false);

      keydown({ key: "Home" });
      await flush();
      confirmButton({ which: "confirm" }).click();
      await flush();
      expect(mount().hidden).toBe(true);
      expect(byId("MetricsTabFlows").getAttribute("aria-selected")).toBe(
        "false",
      );
    });

    it("a tab request while the gate's own prompt is open focuses its safe button and changes nothing else", async () => {
      openFlowsWithList();
      openBuilder();
      dirtyDraft();
      clickTab({ id: "MetricsTabApi" });
      await flush();
      clickTab({ id: "MetricsTabApi" });
      await flush();
      expect(document.activeElement).toBe(confirmButton({ which: "safe" }));
      expect(selectedTab()).toBe("false");
      expect(mount().querySelectorAll("[data-confirm='safe']")).toHaveLength(1);
    });

    it("a tab request while a Delete confirm is open focuses its safe button and changes nothing else", async () => {
      openFlowsWithList({ customs: ["custom_1"] });
      _openFlowBuilderForTests({
        mode: "edit",
        entry: {
          id: "custom_1",
          display_name: "My flow",
          is_builtin: false,
          definition: {
            steps: [{ stream: "ui", label: "One", event_name: "modal_open" }],
          },
          errors: {},
          first_invalid: null,
        } as never,
      });
      resolveCatalog();
      (mount().querySelector('[data-action="delete"]') as HTMLElement).click();
      expect(confirmButton({ which: "safe" })).not.toBeNull();
      clickTab({ id: "MetricsTabApi" });
      await flush();
      expect(document.activeElement).toBe(confirmButton({ which: "safe" }));
      expect(selectedTab()).toBe("false");
      expect(mount().hidden).toBe(false);
    });

    it("a request whose target is the active tab bypasses the gate", async () => {
      openFlowsWithList();
      openBuilder();
      dirtyDraft();
      clickTab({ id: "MetricsTabFlows" });
      await flush();
      expect(mount().querySelector("[data-confirm]")).toBeNull();
      expect(mount().hidden).toBe(false);
    });
  });

  describe("list load in flight at close", () => {
    it.each(["cancel", "missing"] as const)(
      "'%s' hands the displayed busy back; it clears when the fan-out finishes",
      (reason) => {
        openFlowsWithList();
        openBuilder();
        pollTick();
        const load = latestList();
        expect(panelBusy()).toBe(false);
        _closeFlowBuilderForTests({ reason });
        expect(panelBusy()).toBe(true);

        load.resolve(listResponse());
        expect(panelBusy()).toBe(true);
        settleAllFlows();
        expect(panelBusy()).toBe(false);
      },
    );
  });

  it("a grid delete settling while paused aborts a load and hands the fan-out to the takeover refresh", () => {
    openFlowsWithList({ customs: [CUSTOM_ONE] });
    (
      card({ id: CUSTOM_ONE })?.querySelector(
        "[data-flow-delete]",
      ) as HTMLElement
    ).click();
    (
      card({ id: CUSTOM_ONE })?.querySelector(
        "[data-flow-confirm-delete]",
      ) as HTMLElement
    ).click();
    openBuilder();
    // The deleting phase is kept until its DELETE settles.
    expect(grid().querySelector("[data-flow-confirm]")).not.toBeNull();
    pollTick();
    const load = latestList();
    const before = fetchFlowSpy.mock.calls.length;
    const heading = byId("MetricsFlowsHeading");
    const focusedBefore = document.activeElement;

    deleteDeferreds[deleteDeferreds.length - 1].resolve({});
    expect(document.activeElement).not.toBe(heading);
    expect(document.activeElement).toBe(focusedBefore);
    expect(load.isSettled()).toBe(true);
    expect(panelBusy()).toBe(false);
    const refresh = latestList();
    expect(refresh).not.toBe(load);

    refresh.resolve(listResponse());
    expect(panelBusy()).toBe(false);
    expect(fetchFlowSpy.mock.calls.length).toBe(before);

    _closeFlowBuilderForTests({ reason: "cancel" });
    expect(panelBusy()).toBe(true);
    expect(flowCallsFrom({ index: before }).length).toBe(BUILTIN_IDS.length);
    settleAllFlows();
    expect(panelBusy()).toBe(false);
    expect(loadedText()).not.toBe("");
  });

  describe("Refresh while paused", () => {
    it("is aria-disabled, focusable, described by the visible hint and ignores clicks", () => {
      openFlowsWithList();
      openBuilder();
      expect(refreshButton().getAttribute("aria-disabled")).toBe("true");
      expect(refreshButton().hasAttribute("data-builder-paused")).toBe(true);
      expect(refreshButton().getAttribute("aria-describedby")).toBe(
        "MetricsRefreshPausedHint",
      );
      expect(refreshButton().hasAttribute("disabled")).toBe(false);
      expect(hint().hidden).toBe(false);

      const summaryCalls = fetchSummarySpy.mock.calls.length;
      refreshButton().click();
      expect(fetchSummarySpy.mock.calls.length).toBe(summaryCalls);
    });

    it("stays disabled when a request settles during the pause", () => {
      openFlowsWithList();
      openBuilder();
      const before = fetchSummarySpy.mock.calls.length;
      pollTick();
      expect(fetchSummarySpy.mock.calls.length).toBeGreaterThan(before);
      expect(refreshButton().getAttribute("aria-disabled")).toBe("true");
    });

    it("positive control: a click on the enabled button refreshes", () => {
      openFlowsWithList();
      openBuilder();
      _closeFlowBuilderForTests({ reason: "saved" });
      const before = fetchSummarySpy.mock.calls.length;
      refreshButton().click();
      expect(fetchSummarySpy.mock.calls.length).toBeGreaterThan(before);
    });

    it.each(["cancel", "saved", "deleted", "missing", "tab-accept"] as const)(
      "is enabled with the hint hidden after '%s'",
      (reason) => {
        openFlowsWithList();
        openBuilder();
        _closeFlowBuilderForTests({ reason });
        expect(refreshButton().hasAttribute("data-builder-paused")).toBe(false);
        expect(refreshButton().getAttribute("aria-disabled")).not.toBe("true");
        expect(refreshButton().hasAttribute("aria-describedby")).toBe(false);
        expect(hint().hidden).toBe(true);
      },
    );
  });

  describe("open and close from the grid (Step 8)", () => {
    const CUSTOM_NEW = "custom_9";
    const CUSTOM_STEPS = [
      { stream: "ui", label: "One", event_name: "modal_open" },
      { stream: "ui", label: "Two", event_name: "modal_open" },
    ];

    function steppedList({ customs = [] }: { customs?: string[] } = {}) {
      const base = listResponse({ customs });
      return {
        flows: base.flows.map((entry) =>
          entry.is_builtin
            ? entry
            : { ...entry, definition: { steps: CUSTOM_STEPS } },
        ),
      };
    }
    function openWithCustoms({
      customs = [CUSTOM_ONE],
      settle = true,
    }: { customs?: string[]; settle?: boolean } = {}): void {
      initMetricsDashboard();
      clickTab({ id: "MetricsTabFlows" });
      latestList().resolve(steppedList({ customs }));
      if (settle) {
        settleAllFlows();
      }
    }
    function newButton(): HTMLElement {
      return byId("MetricsFlowNewBtn");
    }
    function editButton({ id }: { id: string }): HTMLElement {
      return card({ id })?.querySelector("[data-flow-edit]") as HTMLElement;
    }
    function resolveCatalog(): void {
      catalogDeferreds[catalogDeferreds.length - 1].resolve({
        event_groups: [
          {
            category: "ui",
            events: [
              {
                event_name: "modal_open",
                description: "",
                category: "ui",
                step_allowed: true,
                dims: [],
              },
            ],
          },
        ],
        api_endpoints: [],
      });
    }
    function announcement(): string {
      return byId("MetricsFlowsActionAnnouncement").textContent as string;
    }
    function savedBody({ id, name }: { id: string; name: string }) {
      return {
        id,
        display_name: name,
        is_builtin: false,
        definition: { steps: CUSTOM_STEPS },
        errors: {},
        first_invalid: null,
      };
    }
    function failWith({
      deferred,
      status,
      body,
    }: {
      deferred: Deferred;
      status: number;
      body: unknown;
    }): void {
      (deferred.xhr as unknown as { responseJSON: unknown }).responseJSON =
        body;
      deferred.reject({ status });
    }
    // Edit the flow from its card, load the catalog and submit a clean form.
    function saveEdit({ id }: { id: string }): Deferred {
      const saveDeferred = makeDeferred({ key: "save" });
      vi.mocked(updateMetricFlow).mockReturnValue(saveDeferred.xhr as never);
      editButton({ id }).click();
      resolveCatalog();
      (mount().querySelector("form") as HTMLFormElement).requestSubmit();
      return saveDeferred;
    }
    function fillCreateAndSubmit(): Deferred {
      const saveDeferred = makeDeferred({ key: "create" });
      vi.mocked(createMetricFlow).mockReturnValue(saveDeferred.xhr as never);
      resolveCatalog();
      const name = mount().querySelector(
        '[data-field="display_name"]',
      ) as HTMLInputElement;
      name.value = "Funnel";
      name.dispatchEvent(new Event("input", { bubbles: true }));
      for (const row of mount().querySelectorAll(".flow-builder-step")) {
        const label = row.querySelector('[data-field="label"]') as HTMLElement;
        (label as HTMLInputElement).value = "Label";
        label.dispatchEvent(new Event("input", { bubbles: true }));
        const select = row.querySelector(
          '[data-field="event_name"]',
        ) as HTMLSelectElement;
        select.value = "modal_open";
        select.dispatchEvent(new Event("change", { bubbles: true }));
      }
      (mount().querySelector("form") as HTMLFormElement).requestSubmit();
      return saveDeferred;
    }
    async function flush(): Promise<void> {
      await vi.advanceTimersByTimeAsync(0);
    }
    // Resolve every started /flow except one id, so that id's request starts.
    function settleAllExcept({ id }: { id: string }): void {
      for (let index = 0; index < flowDeferreds.length; index++) {
        const entry = flowDeferreds[index];
        if (entry.key !== id && !entry.isSettled()) entry.resolve();
      }
    }

    it("+ New flow opens the create builder and Cancel returns focus to it", async () => {
      openWithCustoms();
      newButton().click();
      expect(mount().hidden).toBe(false);
      expect(grid().hidden).toBe(true);
      resolveCatalog();
      (mount().querySelector('[data-action="cancel"]') as HTMLElement).click();
      await flush();
      expect(mount().hidden).toBe(true);
      expect(document.activeElement).toBe(newButton());
    });

    it("Edit opens the builder for that flow and Cancel focuses the re-resolved Edit button", async () => {
      openWithCustoms();
      const original = editButton({ id: CUSTOM_ONE });
      original.focus();
      original.click();
      expect(mount().hidden).toBe(false);
      resolveCatalog();
      expect(
        (
          mount().querySelector(
            '[data-field="display_name"]',
          ) as HTMLInputElement
        ).value,
      ).toBe("Name of custom_1");
      (mount().querySelector('[data-action="cancel"]') as HTMLElement).click();
      await flush();
      expect(mount().hidden).toBe(true);
      const replaced = editButton({ id: CUSTOM_ONE });
      expect(document.activeElement).toBe(replaced);
    });

    it("an Edit whose id left the list opens nothing and refreshes the list", () => {
      openWithCustoms();
      // A synthetic card the list no longer knows; no render may run between
      // the append and the click, or the node would be dropped.
      const ghost = document.createElement("section");
      ghost.className = "flow-card";
      ghost.dataset.flowId = "custom_gone";
      ghost.innerHTML = "<button type='button' data-flow-edit></button>";
      grid().append(ghost);
      const listCalls = fetchMetricFlowsSpy.mock.calls.length;
      (ghost.querySelector("[data-flow-edit]") as HTMLElement).click();
      expect(mount().hidden).toBe(true);
      expect(fetchMetricFlowsSpy.mock.calls.length).toBe(listCalls + 1);
    });

    it("+ New flow is aria-disabled with the reason at the cap and opens nothing", () => {
      const customs = Array.from(
        { length: 20 },
        (_, index) => `custom_${index}`,
      );
      openWithCustoms({ customs, settle: false });
      expect(newButton().getAttribute("aria-disabled")).toBe("true");
      const reasonId = newButton().getAttribute("aria-describedby") as string;
      expect(byId(reasonId).hidden).toBe(false);
      expect(byId(reasonId).textContent).toContain("20");
      newButton().click();
      expect(mount().hidden).toBe(true);
    });

    it("+ New flow stays enabled while the list is loading", () => {
      initMetricsDashboard();
      clickTab({ id: "MetricsTabFlows" });
      expect(newButton().hasAttribute("aria-disabled")).toBe(false);
      newButton().click();
      expect(mount().hidden).toBe(false);
    });

    // Leave only the custom card's /flow pending and return that request.
    function pendingCustomFlow(): Deferred {
      openWithCustoms({ settle: false });
      settleAllExcept({ id: CUSTOM_ONE });
      return flowDeferreds.find(
        (entry) => entry.key === CUSTOM_ONE && !entry.isSettled(),
      ) as Deferred;
    }

    const FOCUS_OUTCOMES: Array<{
      name: string;
      settle: (deferred: Deferred) => void;
    }> = [
      { name: "resolves", settle: (deferred) => deferred.resolve() },
      {
        name: "fails",
        settle: (deferred) => deferred.reject({ status: 500 }),
      },
      {
        name: "is invalid",
        settle: (deferred) =>
          failWith({
            deferred,
            status: 422,
            body: {
              error: "flow_invalid",
              invalid: { step_index: 1, field: "event_name", reason: "Bad." },
            },
          }),
      },
    ];

    it.each(FOCUS_OUTCOMES)(
      "an Edit button on a loading card keeps focus when the load $name",
      ({ settle }) => {
        const pending = pendingCustomFlow();
        expect(card({ id: CUSTOM_ONE })?.dataset.flowState).toBe("loading");
        editButton({ id: CUSTOM_ONE }).focus();
        settle(pending);
        expect(card({ id: CUSTOM_ONE })?.dataset.flowState).not.toBe("loading");
        expect(document.activeElement).toBe(editButton({ id: CUSTOM_ONE }));
      },
    );

    it("focus falls back to the card section when the card is in delete-confirm at swap time", () => {
      const pending = pendingCustomFlow();
      (
        card({ id: CUSTOM_ONE })?.querySelector(
          "[data-flow-delete]",
        ) as HTMLElement
      ).click();
      expect(
        card({ id: CUSTOM_ONE })?.querySelector("[data-flow-confirm]"),
      ).not.toBeNull();
      // Focus sits on a control the confirm state does not render (an Edit
      // button), so the re-render cannot refocus the same control.
      const stale = document.createElement("button");
      stale.setAttribute("data-flow-edit", "");
      card({ id: CUSTOM_ONE })?.append(stale);
      stale.focus();
      pending.resolve();
      const swapped = card({ id: CUSTOM_ONE }) as HTMLElement;
      expect(swapped.dataset.flowState).toBe("response");
      expect(swapped.querySelector("[data-flow-confirm]")).not.toBeNull();
      expect(document.activeElement).toBe(swapped);
    });

    it("Edit shows on a loading card and an error card, never on a built-in", () => {
      const pending = pendingCustomFlow();
      expect(card({ id: CUSTOM_ONE })?.dataset.flowState).toBe("loading");
      expect(editButton({ id: CUSTOM_ONE })).not.toBeNull();
      pending.reject({ status: 500 });
      expect(card({ id: CUSTOM_ONE })?.dataset.flowState).toBe("error");
      expect(editButton({ id: CUSTOM_ONE })).not.toBeNull();
      expect(editButton({ id: BUILTIN_IDS[0] })).toBeNull();
    });

    it("a click on a locked Edit opens nothing", () => {
      const other = "custom_2";
      openWithCustoms({ customs: [CUSTOM_ONE, other] });
      (
        card({ id: CUSTOM_ONE })?.querySelector(
          "[data-flow-delete]",
        ) as HTMLElement
      ).click();
      (
        card({ id: CUSTOM_ONE })?.querySelector(
          "[data-flow-confirm-delete]",
        ) as HTMLElement
      ).click();
      // A delete in flight locks every other card's controls.
      expect(editButton({ id: other }).getAttribute("aria-disabled")).toBe(
        "true",
      );
      editButton({ id: other }).click();
      expect(mount().hidden).toBe(true);
    });

    it("+ New flow re-enables when the list drops below the cap", () => {
      const customs = Array.from(
        { length: 20 },
        (_, index) => `custom_${index}`,
      );
      openWithCustoms({ customs });
      const reasonId = newButton().getAttribute("aria-describedby") as string;
      expect(newButton().getAttribute("aria-disabled")).toBe("true");
      pollTick();
      latestList().resolve(steppedList({ customs: customs.slice(1) }));
      expect(newButton().hasAttribute("aria-disabled")).toBe(false);
      expect(newButton().hasAttribute("aria-describedby")).toBe(false);
      expect(byId(reasonId).hidden).toBe(true);
      expect(byId(reasonId).textContent).toBe("");
    });

    it.each(["missing", "deleted"] as const)(
      "a %s close never issues the held id's old-definition request",
      (reason) => {
        openWithCustoms();
        editButton({ id: CUSTOM_ONE }).click();
        pollTick();
        latestList().resolve(steppedList({ customs: [CUSTOM_ONE] }));
        const before = fetchFlowSpy.mock.calls.length;
        if (reason === "missing") {
          const saveDeferred = saveEditFromOpen();
          failWith({
            deferred: saveDeferred,
            status: 404,
            body: { errorCode: 5 },
          });
        } else {
          resolveCatalog();
          (
            mount().querySelector('[data-action="delete"]') as HTMLElement
          ).click();
          (
            mount().querySelector('[data-confirm="confirm"]') as HTMLElement
          ).click();
          deleteDeferreds[deleteDeferreds.length - 1].resolve({});
        }
        expect(mount().hidden).toBe(true);
        settleAllFlows();
        settleAllFlows();
        const calls = flowCallsFrom({ index: before });
        expect(calls.length).toBeGreaterThan(0);
        expect(calls.filter((call) => call.flowId === CUSTOM_ONE)).toHaveLength(
          0,
        );
      },
    );

    it("a save shows the new definition: held id never issued, one fresh /flow, one list refresh, focus on Edit", () => {
      openWithCustoms();
      editButton({ id: CUSTOM_ONE }).click();
      pollTick();
      latestList().resolve(steppedList({ customs: [CUSTOM_ONE] }));
      const saveDeferred = saveEditFromOpen();
      const before = fetchFlowSpy.mock.calls.length;
      const listCalls = fetchMetricFlowsSpy.mock.calls.length;
      saveDeferred.resolve(savedBody({ id: CUSTOM_ONE, name: "Renamed" }));
      expect(mount().hidden).toBe(true);
      // The four built-ins fill the concurrency slots; the saved id's single
      // fresh load follows once one settles, and the held old one never runs.
      expect(
        flowCallsFrom({ index: before }).map((call) => call.flowId),
      ).toEqual(BUILTIN_IDS);
      settleAllFlows();
      const after = flowCallsFrom({ index: before });
      expect(after.filter((call) => call.flowId === CUSTOM_ONE)).toHaveLength(
        1,
      );
      expect(fetchMetricFlowsSpy.mock.calls.length).toBe(listCalls + 1);
      expect(card({ id: CUSTOM_ONE })?.textContent).toContain("Renamed");
      expect(document.activeElement).toBe(editButton({ id: CUSTOM_ONE }));
      // The announcement is set on a zero-delay timer; fire only that.
      vi.advanceTimersByTime(0);
      expect(announcement()).toBe("Flow “Renamed” saved.");
    });

    it("an in-flight /flow for the edited id when Save lands cannot repopulate the cache", () => {
      openWithCustoms({ settle: false });
      settleAllExcept({ id: CUSTOM_ONE });
      const stale = flowDeferreds.find(
        (entry) => entry.key === CUSTOM_ONE,
      ) as Deferred;
      const saveDeferred = saveEdit({ id: CUSTOM_ONE });
      saveDeferred.resolve(savedBody({ id: CUSTOM_ONE, name: "Renamed" }));
      expect(stale.abort).toHaveBeenCalled();
      stale.resolve();
      expect(card({ id: CUSTOM_ONE })?.dataset.flowState).toBe("loading");
    });

    it("a list response in flight at Save time cannot remove or revert the saved flow", () => {
      openWithCustoms({ customs: [] });
      newButton().click();
      pollTick();
      const stale = latestList();
      const saveDeferred = fillCreateAndSubmit();
      saveDeferred.resolve(savedBody({ id: CUSTOM_NEW, name: "Funnel" }));
      expect(stale.isSettled()).toBe(true);
      stale.resolve(steppedList({ customs: [] }));
      expect(card({ id: CUSTOM_NEW })).toBeDefined();
      expect(card({ id: CUSTOM_NEW })?.textContent).toContain("Funnel");
    });

    it("a create saved while the list is null keeps the four built-ins and focuses the heading until the refresh adds the card", () => {
      initMetricsDashboard();
      clickTab({ id: "MetricsTabFlows" });
      newButton().click();
      const saveDeferred = fillCreateAndSubmit();
      saveDeferred.resolve(savedBody({ id: CUSTOM_NEW, name: "Funnel" }));
      expect(cards()).toHaveLength(BUILTIN_IDS.length);
      expect(card({ id: CUSTOM_NEW })).toBeUndefined();
      expect(document.activeElement).toBe(byId("MetricsFlowsHeading"));
      latestList().resolve(steppedList({ customs: [CUSTOM_NEW] }));
      expect(card({ id: CUSTOM_NEW })).toBeDefined();
    });

    it("after a create, focus goes to the new card's Edit button", () => {
      openWithCustoms({ customs: [] });
      newButton().click();
      const saveDeferred = fillCreateAndSubmit();
      saveDeferred.resolve(savedBody({ id: CUSTOM_NEW, name: "Funnel" }));
      expect(document.activeElement).toBe(editButton({ id: CUSTOM_NEW }));
    });

    it("a save with a list load in flight hands the fan-out to a takeover refresh", () => {
      openWithCustoms();
      editButton({ id: CUSTOM_ONE }).click();
      pollTick();
      const load = latestList();
      const saveDeferred = saveEditFromOpen();
      const before = fetchFlowSpy.mock.calls.length;
      saveDeferred.resolve(savedBody({ id: CUSTOM_ONE, name: "Renamed" }));
      expect(load.isSettled()).toBe(true);
      expect(panelBusy()).toBe(true);
      latestList().resolve(steppedList({ customs: [CUSTOM_ONE] }));
      expect(panelBusy()).toBe(true);
      settleAllFlows();
      settleAllFlows();
      // The takeover restarts the fan-out (aborting the saved id's catch-up
      // request), so every listed id is requested for the latest window.
      const calls = flowCallsFrom({ index: before });
      expect([...new Set(calls.map((call) => call.flowId))].sort()).toEqual(
        [...BUILTIN_IDS, CUSTOM_ONE].sort(),
      );
      expect(panelBusy()).toBe(false);
    });

    function saveEditFromOpen(): Deferred {
      const saveDeferred = makeDeferred({ key: "save" });
      vi.mocked(updateMetricFlow).mockReturnValue(saveDeferred.xhr as never);
      resolveCatalog();
      (mount().querySelector("form") as HTMLFormElement).requestSubmit();
      return saveDeferred;
    }

    it("an update 404 returns to the grid with the notice and a refreshed list", () => {
      openWithCustoms();
      const saveDeferred = saveEdit({ id: CUSTOM_ONE });
      const listCalls = fetchMetricFlowsSpy.mock.calls.length;
      failWith({ deferred: saveDeferred, status: 404, body: { errorCode: 5 } });
      expect(mount().hidden).toBe(true);
      expect(card({ id: CUSTOM_ONE })).toBeUndefined();
      expect(byId("MetricsFlowsNotice").textContent).toBe(
        "This flow no longer exists.",
      );
      expect(byId("MetricsFlowsNotice").hidden).toBe(false);
      expect(document.activeElement).toBe(byId("MetricsFlowsHeading"));
      expect(fetchMetricFlowsSpy.mock.calls.length).toBe(listCalls + 1);
    });

    it("a builder Delete returns to the grid, focuses + New flow and announces", () => {
      openWithCustoms();
      editButton({ id: CUSTOM_ONE }).click();
      resolveCatalog();
      (mount().querySelector('[data-action="delete"]') as HTMLElement).click();
      const listCalls = fetchMetricFlowsSpy.mock.calls.length;
      (
        mount().querySelector('[data-confirm="confirm"]') as HTMLElement
      ).click();
      deleteDeferreds[deleteDeferreds.length - 1].resolve({});
      vi.advanceTimersByTime(0);
      expect(mount().hidden).toBe(true);
      expect(card({ id: CUSTOM_ONE })).toBeUndefined();
      expect(document.activeElement).toBe(newButton());
      expect(announcement()).toBe("Flow “Name of custom_1” deleted.");
      expect(fetchMetricFlowsSpy.mock.calls.length).toBe(listCalls + 1);
    });

    it("a builder Delete with a list load in flight hands the fan-out to a takeover refresh", () => {
      openWithCustoms();
      editButton({ id: CUSTOM_ONE }).click();
      resolveCatalog();
      pollTick();
      const load = latestList();
      (mount().querySelector('[data-action="delete"]') as HTMLElement).click();
      (
        mount().querySelector('[data-confirm="confirm"]') as HTMLElement
      ).click();
      const before = fetchFlowSpy.mock.calls.length;
      deleteDeferreds[deleteDeferreds.length - 1].resolve({});
      expect(load.isSettled()).toBe(true);
      expect(panelBusy()).toBe(true);
      latestList().resolve(steppedList({ customs: [] }));
      expect(
        flowCallsFrom({ index: before }).map((call) => call.flowId),
      ).toEqual(expect.arrayContaining(BUILTIN_IDS));
      settleAllFlows();
      expect(panelBusy()).toBe(false);
    });

    it("a builder Delete 404 keeps the builder open and refreshes the list once, silently", () => {
      openWithCustoms();
      editButton({ id: CUSTOM_ONE }).click();
      resolveCatalog();
      (mount().querySelector('[data-action="delete"]') as HTMLElement).click();
      (
        mount().querySelector('[data-confirm="confirm"]') as HTMLElement
      ).click();
      const listCalls = fetchMetricFlowsSpy.mock.calls.length;
      failWith({
        deferred: deleteDeferreds[deleteDeferreds.length - 1],
        status: 404,
        body: { errorCode: 5 },
      });
      expect(mount().hidden).toBe(false);
      expect(mount().textContent).toContain("was already deleted");
      expect(fetchMetricFlowsSpy.mock.calls.length).toBe(listCalls + 1);
      expect(byId("MetricsFlowsNotice").hidden).toBe(true);
      expect(announcement()).toBe("");
    });

    it("a grid delete settling after an open neither focuses nor shows a notice", () => {
      openWithCustoms();
      (
        card({ id: CUSTOM_ONE })?.querySelector(
          "[data-flow-delete]",
        ) as HTMLElement
      ).click();
      (
        card({ id: CUSTOM_ONE })?.querySelector(
          "[data-flow-confirm-delete]",
        ) as HTMLElement
      ).click();
      newButton().click();
      const focusedBefore = document.activeElement;
      failWith({
        deferred: deleteDeferreds[deleteDeferreds.length - 1],
        status: 404,
        body: {},
      });
      expect(document.activeElement).toBe(focusedBefore);
      expect(document.activeElement).not.toBe(newButton());
      expect(byId("MetricsFlowsNotice").hidden).toBe(true);
      vi.advanceTimersByTime(0);
      expect(announcement()).toBe("");
    });

    it("the needs-attention hint names the restored Edit control", () => {
      initMetricsDashboard();
      clickTab({ id: "MetricsTabFlows" });
      const list = steppedList({ customs: [CUSTOM_ONE] });
      list.flows = list.flows.map((entry) =>
        entry.id === CUSTOM_ONE
          ? {
              ...entry,
              errors: { "1": ["bad"] },
              first_invalid: {
                step_index: 1,
                field: "event_name",
                reason: "Unknown event.",
              },
            }
          : entry,
      );
      latestList().resolve(list);
      const invalid = card({ id: CUSTOM_ONE }) as HTMLElement;
      expect(invalid.dataset.flowState).toBe("invalid");
      expect(invalid.textContent).toContain("Edit the flow to fix it");
      expect(invalid.querySelector("[data-flow-edit]")).not.toBeNull();
    });
  });
});
