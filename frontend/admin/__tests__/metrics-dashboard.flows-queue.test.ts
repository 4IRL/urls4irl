/**
 * Flows-tab load queue wiring in the admin metrics dashboard controller.
 *
 * Every `fetchFlow` stub here is DEFERRED (manually settled by the test): the
 * queue's `isCurrent` guard would drop a `done`/`fail` fired synchronously
 * inside `issue()`.
 *
 * `vi.useFakeTimers()` is installed before `initMetricsDashboard()` so the
 * initial `fetchAll()` and polling interval stay under timer control.
 */

const {
  fetchSummarySpy,
  fetchTopEventsSpy,
  fetchGroupedTimeseriesSpy,
  fetchGaugesTimeseriesSpy,
  fetchFlowSpy,
  renderSummarySpy,
  renderTopTableSpy,
  renderFlowGridSpy,
  flowIdsHolder,
} = vi.hoisted(() => ({
  fetchSummarySpy: vi.fn(),
  fetchTopEventsSpy: vi.fn(),
  fetchGroupedTimeseriesSpy: vi.fn(),
  fetchGaugesTimeseriesSpy: vi.fn(),
  fetchFlowSpy: vi.fn(),
  renderSummarySpy: vi.fn(),
  renderTopTableSpy: vi.fn(),
  renderFlowGridSpy: vi.fn(),
  flowIdsHolder: { ids: null as Record<string, string> | null },
}));

vi.mock("../metrics-query-client.js", () => ({
  fetchSummary: fetchSummarySpy,
  fetchTopEvents: fetchTopEventsSpy,
  fetchTimeseries: vi.fn(),
  fetchGroupedTimeseries: fetchGroupedTimeseriesSpy,
  fetchGaugesTimeseries: fetchGaugesTimeseriesSpy,
  fetchFlow: fetchFlowSpy,
}));

vi.mock("../render-summary.js", () => ({
  renderSummary: renderSummarySpy,
}));

vi.mock("../render-top-table.js", () => ({
  renderTopTable: renderTopTableSpy,
}));

vi.mock("../flow-card.js", () => ({
  renderFlowGrid: renderFlowGridSpy,
}));

vi.mock("../../types/metrics-flows.js", async (importOriginal) => {
  const actual =
    await importOriginal<typeof import("../../types/metrics-flows.js")>();
  return {
    ...actual,
    get FLOW_IDS() {
      return flowIdsHolder.ids ?? actual.FLOW_IDS;
    },
    // Ids injected through `flowIdsHolder` have no real metadata entry.
    FLOW_METADATA: new Proxy(actual.FLOW_METADATA as Record<string, unknown>, {
      get: (target, key: string) => target[key] ?? { displayName: key },
    }),
  };
});

import { FLOW_IDS } from "../../types/metrics-flows.js";
import {
  _dropFlowIdForTests,
  _resetMetricsDashboardForTests,
  initMetricsDashboard,
} from "../metrics-dashboard.js";

const DASHBOARD_HTML = `
  <main id="MetricsDashboard" aria-busy="false">
    <button id="MetricsRefreshNowBtn" type="button"></button>
    <button class="MetricsWindowButton" data-window="day" aria-pressed="true"></button>
    <button class="MetricsWindowButton" data-window="week" aria-pressed="false"></button>
    <button class="MetricsWindowButton" data-window="month" aria-pressed="false"></button>
    <button class="MetricsWindowButton" data-window="year" aria-pressed="false"></button>
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
      <button id="MetricsTabApi"            role="tab" aria-selected="true"  aria-controls="MetricsPanelApi"            tabindex="0"  data-tab="api"></button>
      <button id="MetricsTabFlows"          role="tab" aria-selected="false" aria-controls="MetricsPanelFlows"          tabindex="-1" data-tab="flows"></button>
    </div>
    <section id="MetricsPanelFlows" role="tabpanel" tabindex="0" hidden>
      <span class="flows-loading-spinner" aria-hidden="true"></span>
      <span id="MetricsPanelFlowsAnnouncement" class="visually-hidden" aria-live="polite"></span>
      <div id="MetricsFlowGrid" class="flow-grid"></div>
    </section>
    <div id="MetricsErrorBanner" class="hidden"></div>
  </main>
`;

const ANNOUNCEMENT_TEXT = "Flow funnels updated.";
const VISIBILITY_THRESHOLD_MS = 5_000;
const POLL_INTERVAL_MS = 60_000;
const ALL_IDS: string[] = Object.values(FLOW_IDS);
const [ID_A, ID_B, ID_C, ID_D] = ALL_IDS;
const VALID_INVALID = {
  step_index: 1,
  field: "event_name",
  reason: "unknown",
};

interface FakeXhr {
  status: number;
  readyState: number;
  responseJSON: unknown;
  _429Handled: boolean;
  done: (callback: (response: unknown) => void) => FakeXhr;
  fail: (callback: (xhr: FakeXhr) => void) => FakeXhr;
  always: (callback: () => void) => FakeXhr;
  abort: ReturnType<typeof vi.fn>;
}

interface Deferred {
  flowId: string;
  xhr: JQuery.jqXHR;
  abort: ReturnType<typeof vi.fn>;
  resolve: (response?: unknown) => void;
  reject: (options: {
    status?: number;
    readyState?: number;
    responseJSON?: unknown;
    handled429?: boolean;
  }) => void;
}

function makeDeferred({ flowId }: { flowId: string }): Deferred {
  const doneCallbacks: Array<(response: unknown) => void> = [];
  const failCallbacks: Array<(xhr: FakeXhr) => void> = [];
  const alwaysCallbacks: Array<() => void> = [];
  const fake: FakeXhr = {
    status: 0,
    readyState: 1,
    responseJSON: undefined,
    _429Handled: false,
    done: (callback) => {
      doneCallbacks.push(callback);
      return fake;
    },
    fail: (callback) => {
      failCallbacks.push(callback);
      return fake;
    },
    always: (callback) => {
      alwaysCallbacks.push(callback);
      return fake;
    },
    // Mirrors jqXHR.abort(): fail then always, synchronously.
    abort: vi.fn(() => {
      fake.status = 0;
      fake.readyState = 0;
      failCallbacks.forEach((callback) => callback(fake));
      alwaysCallbacks.forEach((callback) => callback());
    }),
  };
  return {
    flowId,
    xhr: fake as unknown as JQuery.jqXHR,
    abort: fake.abort,
    resolve: (response = { marker: "response" }) => {
      fake.status = 200;
      fake.readyState = 4;
      doneCallbacks.forEach((callback) => callback(response));
      alwaysCallbacks.forEach((callback) => callback());
    },
    reject: ({
      status = 500,
      readyState = 4,
      responseJSON,
      handled429 = false,
    }) => {
      fake.status = status;
      fake.readyState = readyState;
      fake.responseJSON = responseJSON;
      fake._429Handled = handled429;
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

function setDocumentVisibility(state: "visible" | "hidden"): void {
  Object.defineProperty(document, "visibilityState", {
    value: state,
    configurable: true,
  });
}

describe("metrics-dashboard flows load queue wiring", () => {
  let deferreds: Deferred[] = [];

  beforeEach(() => {
    document.body.innerHTML = DASHBOARD_HTML;
    setDocumentVisibility("visible");
    deferreds = [];

    fetchSummarySpy.mockReset();
    fetchTopEventsSpy.mockReset();
    fetchGroupedTimeseriesSpy.mockReset();
    fetchGaugesTimeseriesSpy.mockReset();
    fetchFlowSpy.mockReset();
    renderSummarySpy.mockReset();
    renderTopTableSpy.mockReset();
    renderFlowGridSpy.mockReset();

    fetchSummarySpy.mockImplementation(() => makeSettlingXhr());
    fetchTopEventsSpy.mockImplementation(() => makeSettlingXhr());
    fetchGroupedTimeseriesSpy.mockImplementation(() => makeSettlingXhr());
    fetchGaugesTimeseriesSpy.mockImplementation(() => makeSettlingXhr());
    fetchFlowSpy.mockImplementation(({ flowId }: { flowId: string }) => {
      const deferred = makeDeferred({ flowId });
      deferreds.push(deferred);
      return deferred.xhr;
    });

    vi.useFakeTimers();
  });

  afterEach(() => {
    _resetMetricsDashboardForTests();
    flowIdsHolder.ids = null;
    vi.useRealTimers();
    document.body.innerHTML = "";
  });

  function flowsPanel(): HTMLElement {
    return document.getElementById("MetricsPanelFlows") as HTMLElement;
  }

  function announcement(): HTMLElement {
    return document.getElementById(
      "MetricsPanelFlowsAnnouncement",
    ) as HTMLElement;
  }

  function banner(): HTMLElement {
    return document.getElementById("MetricsErrorBanner") as HTMLElement;
  }

  function clickTab({ id }: { id: string }): void {
    (document.getElementById(id) as HTMLButtonElement).click();
  }

  function openFlows(): void {
    initMetricsDashboard();
    clickTab({ id: "MetricsTabFlows" });
  }

  function changeWindow({ windowKey }: { windowKey: string }): void {
    (
      document.querySelector(
        `.MetricsWindowButton[data-window="${windowKey}"]`,
      ) as HTMLButtonElement
    ).click();
  }

  function latest({ flowId }: { flowId: string }): Deferred {
    const matches = deferreds.filter((entry) => entry.flowId === flowId);
    return matches[matches.length - 1];
  }

  function lastEntries(): Array<{
    id: string;
    state: { kind: string; invalid?: unknown };
  }> {
    expect(renderFlowGridSpy.mock.calls.length).toBeGreaterThan(0);
    const { calls } = renderFlowGridSpy.mock;
    const lastCall = calls[calls.length - 1] as [
      { entries: Array<{ id: string; state: { kind: string } }> },
    ];
    return lastCall[0].entries;
  }

  function kindOf({ id }: { id: string }): string | undefined {
    return lastEntries().find((entry) => entry.id === id)?.state.kind;
  }

  function bannerShown(): boolean {
    return !banner().classList.contains("hidden");
  }

  it("a window change off the Flows tab aborts in-flight loads silently", () => {
    openFlows();
    const inFlight = [...deferreds];
    clickTab({ id: "MetricsTabApi" });
    announcement().textContent = "";
    renderFlowGridSpy.mockClear();

    changeWindow({ windowKey: "week" });

    inFlight.forEach((entry) => expect(entry.abort).toHaveBeenCalled());
    expect(flowsPanel().hasAttribute("aria-busy")).toBe(false);
    expect(announcement().textContent).toBe("");

    inFlight[0].resolve();
    const sawResponse = renderFlowGridSpy.mock.calls.some((call) =>
      (call[0].entries as Array<{ state: { kind: string } }>).some(
        (entry) => entry.state.kind === "response",
      ),
    );
    expect(sawResponse).toBe(false);
  });

  it.each(["done", "fail", "abort"] as const)(
    "a flow %s settle updates _lastFetchPerf (visibility-return gate)",
    (outcome) => {
      openFlows();
      vi.advanceTimersByTime(VISIBILITY_THRESHOLD_MS * 2);
      const target = deferreds[0];
      if (outcome === "done") {
        target.resolve();
      } else if (outcome === "fail") {
        target.reject({ status: 500 });
      } else {
        target.xhr.abort();
      }
      fetchSummarySpy.mockClear();

      document.dispatchEvent(new Event("visibilitychange"));
      expect(fetchSummarySpy).not.toHaveBeenCalled();

      vi.advanceTimersByTime(VISIBILITY_THRESHOLD_MS + 1_000);
      document.dispatchEvent(new Event("visibilitychange"));
      expect(fetchSummarySpy).toHaveBeenCalledTimes(1);
    },
  );

  it("a handled 429 with no cache and no state yields an error entry and no banner", () => {
    openFlows();
    latest({ flowId: ID_A }).reject({ status: 429, handled429: true });

    expect(kindOf({ id: ID_A })).toBe("error");
    expect(bannerShown()).toBe(false);
  });

  it("a handled 429 over a cached response keeps the response entry", () => {
    openFlows();
    latest({ flowId: ID_A }).resolve();
    changeWindow({ windowKey: "week" });
    latest({ flowId: ID_A }).reject({ status: 429, handled429: true });

    expect(kindOf({ id: ID_A })).toBe("response");
    expect(bannerShown()).toBe(false);
  });

  it("a window change aborts in-flight loads and a late done does not repopulate", () => {
    openFlows();
    const stale = latest({ flowId: ID_A });
    changeWindow({ windowKey: "week" });

    expect(stale.abort).toHaveBeenCalled();
    stale.resolve();
    expect(kindOf({ id: ID_A })).toBe("loading");
  });

  it("Refresh aborts in-flight flow loads", () => {
    openFlows();
    const inFlight = [...deferreds];
    (
      document.getElementById("MetricsRefreshNowBtn") as HTMLButtonElement
    ).removeAttribute("aria-disabled");
    (
      document.getElementById("MetricsRefreshNowBtn") as HTMLButtonElement
    ).click();

    inFlight.forEach((entry) => expect(entry.abort).toHaveBeenCalled());
  });

  it("the 60 s poll aborts in-flight flow loads", () => {
    openFlows();
    const inFlight = [...deferreds];
    vi.advanceTimersByTime(POLL_INTERVAL_MS);

    inFlight.forEach((entry) => expect(entry.abort).toHaveBeenCalled());
  });

  it("_resetMetricsDashboardForTests aborts in-flight flow loads", () => {
    openFlows();
    const inFlight = [...deferreds];
    _resetMetricsDashboardForTests();

    inFlight.forEach((entry) => expect(entry.abort).toHaveBeenCalled());
  });

  it("aria-busy stays true and nothing is announced until every request settles", () => {
    openFlows();
    expect(deferreds).toHaveLength(4);
    deferreds.slice(0, 3).forEach((entry) => entry.resolve());

    expect(flowsPanel().getAttribute("aria-busy")).toBe("true");
    expect(announcement().textContent).toBe("");

    deferreds[3].resolve();
    expect(flowsPanel().hasAttribute("aria-busy")).toBe(false);
    expect(announcement().textContent).toBe(ANNOUNCEMENT_TEXT);
  });

  it("a flow_invalid 422 yields an invalid entry without the banner", () => {
    openFlows();
    const target = latest({ flowId: ID_A });
    target.reject({
      status: 422,
      responseJSON: { error: "flow_invalid", invalid: VALID_INVALID },
    });

    expect(kindOf({ id: ID_A })).toBe("invalid");
    expect(
      lastEntries().find((entry) => entry.id === ID_A)?.state.invalid,
    ).toEqual(VALID_INVALID);
    expect(bannerShown()).toBe(false);
  });

  it("a flow_invalid body on a non-422 status takes the generic error path", () => {
    openFlows();
    latest({ flowId: ID_A }).reject({
      status: 400,
      responseJSON: { error: "flow_invalid", invalid: VALID_INVALID },
    });

    expect(kindOf({ id: ID_A })).toBe("error");
    expect(bannerShown()).toBe(true);
  });

  it("a 422 with no responseJSON takes the generic error path", () => {
    openFlows();
    latest({ flowId: ID_A }).reject({ status: 422 });

    expect(kindOf({ id: ID_A })).toBe("error");
    expect(bannerShown()).toBe(true);
  });

  it("a 422 flow_invalid without an invalid object takes the generic error path", () => {
    openFlows();
    latest({ flowId: ID_A }).reject({
      status: 422,
      responseJSON: { error: "flow_invalid" },
    });

    expect(kindOf({ id: ID_A })).toBe("error");
    expect(bannerShown()).toBe(true);
  });

  it("a failed id renders as error, not loading, once it settles", () => {
    openFlows();
    latest({ flowId: ID_A }).reject({ status: 500 });

    expect(kindOf({ id: ID_A })).toBe("error");
  });

  it("a 500 shows the banner and a cached card stays a response entry", () => {
    openFlows();
    latest({ flowId: ID_A }).resolve();
    changeWindow({ windowKey: "week" });
    latest({ flowId: ID_A }).reject({ status: 500 });

    expect(bannerShown()).toBe(true);
    expect(kindOf({ id: ID_A })).toBe("response");
  });

  it("a 500 after invalid supersedes it; a handled 429 leaves it invalid", () => {
    openFlows();
    latest({ flowId: ID_A }).reject({
      status: 422,
      responseJSON: { error: "flow_invalid", invalid: VALID_INVALID },
    });
    expect(kindOf({ id: ID_A })).toBe("invalid");

    changeWindow({ windowKey: "week" });
    expect(kindOf({ id: ID_A })).toBe("invalid");
    latest({ flowId: ID_A }).reject({ status: 429, handled429: true });
    expect(kindOf({ id: ID_A })).toBe("invalid");

    changeWindow({ windowKey: "month" });
    latest({ flowId: ID_A }).reject({ status: 500 });
    expect(kindOf({ id: ID_A })).toBe("error");
    expect(bannerShown()).toBe(true);
  });

  it("a throwing fetchFlow sets that id to error and the rest still load", () => {
    fetchFlowSpy.mockImplementation(({ flowId }: { flowId: string }) => {
      if (flowId === ID_B) {
        throw new Error("boom");
      }
      const deferred = makeDeferred({ flowId });
      deferreds.push(deferred);
      return deferred.xhr;
    });
    openFlows();

    expect(deferreds).toHaveLength(3);
    expect(kindOf({ id: ID_B })).toBe("error");
    expect(bannerShown()).toBe(false);
    expect(flowsPanel().getAttribute("aria-busy")).toBe("true");

    deferreds.forEach((entry) => entry.resolve());
    expect(flowsPanel().hasAttribute("aria-busy")).toBe(false);
  });

  it("an aborted request (readyState 0) shows no banner and adds no entry", () => {
    openFlows();
    latest({ flowId: ID_A }).reject({ status: 0, readyState: 0 });

    expect(bannerShown()).toBe(false);
    expect(kindOf({ id: ID_A })).toBeUndefined();
  });

  it("_dropFlowIdForTests aborts the in-flight xhr, clears the cache, and a late resolve stays dropped", () => {
    openFlows();
    latest({ flowId: ID_A }).resolve();
    changeWindow({ windowKey: "week" });
    const refetch = latest({ flowId: ID_A });

    _dropFlowIdForTests({ id: ID_A });
    expect(refetch.abort).toHaveBeenCalled();
    expect(kindOf({ id: ID_A })).toBeUndefined();

    refetch.resolve();
    expect(kindOf({ id: ID_A })).toBeUndefined();
  });

  it("_dropFlowIdForTests on an errored id leaves it omitted", () => {
    openFlows();
    latest({ flowId: ID_A }).reject({ status: 500 });
    expect(kindOf({ id: ID_A })).toBe("error");

    _dropFlowIdForTests({ id: ID_A });
    expect(kindOf({ id: ID_A })).toBeUndefined();
  });

  it("a flow_invalid 422 over a cached response yields invalid, not response", () => {
    openFlows();
    latest({ flowId: ID_A }).resolve();
    changeWindow({ windowKey: "week" });
    latest({ flowId: ID_A }).reject({
      status: 422,
      responseJSON: { error: "flow_invalid", invalid: VALID_INVALID },
    });

    expect(kindOf({ id: ID_A })).toBe("invalid");
  });

  it("error then success clears the error state and renders a response", () => {
    openFlows();
    latest({ flowId: ID_A }).reject({ status: 500 });
    expect(kindOf({ id: ID_A })).toBe("error");

    changeWindow({ windowKey: "week" });
    latest({ flowId: ID_A }).resolve();
    // The _flowStates clear in `.done` is masked by precedence (response wins
    // over a stale error), so only the rendered kind is observable here.
    expect(kindOf({ id: ID_A })).toBe("response");
  });

  it("entry precedence: response > invalid > loading > error; unpending and stateless ids are omitted", () => {
    openFlows();
    latest({ flowId: ID_A }).resolve();
    latest({ flowId: ID_B }).reject({ status: 500 });
    expect(kindOf({ id: ID_A })).toBe("response");
    expect(kindOf({ id: ID_B })).toBe("error");
    expect(kindOf({ id: ID_C })).toBe("loading");
    expect(kindOf({ id: ID_D })).toBe("loading");

    // Abort C and D off the Flows tab, then come back: they are left out.
    clickTab({ id: "MetricsTabApi" });
    changeWindow({ windowKey: "week" });
    clickTab({ id: "MetricsTabFlows" });
    expect(kindOf({ id: ID_A })).toBe("response");
    expect(kindOf({ id: ID_B })).toBe("error");
    expect(kindOf({ id: ID_C })).toBeUndefined();
    expect(kindOf({ id: ID_D })).toBeUndefined();

    // A retried error id is loading while pending; a cached response with a
    // refetch in flight stays a response.
    changeWindow({ windowKey: "month" });
    expect(kindOf({ id: ID_A })).toBe("response");
    expect(kindOf({ id: ID_B })).toBe("loading");
  });

  it("warm cache: switching away and back does not refetch", () => {
    openFlows();
    deferreds.forEach((entry) => entry.resolve());
    fetchFlowSpy.mockClear();

    clickTab({ id: "MetricsTabApi" });
    clickTab({ id: "MetricsTabFlows" });

    expect(fetchFlowSpy).not.toHaveBeenCalled();
    expect(lastEntries().map((entry) => entry.state.kind)).toEqual([
      "response",
      "response",
      "response",
      "response",
    ]);
  });

  it("returning to the tab mid-load does not restart the fan-out", () => {
    openFlows();
    expect(fetchFlowSpy).toHaveBeenCalledTimes(4);

    clickTab({ id: "MetricsTabApi" });
    clickTab({ id: "MetricsTabFlows" });

    expect(fetchFlowSpy).toHaveBeenCalledTimes(4);
    expect(lastEntries().map((entry) => entry.state.kind)).toEqual([
      "loading",
      "loading",
      "loading",
      "loading",
    ]);
  });

  it("first activation issues four requests, shows loading, and announces once on completion", () => {
    initMetricsDashboard();
    fetchFlowSpy.mockClear();
    renderFlowGridSpy.mockClear();
    clickTab({ id: "MetricsTabFlows" });

    expect(fetchFlowSpy).toHaveBeenCalledTimes(4);
    expect(flowsPanel().getAttribute("aria-busy")).toBe("true");
    expect(lastEntries().map((entry) => entry.state.kind)).toEqual([
      "loading",
      "loading",
      "loading",
      "loading",
    ]);

    deferreds.forEach((entry) => entry.resolve());
    expect(flowsPanel().hasAttribute("aria-busy")).toBe(false);
    expect(announcement().textContent).toBe(ANNOUNCEMENT_TEXT);
  });

  it("startFlowFanOut renders loading entries for all ids before any request settles", () => {
    openFlows();

    expect(deferreds).toHaveLength(4);
    expect(lastEntries().map((entry) => entry.id)).toEqual(ALL_IDS);
    expect(lastEntries().every((entry) => entry.state.kind === "loading")).toBe(
      true,
    );
  });

  it("a drop-caused idle clears aria-busy without announcing", () => {
    openFlows();
    deferreds.slice(0, 3).forEach((entry) => entry.resolve());
    announcement().textContent = "";

    _dropFlowIdForTests({ id: ID_D });

    expect(flowsPanel().hasAttribute("aria-busy")).toBe(false);
    expect(announcement().textContent).toBe("");
  });

  it("with six ids only four are in flight; a settle admits the fifth and the rest render as loading", () => {
    const sixIds = ["id1", "id2", "id3", "id4", "id5", "id6"];
    flowIdsHolder.ids = Object.fromEntries(sixIds.map((id) => [id, id]));
    openFlows();

    expect(fetchFlowSpy).toHaveBeenCalledTimes(4);
    expect(lastEntries().map((entry) => entry.state.kind)).toEqual(
      sixIds.map(() => "loading"),
    );

    deferreds[0].resolve();

    expect(fetchFlowSpy).toHaveBeenCalledTimes(5);
    expect(lastEntries().map((entry) => entry.state.kind)).toEqual([
      "response",
      "loading",
      "loading",
      "loading",
      "loading",
      "loading",
    ]);
  });

  it("returning to Flows after all four requests errored retries them", () => {
    openFlows();
    deferreds.forEach((entry) => entry.reject({ status: 500 }));
    expect(lastEntries().map((entry) => entry.state.kind)).toEqual([
      "error",
      "error",
      "error",
      "error",
    ]);
    fetchFlowSpy.mockClear();

    clickTab({ id: "MetricsTabApi" });
    clickTab({ id: "MetricsTabFlows" });

    expect(fetchFlowSpy).toHaveBeenCalledTimes(4);
  });

  it("an empty fan-out clears aria-busy and announces", () => {
    flowIdsHolder.ids = {};
    openFlows();

    expect(fetchFlowSpy).not.toHaveBeenCalled();
    expect(flowsPanel().hasAttribute("aria-busy")).toBe(false);
    expect(announcement().textContent).toBe(ANNOUNCEMENT_TEXT);
  });
});
