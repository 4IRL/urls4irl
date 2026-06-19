import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { APP_CONFIG } from "../../../lib/config.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import {
  CROSS_UTUB_SEARCH_OPEN_TARGET,
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
  <button id="toCrossUtubSearch" class="hidden"></button>
  <div id="leftPanel" class="panel"></div>
  <button id="toUTubs"></button>
  <button id="toURLs"></button>
  <button id="toMembers"></button>
  <button id="toTags"></button>
  <div id="crossUtubSearchMode" class="cross-search-hidden">
    <div id="crossUtubSearchInputWrap"><input id="crossUtubSearchInput" type="search" /><button id="crossUtubSearchClear" class="hidden"></button></div>
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
      query: "alpha",
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

  it("(h) clicking the navbar trigger while open toggles the mode closed", async () => {
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
      target: CROSS_UTUB_SEARCH_OPEN_TARGET.CROSS_UTUB,
    });
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
