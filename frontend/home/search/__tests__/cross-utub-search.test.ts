import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { APP_CONFIG } from "../../../lib/config.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import {
  CROSS_UTUB_SEARCH_CLOSE_TARGET,
  CROSS_UTUB_SEARCH_CLOSE_TRIGGER,
  CROSS_UTUB_SEARCH_OPEN_TARGET,
  CROSS_UTUB_SEARCH_REFRESH_TARGET,
  CROSS_UTUB_SEARCH_RESULT_ACCESS_TARGET,
  CROSS_UTUB_SEARCH_RESULT_ACCESS_TRIGGER,
} from "../../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../render.js", () => ({
  renderSearchResults: vi.fn(),
}));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ utubs: [{ id: 1 }], activeUTubID: null })),
  setState: vi.fn(),
}));

vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  setMobileUIWhenUTubSelectedOrURLNavSelected: vi.fn(),
  setMobileUIWhenUTubNotSelectedOrUTubDeleted: vi.fn(),
}));

vi.mock("../../utubs/search.js", () => ({
  resetUTubSearch: vi.fn(),
}));

vi.mock("../../utubs/selectors.js", () => ({
  selectUTub: vi.fn(),
  getSelectedUTubInfo: vi.fn(),
  pushUTubHistoryState: vi.fn(),
}));

vi.mock("../../urls/cards/selection.js", () => ({
  selectURLCard: vi.fn(),
}));

vi.mock("../../utubs/utils.js", () => ({
  getAllUTubs: vi.fn(),
}));

vi.mock("../../utubs/deck.js", () => ({
  buildUTubDeck: vi.fn(),
}));

const $ = window.jQuery;

const SEARCH_MODE_HTML = `
  <button id="toCrossUtubSearch" class="hidden">
    <span id="crossSearchTriggerOpenIcon"></span>
    <span id="crossSearchTriggerCloseIcon" class="hidden"></span>
  </button>
  <button id="navReturnHome" class="hidden"></button>
  <div id="leftPanel" class="panel"></div>
  <button id="toUTubs"></button>
  <button id="toURLs"></button>
  <button id="toMembers"></button>
  <button id="toTags"></button>
  <div id="crossUtubSearchMode" class="cross-search-hidden">
    <div id="crossUtubSearchInputWrap"><input id="crossUtubSearchInput" type="search" /><button id="crossUtubSearchClear" class="hidden"></button></div>
    <button id="crossUtubSearchSubmit" disabled><span class="crossSearchSubmitIcon"></span><span class="crossSearchRefreshIcon hidden"></span></button>
    <div id="crossUtubSearchFieldControls"></div>
    <span id="crossUtubSearchAnnouncement"></span>
    <div id="crossUtubSearchResults"></div>
    <p id="crossUtubSearchNoResults" class="hidden"></p>
    <p id="crossUtubSearchShortQuery" class="hidden"></p>
  </div>
`;

function buildDoneXhr(results: unknown[]): JQuery.jqXHR {
  return {
    done: vi.fn(function (
      this: JQuery.jqXHR,
      cb: (data: { results: unknown[] }) => void,
    ) {
      cb({ results });
      return this;
    }),
    fail: vi.fn().mockReturnThis(),
    always: vi.fn().mockReturnThis(),
    abort: vi.fn(),
  } as unknown as JQuery.jqXHR;
}

function buildFailXhr(status: number): JQuery.jqXHR {
  return {
    done: vi.fn().mockReturnThis(),
    fail: vi.fn(function (
      this: JQuery.jqXHR,
      cb: (xhr: { status: number; responseJSON?: unknown }) => void,
    ) {
      cb({ status });
      return this;
    }),
    always: vi.fn().mockReturnThis(),
    abort: vi.fn(),
  } as unknown as JQuery.jqXHR;
}

describe("cross-utub-search — mode mechanics", () => {
  beforeEach(async () => {
    document.body.innerHTML = SEARCH_MODE_HTML;
    vi.clearAllMocks();
    // Reset module-scoped search-mode state between tests.
    const { exitCrossUtubSearchMode } = await import("../cross-utub-search.js");
    exitCrossUtubSearchMode({
      trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.ESCAPE_KEY,
    });
  });

  afterEach(() => {
    document.body.innerHTML = "";
    vi.useRealTimers();
  });

  it("(a) Cmd/Ctrl+K opens search mode, focuses input, emits OPEN", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");
    const { initCrossUtubSearch } = await import("../cross-utub-search.js");
    initCrossUtubSearch();

    const event = $.Event("keydown.crossSearchOpen", {
      key: "k",
      metaKey: true,
    });
    $(document).trigger(event);

    const mode = $("#crossUtubSearchMode");
    expect(mode.hasClass("cross-search-visible")).toBe(true);
    expect(mode.hasClass("cross-search-hidden")).toBe(false);
    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_CROSS_UTUB_SEARCH_OPEN,
      target: CROSS_UTUB_SEARCH_OPEN_TARGET.CROSS_UTUB,
    });
  });

  it("(b) typing does NOT fetch; clicking submit fetches once with the right URL and renders results", async () => {
    const { ajaxCall } = await import("../../../lib/ajax.js");
    (ajaxCall as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
      buildDoneXhr([{ utubID: 1, utubName: "A", urls: [] }]),
    );
    const { renderSearchResults } = await import("../render.js");
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    // Typing alone never fires a request (the per-keystroke debounce is gone).
    $("#crossUtubSearchInput").val("alpha").trigger("input");
    expect(ajaxCall).not.toHaveBeenCalled();

    $("#crossUtubSearchSubmit").trigger("click");

    expect(ajaxCall).toHaveBeenCalledTimes(1);
    const calledUrl = (ajaxCall as unknown as ReturnType<typeof vi.fn>).mock
      .calls[0][1] as string;
    expect(calledUrl).toBe(`${APP_CONFIG.routes.crossUtubSearch}?q=alpha`);
    expect(renderSearchResults).toHaveBeenCalledWith({
      results: [{ utubID: 1, utubName: "A", urls: [] }],
      query: "alpha",
    });
  });

  it("(b1) pressing Enter in the input fetches once", async () => {
    const { ajaxCall } = await import("../../../lib/ajax.js");
    (ajaxCall as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
      buildDoneXhr([]),
    );
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    $("#crossUtubSearchInput").val("alpha").trigger("input");
    const enter = $.Event("keydown.crossSearchSubmit", { key: "Enter" });
    $("#crossUtubSearchInput").trigger(enter);

    expect(ajaxCall).toHaveBeenCalledTimes(1);
    const calledUrl = (ajaxCall as unknown as ReturnType<typeof vi.fn>).mock
      .calls[0][1] as string;
    expect(calledUrl).toBe(`${APP_CONFIG.routes.crossUtubSearch}?q=alpha`);
  });

  it("(b1a) spamming Enter aborts each in-flight request so only the last survives", async () => {
    const { ajaxCall } = await import("../../../lib/ajax.js");
    const xhr1 = buildDoneXhr([]);
    const xhr2 = buildDoneXhr([]);
    const xhr3 = buildDoneXhr([]);
    (ajaxCall as unknown as ReturnType<typeof vi.fn>)
      .mockReturnValueOnce(xhr1)
      .mockReturnValueOnce(xhr2)
      .mockReturnValueOnce(xhr3);
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    $("#crossUtubSearchInput").val("alpha").trigger("input");
    const enter = $.Event("keydown.crossSearchSubmit", { key: "Enter" });
    $("#crossUtubSearchInput").trigger(enter);
    $("#crossUtubSearchInput").trigger(enter);
    $("#crossUtubSearchInput").trigger(enter);

    // Each press starts a request, but every predecessor is aborted; only the
    // final request is left running.
    expect(ajaxCall).toHaveBeenCalledTimes(3);
    expect(xhr1.abort).toHaveBeenCalledTimes(1);
    expect(xhr2.abort).toHaveBeenCalledTimes(1);
    expect(xhr3.abort).not.toHaveBeenCalled();
  });

  it("(b1b) an aborted request (status 0) renders nothing and shows no error", async () => {
    const { ajaxCall } = await import("../../../lib/ajax.js");
    (ajaxCall as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
      buildFailXhr(0),
    );
    const { renderSearchResults } = await import("../render.js");
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    $("#crossUtubSearchInput").val("alpha").trigger("input");
    const enter = $.Event("keydown.crossSearchSubmit", { key: "Enter" });
    $("#crossUtubSearchInput").trigger(enter);

    expect(renderSearchResults).not.toHaveBeenCalled();
    expect($("#crossUtubSearchNoResults").hasClass("hidden")).toBe(true);
  });

  it("(b1c) exiting search mode aborts the in-flight request", async () => {
    const { ajaxCall } = await import("../../../lib/ajax.js");
    const xhr = buildDoneXhr([]);
    (ajaxCall as unknown as ReturnType<typeof vi.fn>).mockReturnValue(xhr);
    const {
      initCrossUtubSearch,
      enterCrossUtubSearchMode,
      exitCrossUtubSearchMode,
    } = await import("../cross-utub-search.js");
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    $("#crossUtubSearchInput").val("alpha").trigger("input");
    const enter = $.Event("keydown.crossSearchSubmit", { key: "Enter" });
    $("#crossUtubSearchInput").trigger(enter);

    exitCrossUtubSearchMode({
      trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.ESCAPE_KEY,
    });

    expect(xhr.abort).toHaveBeenCalledTimes(1);
  });

  it("(b1d) a completed request clears _inFlight via .always, so the next submit does NOT abort it", async () => {
    const { ajaxCall } = await import("../../../lib/ajax.js");
    // jQuery fires .always AFTER the request settles, not during chaining, so
    // capture the production callback and invoke it once the first submit has
    // assigned _inFlight — mirroring a real async completion. (buildDoneXhr's
    // .always only returns this and never nulls _inFlight.)
    let firstAlwaysCallback: (() => void) | null = null;
    function buildSettlingXhr(
      onAlways: (cb: () => void) => void,
    ): JQuery.jqXHR {
      return {
        done: vi.fn().mockReturnThis(),
        fail: vi.fn().mockReturnThis(),
        always: vi.fn(function (this: JQuery.jqXHR, cb: () => void) {
          onAlways(cb);
          return this;
        }),
        abort: vi.fn(),
      } as unknown as JQuery.jqXHR;
    }
    const xhr1 = buildSettlingXhr((cb) => {
      firstAlwaysCallback = cb;
    });
    const xhr2 = buildSettlingXhr(() => {});
    (ajaxCall as unknown as ReturnType<typeof vi.fn>)
      .mockReturnValueOnce(xhr1)
      .mockReturnValueOnce(xhr2);
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    $("#crossUtubSearchInput").val("alpha").trigger("input");
    const enter = $.Event("keydown.crossSearchSubmit", { key: "Enter" });
    $("#crossUtubSearchInput").trigger(enter);

    // The first request settles (its .always runs, nulling _inFlight) before
    // the second submit fires.
    firstAlwaysCallback!();
    $("#crossUtubSearchInput").trigger(enter);

    // _inFlight was already null when the second submit ran, so the first
    // request's abort was never called.
    expect(ajaxCall).toHaveBeenCalledTimes(2);
    expect(xhr1.abort).not.toHaveBeenCalled();
    expect(xhr2.abort).not.toHaveBeenCalled();
  });

  it("(b1e) the initCrossUtubSearch viewport-reset closure aborts the in-flight request", async () => {
    // initCrossUtubSearch binds a breakpoint `change` listener that resets
    // search-mode state directly (it does NOT call exitCrossUtubSearchMode, to
    // avoid listener registration-order coupling with mobile.ts). Capture that
    // reset closure off matchMedia, fire a request via Enter, then invoke the
    // closure and assert it aborts the in-flight request exactly once.
    let resetClosure: (() => void) | null = null;
    const matchMediaSpy = vi.spyOn(window, "matchMedia").mockReturnValue({
      addEventListener: (
        _event: string,
        listener: EventListenerOrEventListenerObject,
      ) => {
        resetClosure = listener as () => void;
      },
      removeEventListener: vi.fn(),
    } as unknown as MediaQueryList);

    const { ajaxCall } = await import("../../../lib/ajax.js");
    const xhr = buildDoneXhr([]);
    (ajaxCall as unknown as ReturnType<typeof vi.fn>).mockReturnValue(xhr);
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    $("#crossUtubSearchInput").val("alpha").trigger("input");
    const enter = $.Event("keydown.crossSearchSubmit", { key: "Enter" });
    $("#crossUtubSearchInput").trigger(enter);

    resetClosure!();

    expect(xhr.abort).toHaveBeenCalledTimes(1);

    matchMediaSpy.mockRestore();
  });

  it("(b2) a non-default field selection appends the &fields= query param", async () => {
    const { ajaxCall } = await import("../../../lib/ajax.js");
    (ajaxCall as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
      buildDoneXhr([{ utubID: 1, utubName: "A", urls: [] }]),
    );
    const {
      initCrossUtubSearch,
      enterCrossUtubSearchMode,
      performCrossUtubSearch,
    } = await import("../cross-utub-search.js");
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    performCrossUtubSearch({ query: "alpha", fields: ["title"] });

    expect(ajaxCall).toHaveBeenCalledTimes(1);
    const calledUrl = (ajaxCall as unknown as ReturnType<typeof vi.fn>).mock
      .calls[0][1] as string;
    expect(calledUrl).toBe(
      `${APP_CONFIG.routes.crossUtubSearch}?q=alpha&fields=title`,
    );
  });

  it("(c) empty result set shows the no-results state", async () => {
    const { ajaxCall } = await import("../../../lib/ajax.js");
    (ajaxCall as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
      buildDoneXhr([]),
    );
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    $("#crossUtubSearchInput").val("zzz").trigger("input");
    $("#crossUtubSearchSubmit").trigger("click");

    expect($("#crossUtubSearchNoResults").hasClass("hidden")).toBe(false);
  });

  it("(d) is429Handled true early-returns without rendering", async () => {
    vi.useFakeTimers();
    const ajaxModule = await import("../../../lib/ajax.js");
    (
      ajaxModule.is429Handled as unknown as ReturnType<typeof vi.fn>
    ).mockReturnValue(true);
    (
      ajaxModule.ajaxCall as unknown as ReturnType<typeof vi.fn>
    ).mockReturnValue(buildFailXhr(429));
    const { renderSearchResults } = await import("../render.js");
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    $("#crossUtubSearchInput").val("alpha").trigger("input");
    $("#crossUtubSearchSubmit").trigger("click");

    expect(renderSearchResults).not.toHaveBeenCalled();
    expect($("#crossUtubSearchNoResults").hasClass("hidden")).toBe(true);
  });

  it("(d2) a 400 error response shows the no-results state", async () => {
    const ajaxModule = await import("../../../lib/ajax.js");
    (
      ajaxModule.is429Handled as unknown as ReturnType<typeof vi.fn>
    ).mockReturnValue(false);
    (
      ajaxModule.ajaxCall as unknown as ReturnType<typeof vi.fn>
    ).mockReturnValue(buildFailXhr(400));
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    $("#crossUtubSearchInput").val("alpha").trigger("input");
    $("#crossUtubSearchSubmit").trigger("click");

    expect($("#crossUtubSearchNoResults").hasClass("hidden")).toBe(false);
  });

  it("(e) ESC closes the mode and emits CLOSE", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();
    (emit as unknown as ReturnType<typeof vi.fn>).mockClear();

    const event = $.Event("keydown.crossSearchEsc", { key: "Escape" });
    $(document).trigger(event);

    const mode = $("#crossUtubSearchMode");
    expect(mode.hasClass("cross-search-hidden")).toBe(true);
    expect(mode.hasClass("cross-search-visible")).toBe(false);
    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_CROSS_UTUB_SEARCH_CLOSE,
      target: CROSS_UTUB_SEARCH_CLOSE_TARGET.CROSS_UTUB,
      trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.ESCAPE_KEY,
    });
  });

  it("(f) the navbar trigger morphs to its close glyph on open and back on close", async () => {
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();

    // Closed: open glyph shown, close glyph hidden, open aria-label.
    const openIcon = $("#crossSearchTriggerOpenIcon");
    const closeIcon = $("#crossSearchTriggerCloseIcon");
    expect(openIcon.hasClass("hidden")).toBe(false);
    expect(closeIcon.hasClass("hidden")).toBe(true);

    enterCrossUtubSearchMode();
    expect(openIcon.hasClass("hidden")).toBe(true);
    expect(closeIcon.hasClass("hidden")).toBe(false);
    expect($("#toCrossUtubSearch").attr("aria-label")).toBe(
      APP_CONFIG.strings.CROSS_SEARCH_TRIGGER_CLOSE_LABEL,
    );
    // The bordered "called-out" styling applies only while open (Close state).
    expect(
      $("#toCrossUtubSearch").hasClass("navbar-cross-search--active"),
    ).toBe(true);

    const event = $.Event("keydown.crossSearchEsc", { key: "Escape" });
    $(document).trigger(event);
    expect(openIcon.hasClass("hidden")).toBe(false);
    expect(closeIcon.hasClass("hidden")).toBe(true);
    expect($("#toCrossUtubSearch").attr("aria-label")).toBe(
      APP_CONFIG.strings.CROSS_SEARCH_TRIGGER_OPEN_LABEL,
    );
    expect(
      $("#toCrossUtubSearch").hasClass("navbar-cross-search--active"),
    ).toBe(false);
  });

  it("(f2) the submit button is disabled when empty and enabled once text is typed", async () => {
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    const submit = $("#crossUtubSearchSubmit");
    expect(submit.prop("disabled")).toBe(true);

    $("#crossUtubSearchInput").val("alpha").trigger("input");
    expect(submit.prop("disabled")).toBe(false);

    $("#crossUtubSearchInput").val("").trigger("input");
    expect(submit.prop("disabled")).toBe(true);
  });

  it("(f3) after a search the submit button morphs to Refresh; re-submitting re-runs the query and emits REFRESH; editing flips back to Search", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");
    const { ajaxCall } = await import("../../../lib/ajax.js");
    (ajaxCall as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
      buildDoneXhr([]),
    );
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    $("#crossUtubSearchInput").val("alpha").trigger("input");
    $("#crossUtubSearchSubmit").trigger("click");

    // Now in Refresh state: refresh glyph shown, search glyph hidden.
    const submit = $("#crossUtubSearchSubmit");
    expect(submit.find(".crossSearchRefreshIcon").hasClass("hidden")).toBe(
      false,
    );
    expect(submit.find(".crossSearchSubmitIcon").hasClass("hidden")).toBe(true);
    expect(submit.attr("aria-label")).toBe(
      APP_CONFIG.strings.CROSS_SEARCH_REFRESH_LABEL,
    );

    (emit as unknown as ReturnType<typeof vi.fn>).mockClear();
    submit.trigger("click");

    // Re-running the identical query fires a second request and records REFRESH.
    expect(ajaxCall).toHaveBeenCalledTimes(2);
    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_CROSS_UTUB_SEARCH_REFRESH,
      target: CROSS_UTUB_SEARCH_REFRESH_TARGET.CROSS_UTUB,
    });

    // Editing the query away from the last-submitted value flips back to Search.
    $("#crossUtubSearchInput").val("alphab").trigger("input");
    expect(submit.find(".crossSearchSubmitIcon").hasClass("hidden")).toBe(
      false,
    );
    expect(submit.find(".crossSearchRefreshIcon").hasClass("hidden")).toBe(
      true,
    );
  });

  it("(h) clicking the navbar trigger while open toggles the mode closed and emits CLOSE with the trigger_icon trigger", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();
    (emit as unknown as ReturnType<typeof vi.fn>).mockClear();

    $("#toCrossUtubSearch").trigger("click");

    const mode = $("#crossUtubSearchMode");
    expect(mode.hasClass("cross-search-hidden")).toBe(true);
    expect(mode.hasClass("cross-search-visible")).toBe(false);
    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_CROSS_UTUB_SEARCH_CLOSE,
      target: CROSS_UTUB_SEARCH_CLOSE_TARGET.CROSS_UTUB,
      trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.TRIGGER_ICON,
    });
  });

  it("(h2) opening search reveals the hamburger Return Home item; closing hides it", async () => {
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();

    expect($("#navReturnHome").hasClass("hidden")).toBe(true);
    enterCrossUtubSearchMode();
    expect($("#navReturnHome").hasClass("hidden")).toBe(false);

    const event = $.Event("keydown.crossSearchEsc", { key: "Escape" });
    $(document).trigger(event);
    expect($("#navReturnHome").hasClass("hidden")).toBe(true);
  });

  it("(i) typing shows the clear button; clicking it clears the input and re-hides the button", async () => {
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    const clearButton = $("#crossUtubSearchClear");
    expect(clearButton.hasClass("hidden")).toBe(true);

    $("#crossUtubSearchInput").val("alpha").trigger("input");
    expect(clearButton.hasClass("hidden")).toBe(false);

    clearButton.trigger("click");

    expect($("#crossUtubSearchInput").val()).toBe("");
    expect($("#crossUtubSearchClear").hasClass("hidden")).toBe(true);
  });

  it("(g) clicking a result card exits mode, selects the UTub, and selects the URL card after UTUB_SELECTED", async () => {
    // Partial-mock the event bus: keep the real on/emit so the one-shot
    // subscription wired by the click handler actually fires, but the rest of
    // the module is shared with cross-utub-search.ts via importActual.
    const eventBus = await vi.importActual<
      typeof import("../../../lib/event-bus.js")
    >("../../../lib/event-bus.js");
    const { selectUTub } = await import("../../utubs/selectors.js");
    const { selectURLCard } = await import("../../urls/cards/selection.js");
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    // A rendered result card plus the UTub selector the click handler locates,
    // and the target .urlRow the URL deck would render once UTUB_SELECTED fires.
    const targetUtubID = 7;
    const targetUrlID = 42;
    $("#crossUtubSearchResults").html(
      `<div class="crossSearchHitCard" data-utub-id="${targetUtubID}" data-utub-url-id="${targetUrlID}"></div>`,
    );
    $(document.body).append(
      `<div class="UTubSelector" utubid="${targetUtubID}"></div>` +
        `<div class="urlRow" utuburlid="${targetUrlID}"></div>`,
    );

    $(`.crossSearchHitCard[data-utub-id="${targetUtubID}"]`).trigger("click");

    // Mode exits and the source UTub is selected via its selector element.
    expect($("#crossUtubSearchMode").hasClass("cross-search-hidden")).toBe(
      true,
    );
    expect(selectUTub).toHaveBeenCalledTimes(1);
    const selectUTubCall = (selectUTub as unknown as ReturnType<typeof vi.fn>)
      .mock.calls[0];
    expect(selectUTubCall[0]).toBe(targetUtubID);

    // The URL card is NOT selected synchronously — only after UTUB_SELECTED.
    expect(selectURLCard).not.toHaveBeenCalled();

    eventBus.emit(eventBus.AppEvents.UTUB_SELECTED, {
      utubID: targetUtubID,
      utubName: "Seven",
      urls: [],
      tags: [],
      members: [],
      utubOwnerID: 1,
      isCurrentUserOwner: true,
      currentUserID: 1,
    });

    expect(selectURLCard).toHaveBeenCalledTimes(1);
    const selectedCard = (selectURLCard as unknown as ReturnType<typeof vi.fn>)
      .mock.calls[0][0] as JQuery;
    expect(selectedCard.attr("utuburlid")).toBe(String(targetUrlID));
  });

  it("(g2) clicking a result card whose UTub is already active selects the URL card synchronously without selecting the UTub", async () => {
    const { getState } = await import("../../../store/app-store.js");
    const { selectUTub } = await import("../../utubs/selectors.js");
    const { selectURLCard } = await import("../../urls/cards/selection.js");
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    // The deck is already built for the hit card's UTub: activeUTubID matches.
    const targetUtubID = 7;
    const targetUrlID = 42;
    (getState as unknown as ReturnType<typeof vi.fn>).mockReturnValueOnce({
      utubs: [{ id: targetUtubID }],
      activeUTubID: targetUtubID,
    });

    $("#crossUtubSearchResults").html(
      `<div class="crossSearchHitCard" data-utub-id="${targetUtubID}" data-utub-url-id="${targetUrlID}"></div>`,
    );
    $(document.body).append(
      `<div class="urlRow" utuburlid="${targetUrlID}"></div>`,
    );

    $(`.crossSearchHitCard[data-utub-id="${targetUtubID}"]`).trigger("click");

    // Mode exits and the URL card is selected synchronously — no UTUB_SELECTED
    // emission is awaited and the already-active UTub is not re-selected.
    expect($("#crossUtubSearchMode").hasClass("cross-search-hidden")).toBe(
      true,
    );
    expect(selectUTub).not.toHaveBeenCalled();
    expect(selectURLCard).toHaveBeenCalledTimes(1);
    const selectedCard = (selectURLCard as unknown as ReturnType<typeof vi.fn>)
      .mock.calls[0][0] as JQuery;
    expect(selectedCard.attr("utuburlid")).toBe(String(targetUrlID));
  });

  it("(g3) clicking a result card records the search in browser history before navigating", async () => {
    const pushStateSpy = vi.spyOn(window.history, "pushState");
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    const targetUtubID = 7;
    const targetUrlID = 42;
    $("#crossUtubSearchInput").val("cats");
    $("#crossUtubSearchResults").html(
      `<div class="crossSearchHitCard" data-utub-id="${targetUtubID}" data-utub-url-id="${targetUrlID}"></div>`,
    );
    $(document.body).append(
      `<div class="UTubSelector" utubid="${targetUtubID}"></div>` +
        `<div class="urlRow" utuburlid="${targetUrlID}"></div>`,
    );

    $(`.crossSearchHitCard[data-utub-id="${targetUtubID}"]`).trigger("click");

    // A crossSearch entry is pushed carrying the query + current field order so
    // popstate can re-run it on Back.
    expect(pushStateSpy).toHaveBeenCalledWith(
      { crossSearch: { query: "cats", fields: ["url", "title", "tag"] } },
      "",
      "/home",
    );

    pushStateSpy.mockRestore();
  });

  it("(g4) the already-active fast-path also pushes a UTub entry so Back lands on the search entry", async () => {
    const pushStateSpy = vi.spyOn(window.history, "pushState");
    const { getState } = await import("../../../store/app-store.js");
    const { pushUTubHistoryState } = await import("../../utubs/selectors.js");
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();

    const targetUtubID = 7;
    const targetUrlID = 42;
    (getState as unknown as ReturnType<typeof vi.fn>).mockReturnValueOnce({
      utubs: [{ id: targetUtubID }],
      activeUTubID: targetUtubID,
    });
    $("#crossUtubSearchInput").val("cats");
    $("#crossUtubSearchResults").html(
      `<div class="crossSearchHitCard" data-utub-id="${targetUtubID}" data-utub-url-id="${targetUrlID}"></div>`,
    );
    $(document.body).append(
      `<div class="urlRow" utuburlid="${targetUrlID}"></div>`,
    );

    $(`.crossSearchHitCard[data-utub-id="${targetUtubID}"]`).trigger("click");

    expect(pushStateSpy).toHaveBeenCalledWith(
      { crossSearch: { query: "cats", fields: ["url", "title", "tag"] } },
      "",
      "/home",
    );
    expect(pushUTubHistoryState).toHaveBeenCalledWith(targetUtubID);

    pushStateSpy.mockRestore();
  });

  it("(g5) restoreCrossUtubSearchFromHistory re-opens the mode and re-runs the saved query with its fields", async () => {
    const { ajaxCall } = await import("../../../lib/ajax.js");
    (ajaxCall as unknown as ReturnType<typeof vi.fn>).mockReturnValue(
      buildDoneXhr([]),
    );
    const { initCrossUtubSearch, restoreCrossUtubSearchFromHistory } =
      await import("../cross-utub-search.js");
    initCrossUtubSearch();

    restoreCrossUtubSearchFromHistory({ query: "dogs", fields: ["title"] });

    // Mode is visible, the input carries the restored query, and the query is
    // re-fetched immediately with the saved (non-default) field order applied.
    expect($("#crossUtubSearchMode").hasClass("cross-search-visible")).toBe(
      true,
    );
    expect($("#crossUtubSearchInput").val()).toBe("dogs");
    expect(ajaxCall).toHaveBeenCalledTimes(1);
    const calledUrl = (ajaxCall as unknown as ReturnType<typeof vi.fn>).mock
      .calls[0][1] as string;
    expect(calledUrl).toContain("q=dogs");
    expect(calledUrl).toContain("fields=title");
  });

  // render.js is mocked, so each result-access test builds the card DOM by
  // hand: a live URL text link (.crossSearchUrl) and the corner go-to icon
  // (.crossSearchGoTo), both http hrefs, nested inside a result card.
  function buildResultCardWithLinks(): void {
    $("#crossUtubSearchResults").html(
      `<div class="crossSearchHitCard" data-utub-id="7" data-utub-url-id="42">` +
        `<a class="crossSearchUrl" href="https://example.com" target="_blank" rel="noopener noreferrer">https://example.com</a>` +
        `<a class="crossSearchGoTo" href="https://example.com" target="_blank" rel="noopener noreferrer" aria-label="Open this URL in a new tab"></a>` +
        `</div>`,
    );
  }

  it("(j) clicking the result URL text emits RESULT_ACCESS with the url_text trigger and does not navigate", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");
    const { selectUTub } = await import("../../utubs/selectors.js");
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();
    (emit as unknown as ReturnType<typeof vi.fn>).mockClear();

    buildResultCardWithLinks();
    $(".crossSearchUrl").trigger("click");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_CROSS_UTUB_SEARCH_RESULT_ACCESS,
      target: CROSS_UTUB_SEARCH_RESULT_ACCESS_TARGET.CROSS_UTUB,
      trigger: CROSS_UTUB_SEARCH_RESULT_ACCESS_TRIGGER.URL_TEXT,
    });
    // The URL handler stops propagation, so the card's navigate handler never
    // runs and the source UTub is not selected.
    expect(selectUTub).not.toHaveBeenCalled();
  });

  it("(k) clicking the corner go-to icon emits RESULT_ACCESS with the corner_button trigger and does not navigate", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");
    const { selectUTub } = await import("../../utubs/selectors.js");
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();
    (emit as unknown as ReturnType<typeof vi.fn>).mockClear();

    buildResultCardWithLinks();
    $(".crossSearchGoTo").trigger("click");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_CROSS_UTUB_SEARCH_RESULT_ACCESS,
      target: CROSS_UTUB_SEARCH_RESULT_ACCESS_TARGET.CROSS_UTUB,
      trigger: CROSS_UTUB_SEARCH_RESULT_ACCESS_TRIGGER.CORNER_BUTTON,
    });
    // The corner-icon handler stops propagation, so the card's navigate handler
    // never runs and the source UTub is not selected.
    expect(selectUTub).not.toHaveBeenCalled();
  });
});
