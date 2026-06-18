import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { APP_CONFIG } from "../../../lib/config.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { CROSS_UTUB_SEARCH_OPEN_TARGET } from "../../../types/metrics-dim-values.js";

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

const $ = window.jQuery;

const SEARCH_MODE_HTML = `
  <button id="toCrossUtubSearch" class="hidden"></button>
  <div id="leftPanel" class="panel"></div>
  <button id="toUTubs"></button>
  <button id="toURLs"></button>
  <button id="toMembers"></button>
  <button id="toTags"></button>
  <div id="crossUtubSearchMode" class="cross-search-hidden">
    <input id="crossUtubSearchInput" type="search" />
    <div id="crossUtubSearchFieldControls"></div>
    <button id="crossUtubSearchClose"></button>
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
  } as unknown as JQuery.jqXHR;
}

describe("cross-utub-search — mode mechanics", () => {
  beforeEach(async () => {
    document.body.innerHTML = SEARCH_MODE_HTML;
    vi.clearAllMocks();
    // Reset module-scoped search-mode state between tests.
    const { exitCrossUtubSearchMode } = await import("../cross-utub-search.js");
    exitCrossUtubSearchMode();
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

  it("(b) debounced input fetches once with the right URL and renders results", async () => {
    vi.useFakeTimers();
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

    const input = $("#crossUtubSearchInput");
    input.val("alpha").trigger("input");
    vi.advanceTimersByTime(250);

    expect(ajaxCall).toHaveBeenCalledTimes(1);
    const calledUrl = (ajaxCall as unknown as ReturnType<typeof vi.fn>).mock
      .calls[0][1] as string;
    expect(calledUrl).toBe(`${APP_CONFIG.routes.crossUtubSearch}?q=alpha`);
    expect(renderSearchResults).toHaveBeenCalledWith({
      results: [{ utubID: 1, utubName: "A", urls: [] }],
    });
  });

  it("(c) empty result set shows the no-results state", async () => {
    vi.useFakeTimers();
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
    vi.advanceTimersByTime(250);

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
    vi.advanceTimersByTime(250);

    expect(renderSearchResults).not.toHaveBeenCalled();
    expect($("#crossUtubSearchNoResults").hasClass("hidden")).toBe(true);
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
      target: CROSS_UTUB_SEARCH_OPEN_TARGET.CROSS_UTUB,
    });
  });

  it("(f) clicking the ✕ button closes the mode and emits CLOSE", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");
    const { initCrossUtubSearch, enterCrossUtubSearchMode } = await import(
      "../cross-utub-search.js"
    );
    initCrossUtubSearch();
    enterCrossUtubSearchMode();
    (emit as unknown as ReturnType<typeof vi.fn>).mockClear();

    $("#crossUtubSearchClose").trigger("click");

    const mode = $("#crossUtubSearchMode");
    expect(mode.hasClass("cross-search-hidden")).toBe(true);
    expect(mode.hasClass("cross-search-visible")).toBe(false);
    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_CROSS_UTUB_SEARCH_CLOSE,
      target: CROSS_UTUB_SEARCH_OPEN_TARGET.CROSS_UTUB,
    });
  });
});
