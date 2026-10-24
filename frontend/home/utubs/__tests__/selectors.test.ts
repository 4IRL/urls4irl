import type { UtubDetail } from "../../../types/utub.js";

import { fetchUTubForRefresh, selectUTub } from "../selectors.js";
import { showUTubLoadingIconAndSetTimeout } from "../deck.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { AppEvents, emit } from "../../../lib/event-bus.js";
import { createMockJqXHR } from "../../../__tests__/helpers/mock-jquery.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../header-fit.js", () => ({ fitUTubHeaderAndSubheader: vi.fn() }));

vi.mock("../deck.js", () => ({
  showUTubLoadingIconAndSetTimeout: vi.fn(() => 0),
  hideUTubLoadingIconAndClearTimeout: vi.fn(),
  setUTubDeckOnUTubSelected: vi.fn(),
}));

vi.mock("../../urls/update-description.js", () => ({
  removeEventListenersForShowCreateUTubDescIfEmptyDesc: vi.fn(),
  showCreateDescriptionButtonAlways: vi.fn(),
}));

vi.mock("../../../lib/event-bus.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../../lib/event-bus.js")
  >("../../../lib/event-bus.js");
  return {
    ...actual,
    emit: vi.fn(),
  };
});

vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  replaceMobilePanelHistoryState: vi.fn(),
}));

const $ = window.jQuery;

const SELECTORS_HTML = `
  <input id="UTubNameSearch" value="" />
  <div id="listUTubs">
    <span class="UTubSelector" utubid="1" position="1"></span>
    <span class="UTubSelector" utubid="2" position="2"></span>
  </div>
  <span id="URLDeckLockIcon" class="hidden"></span>
  <h2 id="URLDeckSubheader"></h2>
  <div id="UTubDescriptionSubheaderWrap"></div>
  <button id="URLDeckSubheaderCreateDescription"></button>
  <div id="URLDeckNoDescription"></div>
  <input id="utubDescriptionUpdate" />
`;

function makeUtubDetail({ id }: { id: number }): UtubDetail {
  const utubDetail: Partial<UtubDetail> = {
    id,
    name: `UTub ${id}`,
    description: "",
    isCreator: false,
    isCoCreator: false,
    isLocked: false,
    currentUser: 1,
    createdByUserID: 2,
    urls: [],
    tags: [],
    members: [],
  };
  return utubDetail as UtubDetail;
}

// jQuery 3 runs Deferred `.then` callbacks on a later macrotask, so a queued
// zero-delay timer lands after any callback scheduled by an earlier resolve.
function flushDeferredCallbacks(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

function utubSelectedEmits(): unknown[][] {
  return vi
    .mocked(emit)
    .mock.calls.filter(([eventName]) => eventName === AppEvents.UTUB_SELECTED);
}

describe("getSelectedUTubInfo — out-of-order UTub responses", () => {
  let getJSONSpy: ReturnType<typeof vi.spyOn>;
  let firstRequest: ReturnType<typeof createMockJqXHR>;
  let secondRequest: ReturnType<typeof createMockJqXHR>;

  beforeEach(() => {
    document.body.innerHTML = SELECTORS_HTML;
    resetStore();
    vi.clearAllMocks();
    window.history.replaceState(null, "", "/");
    firstRequest = createMockJqXHR();
    secondRequest = createMockJqXHR();
    getJSONSpy = vi
      .spyOn($, "getJSON")
      .mockReturnValueOnce(firstRequest)
      .mockReturnValueOnce(secondRequest);
  });

  afterEach(() => {
    getJSONSpy.mockRestore();
    vi.mocked(emit).mockReset();
    document.body.innerHTML = "";
    resetStore();
  });

  it("renders the currently selected UTub when its response arrives", async () => {
    selectUTub(1, $(".UTubSelector[utubid='1']"));

    firstRequest.resolve(makeUtubDetail({ id: 1 }));

    await vi.waitFor(() => {
      expect(getState().activeUTubID).toBe(1);
    });
    expect(utubSelectedEmits()).toHaveLength(1);
    expect(utubSelectedEmits()[0][1]).toMatchObject({ utubID: 1 });
  });

  it("keeps settings saved during the fetch of a same-UTub rebuild", async () => {
    const saved = {
      utubs: { saved: 1 },
      members: {},
      tags: {},
      urls: { default_url_scheme: "https", hide_scheme_selector: false },
    };
    setState({ activeUTubID: 1, settings: { ...saved, utubs: {} } as never });
    selectUTub(1, $(".UTubSelector[utubid='1']"));
    setState({ settings: saved as never, settingsVersion: 1 });

    firstRequest.resolve(makeUtubDetail({ id: 1 }));

    await vi.waitFor(() => {
      expect(utubSelectedEmits()).toHaveLength(1);
    });
    expect(getState().settings).toEqual(saved);
  });

  it("takes the new UTub's settings on a different-UTub switch", async () => {
    setState({ activeUTubID: 2, settings: { utubs: { old: 1 } } as never });
    selectUTub(1, $(".UTubSelector[utubid='1']"));
    setState({ settingsVersion: 1 });

    firstRequest.resolve(makeUtubDetail({ id: 1 }));

    await vi.waitFor(() => {
      expect(utubSelectedEmits()).toHaveLength(1);
    });
    expect(getState().settings).toEqual({
      utubs: {},
      members: {},
      tags: {},
      urls: { default_url_scheme: "https", hide_scheme_selector: false },
    });
  });

  it("populates the store's members before UTUB_SELECTED is emitted (cards never see an empty member list)", async () => {
    const members = [
      { id: 1, username: "alice", memberRole: "member" as const },
    ];
    let membersSeenAtEmit: unknown = null;
    vi.mocked(emit).mockImplementation(((eventName: string) => {
      if (eventName === AppEvents.UTUB_SELECTED) {
        membersSeenAtEmit = getState().members;
      }
    }) as unknown as typeof emit);
    selectUTub(1, $(".UTubSelector[utubid='1']"));

    firstRequest.resolve({ ...makeUtubDetail({ id: 1 }), members });

    await vi.waitFor(() => {
      expect(utubSelectedEmits()).toHaveLength(1);
    });
    expect(membersSeenAtEmit).toEqual(members);
  });

  it("ignores a previously selected UTub's response that lands after the current one", async () => {
    selectUTub(1, $(".UTubSelector[utubid='1']"));
    selectUTub(2, $(".UTubSelector[utubid='2']"));

    secondRequest.resolve(makeUtubDetail({ id: 2 }));
    await vi.waitFor(() => {
      expect(getState().activeUTubID).toBe(2);
    });

    firstRequest.resolve(makeUtubDetail({ id: 1 }));
    await flushDeferredCallbacks();

    expect(getState().activeUTubID).toBe(2);
    expect(getState().activeUTubName).toBe("UTub 2");
    expect(utubSelectedEmits()).toHaveLength(1);
    expect($(".UTubSelector.active").attr("utubid")).toBe("2");
  });

  it("renders the response when no UTub selector is active any more", async () => {
    selectUTub(1, $(".UTubSelector[utubid='1']"));
    $(".UTubSelector").removeClass("active");

    firstRequest.resolve(makeUtubDetail({ id: 1 }));

    await vi.waitFor(() => {
      expect(getState().activeUTubID).toBe(1);
    });
    expect(utubSelectedEmits()).toHaveLength(1);
  });

  it("does not redirect to the error page when a previously selected UTub's request fails", async () => {
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});

    selectUTub(1, $(".UTubSelector[utubid='1']"));
    selectUTub(2, $(".UTubSelector[utubid='2']"));

    firstRequest.reject({ status: 404 });
    await flushDeferredCallbacks();

    expect(assignSpy).not.toHaveBeenCalled();

    assignSpy.mockRestore();
  });

  it("leaves browser history alone when a previously selected UTub's request fails", async () => {
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    const replaceStateSpy = vi.spyOn(window.history, "replaceState");

    selectUTub(1, $(".UTubSelector[utubid='1']"));
    selectUTub(2, $(".UTubSelector[utubid='2']"));

    firstRequest.reject({ status: 404 });
    await flushDeferredCallbacks();

    expect(replaceStateSpy).not.toHaveBeenCalled();

    replaceStateSpy.mockRestore();
    assignSpy.mockRestore();
  });

  it("resets browser history to /home when the currently selected UTub's request fails", async () => {
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    const replaceStateSpy = vi.spyOn(window.history, "replaceState");

    selectUTub(1, $(".UTubSelector[utubid='1']"));

    firstRequest.reject({ status: 404 });
    await flushDeferredCallbacks();

    expect(replaceStateSpy).toHaveBeenCalledWith(null, "", "/home");

    replaceStateSpy.mockRestore();
    assignSpy.mockRestore();
  });

  it("redirects to the error page when the currently selected UTub's request fails", async () => {
    const assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});

    selectUTub(1, $(".UTubSelector[utubid='1']"));

    firstRequest.reject({ status: 404 });

    await vi.waitFor(() => {
      expect(assignSpy).toHaveBeenCalledWith("/error");
    });

    assignSpy.mockRestore();
  });
});

describe("fetchUTubForRefresh — background-safe fetch", () => {
  let getJSONSpy: ReturnType<typeof vi.spyOn>;
  let request: ReturnType<typeof createMockJqXHR>;
  let replaceStateSpy: ReturnType<typeof vi.spyOn>;
  let assignSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    document.body.innerHTML = SELECTORS_HTML;
    resetStore();
    vi.clearAllMocks();
    request = createMockJqXHR();
    getJSONSpy = vi.spyOn($, "getJSON").mockReturnValue(request);
    replaceStateSpy = vi
      .spyOn(window.history, "replaceState")
      .mockImplementation(() => {});
    assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
  });

  afterEach(() => {
    getJSONSpy.mockRestore();
    replaceStateSpy.mockRestore();
    assignSpy.mockRestore();
    document.body.innerHTML = "";
    resetStore();
  });

  function expectNoSideEffects(): void {
    expect(showUTubLoadingIconAndSetTimeout).not.toHaveBeenCalled();
    expect(replaceStateSpy).not.toHaveBeenCalled();
    expect(assignSpy).not.toHaveBeenCalled();
  }

  it("requests the refresh route and resolves ok on a 200", async () => {
    const detail = makeUtubDetail({ id: 7 });
    const resultPromise = fetchUTubForRefresh({ utubID: 7 });

    request.resolve(detail, "success", { status: 200 });

    await expect(resultPromise).resolves.toEqual({ kind: "ok", data: detail });
    expect(getJSONSpy).toHaveBeenCalledWith(APP_CONFIG.routes.refreshUTub(7));
    expectNoSideEffects();
  });

  it("resolves error on a success callback that is not an explicit 200", async () => {
    const resultPromise = fetchUTubForRefresh({ utubID: 7 });

    request.resolve(makeUtubDetail({ id: 7 }), "success", { status: 204 });

    await expect(resultPromise).resolves.toEqual({ kind: "error" });
    expectNoSideEffects();
  });

  it("resolves gone on a 404", async () => {
    const resultPromise = fetchUTubForRefresh({ utubID: 7 });

    request.reject({ status: 404 });

    await expect(resultPromise).resolves.toEqual({ kind: "gone" });
    await flushDeferredCallbacks();
    expectNoSideEffects();
  });

  it.each([403, 500, 0])("resolves error on status %i", async (status) => {
    const resultPromise = fetchUTubForRefresh({ utubID: 7 });

    request.reject({ status });

    await expect(resultPromise).resolves.toEqual({ kind: "error" });
    await flushDeferredCallbacks();
    expectNoSideEffects();
  });

  it("resolves error without replacing the page when the 429 was already handled", async () => {
    const resultPromise = fetchUTubForRefresh({ utubID: 7 });

    request.reject({ status: 429, _429Handled: true });

    await expect(resultPromise).resolves.toEqual({ kind: "error" });
    await flushDeferredCallbacks();
    expectNoSideEffects();
    expect(document.body.innerHTML).toContain("listUTubs");
  });
});
