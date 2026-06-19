import { $, getInputValue } from "../../lib/globals.js";
import { KEYS, TABLET_WIDTH } from "../../lib/constants.js";
import { APP_CONFIG } from "../../lib/config.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { emit as recordUIEvent } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import {
  CROSS_UTUB_SEARCH_OPEN_TARGET,
  CROSS_UTUB_SEARCH_RESULT_ACCESS_TARGET,
} from "../../types/metrics-dim-values.js";
import { AppEvents, on } from "../../lib/event-bus.js";
import { getState } from "../../store/app-store.js";
import {
  isMobile,
  setMobileUIWhenUTubSelectedOrURLNavSelected,
  setMobileUIWhenUTubNotSelectedOrUTubDeleted,
} from "../mobile.js";
import { selectURLCard } from "../urls/cards/selection.js";
import { buildUTubDeck } from "../utubs/deck.js";
import { resetUTubSearch } from "../utubs/search.js";
import { selectUTub } from "../utubs/selectors.js";
import { getAllUTubs } from "../utubs/utils.js";
import { renderSearchResults } from "./render.js";
import {
  getSelectedFields,
  initFieldControls,
  setFieldControls,
} from "./field-controls.js";
import {
  clearSearchHistory,
  getSearchHistory,
  pushSearchHistory,
  removeSearchHistoryEntry,
} from "./search-history.js";

import type { SuccessResponse } from "../../types/api-helpers.d.ts";
import type { MatchedField } from "../../types/search.js";
import type { SearchHistoryEntry } from "./search-history.js";

type SearchResponse = SuccessResponse<"searchAcrossUtubs">;

const MAX_SEARCH_LENGTH = 500;
const SEARCH_DEBOUNCE_MS = 200;
// Matches the 0.3s opacity/visibility transition in cross-utub-search.css; the
// overlay's computed `visibility` stays `hidden` until the transition completes,
// so a focus attempt before then is a no-op. Used as the fallback delay when no
// transitionend fires (e.g. prefers-reduced-motion, or a missing transition).
const OVERLAY_TRANSITION_MS = 300;
// Default field order; when the user's selection equals this, `&fields=` is
// omitted from the request URL (backend defaults to url>title>tag).
const DEFAULT_FIELD_ORDER: MatchedField[] = ["url", "title", "tag"];

let _searchModeActive = false;
let _searchDebounceTimer: ReturnType<typeof setTimeout> | null = null;
let _breakpointQuery: MediaQueryList | null = null;
let _onBreakpointChange: (() => void) | null = null;

export function isCrossUtubSearchActive(): boolean {
  return _searchModeActive;
}

function clearResultStates(): void {
  $("#crossUtubSearchResults").empty();
  $("#crossUtubSearchNoResults").addClass("hidden").text("");
  $("#crossUtubSearchShortQuery").addClass("hidden").text("");
}

function showShortQueryState(): void {
  $("#crossUtubSearchResults").empty();
  $("#crossUtubSearchNoResults").addClass("hidden");
  $("#crossUtubSearchShortQuery")
    .text(APP_CONFIG.strings.CROSS_SEARCH_SHORT_QUERY)
    .removeClass("hidden");
}

function showNoResultsState(): void {
  $("#crossUtubSearchNoResults")
    .text(APP_CONFIG.strings.CROSS_SEARCH_NO_RESULTS)
    .removeClass("hidden");
}

function announceResultCount({
  count,
  utubs,
}: {
  count: number;
  utubs: number;
}): void {
  const text = APP_CONFIG.strings.CROSS_SEARCH_COUNT_TEMPLATE.replace(
    "{{ count }}",
    String(count),
  ).replace("{{ utubs }}", String(utubs));
  $("#crossUtubSearchAnnouncement").text(text);
}

function isDefaultFieldOrder(fields: MatchedField[]): boolean {
  return (
    fields.length === DEFAULT_FIELD_ORDER.length &&
    fields.every((field, index) => field === DEFAULT_FIELD_ORDER[index])
  );
}

export function performCrossUtubSearch({
  query,
  fields,
}: {
  query: string;
  fields: MatchedField[];
}): void {
  const trimmed = query.trim();
  if (trimmed.length === 0) {
    showShortQueryState();
    return;
  }

  let url = `${APP_CONFIG.routes.crossUtubSearch}?q=${encodeURIComponent(trimmed)}`;
  // Single comma-delimited ordered param (NOT repeated keys); omit when default.
  if (!isDefaultFieldOrder(fields)) {
    url += "&fields=" + fields.join(",");
  }

  ajaxCall("GET", url, null)
    .done((data: SearchResponse) => {
      $("#crossUtubSearchShortQuery").addClass("hidden");
      renderSearchResults({ results: data.results, query: trimmed });
      if (data.results.length === 0) {
        showNoResultsState();
      } else {
        $("#crossUtubSearchNoResults").addClass("hidden");
      }
      const totalHits = data.results.reduce(
        (sum, group) => sum + group.urls.length,
        0,
      );
      announceResultCount({ count: totalHits, utubs: data.results.length });
      pushSearchHistory({ query: trimmed, fields });
    })
    .fail((xhr: JQuery.jqXHR) => {
      if (is429Handled(xhr)) return;
      // A same-origin 302 to the login page is followed by the browser and
      // surfaces in jqXHR as status 0 with an empty body; the HTML-body check
      // is unreliable for browser-followed redirects, so gate on status alone.
      if (xhr.status === 0) return;
      if (xhr.status === 400) {
        showNoResultsState();
      }
    });
}

// One history entry as an <li> holding two sibling buttons: a re-run button (the
// query text) and a small trash button to delete just that entry. The buttons
// are siblings (not nested — a button cannot contain a button).
function buildHistoryRow(entry: SearchHistoryEntry): JQuery<HTMLElement> {
  const item = $(document.createElement("li")).addClass(
    "crossSearchHistoryItem",
  );

  const row = $(document.createElement("button"))
    .addClass("crossSearchHistoryRow")
    .attr("type", "button")
    .attr("aria-label", "Re-run search for " + entry.query);

  $(document.createElement("span"))
    .addClass("crossSearchHistoryQuery")
    .attr("title", entry.query)
    .text(entry.query)
    .appendTo(row);

  row.on("click", () => {
    $("#crossUtubSearchInput").val(entry.query);
    // The input now has text — surface the clear (×) button to match.
    syncClearButtonVisibility();
    $("#crossUtubSearchHistoryList").remove();
    // Reflect the saved field order/selection in the controls UI; this also
    // re-triggers the search via the controls' onChange, so we still call
    // performCrossUtubSearch explicitly to honor the saved fields directly.
    setFieldControls({ fields: entry.fields });
    performCrossUtubSearch({ query: entry.query, fields: entry.fields });
  });

  const deleteButton = $(document.createElement("button"))
    .addClass("crossSearchHistoryDelete")
    .attr("type", "button")
    .attr("aria-label", "Remove " + entry.query + " from recent searches")
    .html(
      '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-trash3-fill" viewBox="0 0 16 16"><path d="M11 1.5v1h3.5a.5.5 0 0 1 0 1h-.538l-.853 10.66A2 2 0 0 1 11.115 16h-6.23a2 2 0 0 1-1.994-1.84L2.038 3.5H1.5a.5.5 0 0 1 0-1H5v-1A1.5 1.5 0 0 1 6.5 0h3A1.5 1.5 0 0 1 11 1.5m-5 0v1h4v-1a.5.5 0 0 0-.5-.5h-3a.5.5 0 0 0-.5.5M4.5 5.029l.5 8.5a.5.5 0 1 0 .998-.06l-.5-8.5a.5.5 0 1 0-.998.06m6.53-.528a.5.5 0 0 0-.528.47l-.5 8.5a.5.5 0 0 0 .998.058l.5-8.5a.5.5 0 0 0-.47-.528M8 4.5a.5.5 0 0 0-.5.5v8.5a.5.5 0 0 0 1 0V5a.5.5 0 0 0-.5-.5"/></svg>',
    );

  deleteButton.on("click", () => {
    removeSearchHistoryEntry({ query: entry.query, fields: entry.fields });
    item.remove();
    if ($(".crossSearchHistoryItem").length === 0) {
      $("#crossUtubSearchHistoryList").remove();
    }
  });

  row.appendTo(item);
  deleteButton.appendTo(item);

  return item;
}

function renderSearchHistory(): void {
  const history = getSearchHistory();
  const inputValue = getInputValue($("#crossUtubSearchInput")).trim();
  if (history.length === 0 || inputValue.length > 0) return;

  const section = $(document.createElement("section"))
    .attr("id", "crossUtubSearchHistoryList")
    .attr("aria-labelledby", "crossUtubSearchHistoryHeading");

  // Heading + Clear share a single header row (title left, Clear right).
  const header = $(document.createElement("div")).addClass(
    "crossSearchHistoryHeader",
  );

  $(document.createElement("h3"))
    .attr("id", "crossUtubSearchHistoryHeading")
    .text(APP_CONFIG.strings.CROSS_SEARCH_HISTORY_HEADING)
    .appendTo(header);

  $(document.createElement("button"))
    .attr("id", "crossUtubSearchHistoryClear")
    .attr("type", "button")
    .attr("aria-label", "Clear search history")
    .text(APP_CONFIG.strings.CROSS_SEARCH_HISTORY_CLEAR)
    .on("click", () => {
      clearSearchHistory();
      $("#crossUtubSearchHistoryList").remove();
    })
    .appendTo(header);

  header.appendTo(section);

  const list = $(document.createElement("ul")).addClass(
    "crossSearchHistoryItems",
  );
  history.forEach((entry) => {
    buildHistoryRow(entry).appendTo(list);
  });
  list.appendTo(section);

  $("#crossUtubSearchResults").prepend(section);
}

// The overlay reveals via a `visibility` transition, whose computed value stays
// `hidden` until the transition finishes — focusing the input before then is a
// no-op. Wait for the overlay's transitionend (with a timeout fallback so the
// focus still lands under prefers-reduced-motion or if no transition runs), then
// focus the input.
function focusSearchInputAfterReveal(): void {
  const overlay = $("#crossUtubSearchMode");
  const input = document.getElementById("crossUtubSearchInput");
  if (input === null) return;

  let focused = false;
  const focusInput = (): void => {
    if (focused) return;
    focused = true;
    overlay.off("transitionend.crossSearchFocus");
    input.focus();
  };

  overlay
    .off("transitionend.crossSearchFocus")
    .on("transitionend.crossSearchFocus", (event: JQuery.TriggeredEvent) => {
      const nativeEvent = event.originalEvent as TransitionEvent | undefined;
      if (nativeEvent?.propertyName === "visibility") {
        focusInput();
      }
    });
  // Fallback: no transitionend (reduced motion / no transition) — focus anyway.
  setTimeout(focusInput, OVERLAY_TRANSITION_MS);
}

export function enterCrossUtubSearchMode(): void {
  if (_searchModeActive) return;
  _searchModeActive = true;

  recordUIEvent({
    event: UI_EVENTS.UI_CROSS_UTUB_SEARCH_OPEN,
    target: CROSS_UTUB_SEARCH_OPEN_TARGET.CROSS_UTUB,
  });

  // Hide the left panel (UTub/Member/Tag decks) and clear any stale in-deck
  // filter. Mobile: hide the four deck-switcher buttons.
  $("#leftPanel").addClass("hidden");
  resetUTubSearch();
  if (isMobile()) {
    $("#toUTubs").addClass("hidden");
    $("#toURLs").addClass("hidden");
    $("#toMembers").addClass("hidden");
    $("#toTags").addClass("hidden");
  }

  $("#crossUtubSearchMode")
    .removeClass("cross-search-hidden")
    .addClass("cross-search-visible");

  clearResultStates();
  renderSearchHistory();
  focusSearchInputAfterReveal();
}

export function exitCrossUtubSearchMode(): void {
  $("#crossUtubSearchInput").off("keydown.crossSearchInputEsc");
  if (!_searchModeActive) {
    $("#crossUtubSearchMode")
      .removeClass("cross-search-visible")
      .addClass("cross-search-hidden");
    return;
  }
  _searchModeActive = false;

  if (_searchDebounceTimer !== null) {
    clearTimeout(_searchDebounceTimer);
    _searchDebounceTimer = null;
  }

  recordUIEvent({
    event: UI_EVENTS.UI_CROSS_UTUB_SEARCH_CLOSE,
    target: CROSS_UTUB_SEARCH_OPEN_TARGET.CROSS_UTUB,
  });

  $("#crossUtubSearchMode")
    .removeClass("cross-search-visible")
    .addClass("cross-search-hidden");

  // Restore the LHS via the existing layout helpers. Do NOT clear
  // activeUTubID/selectedURLCardID — clearing flips downstream selection state.
  // Un-hide #leftPanel first: enterCrossUtubSearchMode() added `.hidden` to it,
  // but the mobile no-UTub helper (setMobileUIWhenUTubNotSelectedOrUTubDeleted)
  // only toggles the decks, not the panel, so without this the panel stays
  // hidden and the user lands on an empty screen. The with-UTub mobile helper
  // re-hides #leftPanel itself to surface the URL deck, so this is safe.
  $("#leftPanel").removeClass("hidden");
  if (isMobile()) {
    if (getState().activeUTubID !== null) {
      setMobileUIWhenUTubSelectedOrURLNavSelected();
    } else {
      setMobileUIWhenUTubNotSelectedOrUTubDeleted();
    }
  }

  // Reset the input and result states so the next open starts fresh — an empty
  // input lets renderSearchHistory() surface the recent-searches list.
  $("#crossUtubSearchInput").val("");
  $("#crossUtubSearchClear").addClass("hidden");
  clearResultStates();

  $("#toCrossUtubSearch").trigger("focus");
}

function clearSearchInput(): void {
  if (_searchDebounceTimer !== null) {
    clearTimeout(_searchDebounceTimer);
    _searchDebounceTimer = null;
  }
  $("#crossUtubSearchInput").val("");
  $("#crossUtubSearchClear").addClass("hidden");
  clearResultStates();
  renderSearchHistory();
  $("#crossUtubSearchInput").trigger("focus");
}

// Show the clear (×) button whenever the input has text, hide it when empty.
// Called from the input handler and from any path that sets the input value
// programmatically (e.g. re-running a recent search).
function syncClearButtonVisibility(): void {
  const hasText = getInputValue($("#crossUtubSearchInput")).length > 0;
  $("#crossUtubSearchClear").toggleClass("hidden", !hasText);
  // Only reserve the input's right padding for the clear button when text is
  // present, so the placeholder isn't clipped while empty.
  $("#crossUtubSearchInput").toggleClass("crossSearchHasText", hasText);
}

function handleSearchInput(): void {
  if (_searchDebounceTimer !== null) {
    clearTimeout(_searchDebounceTimer);
    _searchDebounceTimer = null;
  }

  const input = $("#crossUtubSearchInput");
  const rawValue = getInputValue(input);
  syncClearButtonVisibility();
  if (rawValue.length > MAX_SEARCH_LENGTH) {
    input.val(rawValue.slice(0, MAX_SEARCH_LENGTH));
    return;
  }

  const query = rawValue.trim();
  if (query === "") {
    clearResultStates();
    renderSearchHistory();
    return;
  }

  // History only shows for an empty input; a typed query supersedes it.
  $("#crossUtubSearchHistoryList").remove();

  _searchDebounceTimer = setTimeout(() => {
    _searchDebounceTimer = null;
    performCrossUtubSearch({ query, fields: getSelectedFields() });
  }, SEARCH_DEBOUNCE_MS);
}

// Navigate from a search result card to its source UTub and highlight the
// matched URL card. The URL deck is rebuilt asynchronously by selectUTub, so
// the target .urlRow does not exist until AppEvents.UTUB_SELECTED fires — defer
// selectURLCard until that event (one-shot), never synchronously after
// selectUTub.
function navigateToHit({
  utubID,
  utubUrlID,
}: {
  utubID: number;
  utubUrlID: number;
}): void {
  exitCrossUtubSearchMode();

  // Deck already built for this UTub: select the card directly.
  if (getState().activeUTubID === utubID) {
    selectURLCard($(`.urlRow[utuburlid=${utubUrlID}]`));
    return;
  }

  // One-shot: unsubscribe first so it fires exactly once even if the handler
  // throws.
  const unsubscribe = on(AppEvents.UTUB_SELECTED, () => {
    unsubscribe();
    selectURLCard($(`.urlRow[utuburlid=${utubUrlID}]`));
  });

  const utubSelector = $(`.UTubSelector[utubid=${utubID}]`);
  if (utubSelector.length > 0) {
    selectUTub(utubID, utubSelector);
    return;
  }

  // The selector is missing only in a race where the user was added to a UTub
  // and searched before the deck reloaded — trust the search result and rebuild
  // the deck, then select.
  getAllUTubs().then((utubData) => {
    buildUTubDeck(utubData.utubs);
    const rebuiltSelector = $(`.UTubSelector[utubid=${utubID}]`);
    if (rebuiltSelector.length > 0) {
      selectUTub(utubID, rebuiltSelector);
    }
  });
}

export function initCrossUtubSearch(): void {
  $("#crossUtubSearchInput").attr(
    "placeholder",
    APP_CONFIG.strings.CROSS_SEARCH_PLACEHOLDER,
  );

  // The navbar trigger toggles search mode: tapping the magnifying glass again
  // while search is open closes it (mirrors the ✕/ESC close).
  $("#toCrossUtubSearch").offAndOnExact("click.crossSearch", () => {
    if (_searchModeActive) {
      exitCrossUtubSearchMode();
    } else {
      enterCrossUtubSearchMode();
    }
  });

  // Delegated result-card clicks: leave search mode and navigate to the source
  // UTub with the matched URL card highlighted. offAndOn does not support the
  // delegated-selector form, so use off().on() directly for the delegation.
  $("#crossUtubSearchResults")
    .off("click.crossSearch")
    .on(
      "click.crossSearch",
      ".crossSearchHitCard",
      (event: JQuery.TriggeredEvent) => {
        const card = $(event.currentTarget);
        const utubID = parseInt(card.attr("data-utub-id")!, 10);
        const utubUrlID = parseInt(card.attr("data-utub-url-id")!, 10);
        navigateToHit({ utubID, utubUrlID });
      },
    );
  $("#crossUtubSearchResults")
    .off("click.crossSearchUrl")
    .on(
      "click.crossSearchUrl",
      ".crossSearchUrl",
      (event: JQuery.TriggeredEvent) => {
        const link = $(event.currentTarget);
        // Only live (http/https) links have an href; a non-openable URL falls
        // through to the card's navigate-to-source-UTub handler.
        if (!link.attr("href")) return;
        // Tapping the URL opens it (target=_blank) — keep it from bubbling to
        // the card's navigate handler, and record the access.
        event.stopPropagation();
        recordUIEvent({
          event: UI_EVENTS.UI_CROSS_UTUB_SEARCH_RESULT_ACCESS,
          target: CROSS_UTUB_SEARCH_RESULT_ACCESS_TARGET.CROSS_UTUB,
        });
      },
    );
  $("#crossUtubSearchSettingsBtn").offAndOnExact("click.crossSearch", () =>
    $("#crossUtubSearchSettingsModal").modal("show"),
  );
  $("#crossUtubSearchClose").offAndOnExact("click.crossSearch", () =>
    exitCrossUtubSearchMode(),
  );
  $("#crossUtubSearchClear").offAndOnExact("click.crossSearch", () =>
    clearSearchInput(),
  );

  $("#crossUtubSearchInput").offAndOn("input.crossSearch", handleSearchInput);

  // Field-select + ordering controls. A change re-runs the search against the
  // current input value with the new field selection/order; the empty-query
  // guard inside performCrossUtubSearch short-circuits when nothing is typed.
  initFieldControls({
    onChange: (fields: MatchedField[]) => {
      const query = getInputValue($("#crossUtubSearchInput")).trim();
      if (query === "") return;
      performCrossUtubSearch({ query, fields });
    },
  });

  // Cmd/Ctrl+K opens — only when not typing in a field, no modal is open, and
  // search mode is not already active.
  $(document).offAndOn(
    "keydown.crossSearchOpen",
    (event: JQuery.TriggeredEvent) => {
      if (!(event.metaKey || event.ctrlKey)) return;
      if (typeof event.key !== "string" || event.key.toLowerCase() !== KEYS.K) {
        return;
      }
      const active = document.activeElement;
      const tag = active?.tagName;
      if (
        tag === "INPUT" ||
        tag === "TEXTAREA" ||
        (active as HTMLElement | null)?.isContentEditable
      ) {
        return;
      }
      if ($(".modal.show").length > 0) return;
      if (_searchModeActive) return;
      event.preventDefault();
      enterCrossUtubSearchMode();
    },
  );

  // ESC closes — only while active and no Bootstrap modal owns ESC.
  $(document).offAndOn(
    "keydown.crossSearchEsc",
    (event: JQuery.TriggeredEvent) => {
      if (event.key !== KEYS.ESCAPE) return;
      if (!_searchModeActive) return;
      if ($(".modal.show").length > 0) return;
      exitCrossUtubSearchMode();
    },
  );

  // Crossing the mobile/desktop breakpoint while open: cancel any pending
  // fetch, drop search-mode state, hide the overlay, and restore focus to the
  // trigger. mobile.ts owns ALL panel layout, so do NOT call
  // exitCrossUtubSearchMode() here (avoids listener registration-order coupling).
  if (_breakpointQuery !== null && _onBreakpointChange !== null) {
    _breakpointQuery.removeEventListener("change", _onBreakpointChange);
  }
  _breakpointQuery = matchMedia("(max-width: " + TABLET_WIDTH + "px)");
  _onBreakpointChange = () => {
    if (!_searchModeActive) return;
    if (_searchDebounceTimer !== null) {
      clearTimeout(_searchDebounceTimer);
      _searchDebounceTimer = null;
    }
    _searchModeActive = false;
    $("#crossUtubSearchMode")
      .removeClass("cross-search-visible")
      .addClass("cross-search-hidden");
    $("#toCrossUtubSearch").trigger("focus");
  };
  _breakpointQuery.addEventListener("change", _onBreakpointChange);

  if (getState().utubs.length > 0) {
    $("#toCrossUtubSearch").removeClass("hidden");
  }
}
