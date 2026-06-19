import { $, getInputValue } from "../../lib/globals.js";
import { KEYS, TABLET_WIDTH } from "../../lib/constants.js";
import { APP_CONFIG } from "../../lib/config.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { emit as recordUIEvent } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import {
  CROSS_UTUB_SEARCH_CLOSE_TARGET,
  CROSS_UTUB_SEARCH_CLOSE_TRIGGER,
  CROSS_UTUB_SEARCH_OPEN_TARGET,
  CROSS_UTUB_SEARCH_REFRESH_TARGET,
  CROSS_UTUB_SEARCH_RESULT_ACCESS_TARGET,
  CROSS_UTUB_SEARCH_RESULT_ACCESS_TRIGGER,
} from "../../types/metrics-dim-values.js";
import { AppEvents, on } from "../../lib/event-bus.js";
import { getState } from "../../store/app-store.js";
import { setSearchModeActive } from "../left-panel-toggle.js";
import {
  isMobile,
  setMobileUIWhenUTubSelectedOrURLNavSelected,
  setMobileUIWhenUTubNotSelectedOrUTubDeleted,
} from "../mobile.js";
import { selectURLCard } from "../urls/cards/selection.js";
import { buildUTubDeck } from "../utubs/deck.js";
import { resetUTubSearch } from "../utubs/search.js";
import { pushUTubHistoryState, selectUTub } from "../utubs/selectors.js";
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
// Default field order; when the user's selection equals this, `&fields=` is
// omitted from the request URL (backend defaults to url>title>tag).
const DEFAULT_FIELD_ORDER: MatchedField[] = ["url", "title", "tag"];

type CrossSearchCloseTrigger =
  (typeof CROSS_UTUB_SEARCH_CLOSE_TRIGGER)[keyof typeof CROSS_UTUB_SEARCH_CLOSE_TRIGGER];

let _searchModeActive = false;
// Signature (query + field order) of the last query actually submitted this open.
// Drives the submit button's Search<->Refresh morph: when the current input
// equals this, the next submit is a Refresh (re-run for fresh results); when it
// differs (or nothing has been submitted), it is a Search. `null` means nothing
// submitted yet this open.
let _lastSubmitted: string | null = null;
let _breakpointQuery: MediaQueryList | null = null;
let _onBreakpointChange: (() => void) | null = null;

// Stable identity for a submitted search. The leading query length makes the
// query/fields boundary unambiguous, so distinct (query, fields) pairs can never
// collapse to the same signature even when the query itself contains a colon.
function submissionSignature({
  query,
  fields,
}: {
  query: string;
  fields: MatchedField[];
}): string {
  const trimmed = query.trim();
  return `${trimmed.length}:${trimmed}:${fields.join(",")}`;
}

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

// Reflect the submit button's two states. Empty input -> disabled (a fixed,
// discoverable slot rather than a layout-shifting hide). Non-empty: Refresh when
// the current query+fields match the last submitted search (re-run for fresh
// results), otherwise Search. Single source of truth — every path that changes
// the input or `_lastSubmitted` calls this.
function updateSubmitButtonState(): void {
  const button = $("#crossUtubSearchSubmit");
  const query = getInputValue($("#crossUtubSearchInput")).trim();

  if (query === "") {
    button
      .prop("disabled", true)
      .attr("aria-label", APP_CONFIG.strings.CROSS_SEARCH_SUBMIT_LABEL);
    button.find(".crossSearchSubmitIcon").removeClass("hidden");
    button.find(".crossSearchRefreshIcon").addClass("hidden");
    return;
  }

  const isRefresh =
    _lastSubmitted !== null &&
    submissionSignature({ query, fields: getSelectedFields() }) ===
      _lastSubmitted;

  button
    .prop("disabled", false)
    .attr(
      "aria-label",
      isRefresh
        ? APP_CONFIG.strings.CROSS_SEARCH_REFRESH_LABEL
        : APP_CONFIG.strings.CROSS_SEARCH_SUBMIT_LABEL,
    );
  button.find(".crossSearchSubmitIcon").toggleClass("hidden", isRefresh);
  button.find(".crossSearchRefreshIcon").toggleClass("hidden", !isRefresh);
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

  // Record the submitted identity synchronously so the button morphs to Refresh
  // immediately (not gated on the network); this is the single place the morph
  // flips, so the restore / recent-rerun / field-change paths stay truthful too.
  _lastSubmitted = submissionSignature({ query: trimmed, fields });
  updateSubmitButtonState();

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

// Run the current query. Shared by the submit button and the Enter key. A Refresh
// (current query+fields unchanged since the last submit) records its own metric
// before re-running; a first/changed Search just runs.
function submitCurrentSearch(): void {
  const query = getInputValue($("#crossUtubSearchInput")).trim();
  if (query === "") return;
  const fields = getSelectedFields();

  const isRefresh =
    _lastSubmitted !== null &&
    submissionSignature({ query, fields }) === _lastSubmitted;
  if (isRefresh) {
    recordUIEvent({
      event: UI_EVENTS.UI_CROSS_UTUB_SEARCH_REFRESH,
      target: CROSS_UTUB_SEARCH_REFRESH_TARGET.CROSS_UTUB,
    });
  }

  performCrossUtubSearch({ query, fields });
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
    // Static SVG literal only — never interpolate user data here.
    .html(
      '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" fill="currentColor" class="bi bi-trash3-fill" viewBox="0 0 16 16"><path d="M11 1.5v1h3.5a.5.5 0 0 1 0 1h-.538l-.853 10.66A2 2 0 0 1 11.115 16h-6.23a2 2 0 0 1-1.994-1.84L2.038 3.5H1.5a.5.5 0 0 1 0-1H5v-1A1.5 1.5 0 0 1 6.5 0h3A1.5 1.5 0 0 1 11 1.5m-5 0v1h4v-1a.5.5 0 0 0-.5-.5h-3a.5.5 0 0 0-.5.5M4.5 5.029l.5 8.5a.5.5 0 1 0 .998-.06l-.5-8.5a.5.5 0 1 0-.998.06m6.53-.528a.5.5 0 0 0-.528.47l-.5 8.5a.5.5 0 0 0 .998.058l.5-8.5a.5.5 0 0 0-.47-.528M8 4.5a.5.5 0 0 0-.5.5v8.5a.5.5 0 0 0 1 0V5a.5.5 0 0 0-.5-.5"/></svg>',
    );

  deleteButton.on("click", () => {
    removeSearchHistoryEntry({ query: entry.query });
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

// Swap the navbar trigger between its open (magnifying glass / "Search") and
// close (glass-with-X / "Close") states and update its aria-label. The header ✕
// was removed; the trigger itself is now the in-overlay close affordance.
function setTriggerToOpenState(): void {
  $("#crossSearchTriggerOpenIcon").removeClass("hidden");
  $("#crossSearchTriggerCloseIcon").addClass("hidden");
  $("#toCrossUtubSearch")
    .removeClass("navbar-cross-search--active")
    .attr("aria-label", APP_CONFIG.strings.CROSS_SEARCH_TRIGGER_OPEN_LABEL);
}

function setTriggerToCloseState(): void {
  $("#crossSearchTriggerOpenIcon").addClass("hidden");
  $("#crossSearchTriggerCloseIcon").removeClass("hidden");
  // The bordered "--active" styling calls out the Close affordance while open.
  $("#toCrossUtubSearch")
    .addClass("navbar-cross-search--active")
    .attr("aria-label", APP_CONFIG.strings.CROSS_SEARCH_TRIGGER_CLOSE_LABEL);
}

export function enterCrossUtubSearchMode(): void {
  if (_searchModeActive) return;
  _searchModeActive = true;

  recordUIEvent({
    event: UI_EVENTS.UI_CROSS_UTUB_SEARCH_OPEN,
    target: CROSS_UTUB_SEARCH_OPEN_TARGET.CROSS_UTUB,
  });

  // Hide the left panel (UTub/Member/Tag decks) via the shared resolver so a
  // manual collapse is preserved, and clear any stale in-deck filter. Mobile:
  // hide the four deck-switcher buttons.
  setSearchModeActive({ active: true });
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

  setTriggerToCloseState();
  // Surface the hamburger "Return Home" exit (the labeled way out while search
  // is open — the only one reachable on mobile, where the deck-switchers above
  // are hidden during search).
  $("#navReturnHome").removeClass("hidden");

  clearResultStates();
  renderSearchHistory();
  updateSubmitButtonState();
  // Focus synchronously inside the opening gesture so the mobile soft keyboard
  // rises. The reveal CSS flips `visibility` to visible immediately (only the
  // opacity/transform animate), so the input is focusable in this same frame;
  // iOS only raises the keyboard from a gesture-synchronous focus, never a
  // deferred one.
  document.getElementById("crossUtubSearchInput")?.focus();
}

// Re-opens cross-UTub search mode from a browser-history entry (see
// pushCrossUtubSearchHistoryState) and re-runs the saved query so the browser
// Back button returns the user to their previous search results.
export function restoreCrossUtubSearchFromHistory({
  query,
  fields,
}: {
  query: string;
  fields: MatchedField[];
}): void {
  enterCrossUtubSearchMode();
  // Apply the saved field order BEFORE filling the input: setFieldControls fires
  // the controls' onChange, which would re-run the search — harmless but wasteful
  // on every Back. With the input still empty, that onChange short-circuits, so
  // the single explicit performCrossUtubSearch below is the only fetch.
  setFieldControls({ fields });
  $("#crossUtubSearchInput").val(query);
  syncClearButtonVisibility();
  // The recent-search list only shows for an empty input; a restored query
  // supersedes it.
  $("#crossUtubSearchHistoryList").remove();
  performCrossUtubSearch({ query, fields });
}

export function exitCrossUtubSearchMode({
  trigger,
}: {
  trigger: CrossSearchCloseTrigger;
}): void {
  $("#crossUtubSearchInput").off("keydown.crossSearchInputEsc");
  if (!_searchModeActive) {
    $("#crossUtubSearchMode")
      .removeClass("cross-search-visible")
      .addClass("cross-search-hidden");
    setTriggerToOpenState();
    $("#navReturnHome").addClass("hidden");
    return;
  }
  _searchModeActive = false;

  recordUIEvent({
    event: UI_EVENTS.UI_CROSS_UTUB_SEARCH_CLOSE,
    target: CROSS_UTUB_SEARCH_CLOSE_TARGET.CROSS_UTUB,
    trigger,
  });

  $("#crossUtubSearchMode")
    .removeClass("cross-search-visible")
    .addClass("cross-search-hidden");
  setTriggerToOpenState();
  $("#navReturnHome").addClass("hidden");

  // Restore the LHS via the shared resolver. Do NOT clear
  // activeUTubID/selectedURLCardID — clearing flips downstream selection state.
  // Releasing search mode lets the resolver re-derive visibility: it restores
  // the LHS unless the user had manually collapsed it (userCollapsedLHS), so a
  // manual collapse is no longer clobbered. On mobile this also removes the
  // `.hidden` class enterCrossUtubSearchMode() added, since the mobile no-UTub
  // helper (setMobileUIWhenUTubNotSelectedOrUTubDeleted) only toggles the decks,
  // not the panel; the with-UTub mobile helper re-hides #leftPanel itself to
  // surface the URL deck, so this is safe.
  setSearchModeActive({ active: false });
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
  _lastSubmitted = null;
  updateSubmitButtonState();

  $("#toCrossUtubSearch").trigger("focus");
}

function clearSearchInput(): void {
  $("#crossUtubSearchInput").val("");
  $("#crossUtubSearchClear").addClass("hidden");
  clearResultStates();
  renderSearchHistory();
  updateSubmitButtonState();
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

// Input changes no longer fetch — search fires only on an explicit submit (the
// button or Enter). This handler keeps the clear button, history list, and submit
// button state in sync with what's typed; the length cap is enforced here too.
function handleSearchInput(): void {
  const input = $("#crossUtubSearchInput");
  const rawValue = getInputValue(input);
  syncClearButtonVisibility();
  if (rawValue.length > MAX_SEARCH_LENGTH) {
    input.val(rawValue.slice(0, MAX_SEARCH_LENGTH));
    updateSubmitButtonState();
    return;
  }

  const query = rawValue.trim();
  if (query === "") {
    clearResultStates();
    renderSearchHistory();
    updateSubmitButtonState();
    return;
  }

  // History only shows for an empty input; a typed query supersedes it.
  $("#crossUtubSearchHistoryList").remove();
  updateSubmitButtonState();
}

// Navigate from a search result card to its source UTub and highlight the
// matched URL card. The URL deck is rebuilt asynchronously by selectUTub, so
// the target .urlRow does not exist until AppEvents.UTUB_SELECTED fires — defer
// selectURLCard until that event (one-shot), never synchronously after
// selectUTub.
// Records the current cross-UTub search (query + field selection) as a browser
// history entry so that, after navigating into a result's source UTub, the Back
// button returns to these results (re-running the query). Pushes nothing and
// returns false when there is no query to restore.
function pushCrossUtubSearchHistoryState(): boolean {
  const query = getInputValue($("#crossUtubSearchInput")).trim();
  if (query.length === 0) return false;
  window.history.pushState(
    { crossSearch: { query, fields: getSelectedFields() } },
    "",
    "/home",
  );
  return true;
}

function navigateToHit({
  utubID,
  utubUrlID,
}: {
  utubID: number;
  utubUrlID: number;
}): void {
  // Record the search results in browser history (beneath the UTub entry pushed
  // below) so the Back button returns to them.
  const recordedSearch = pushCrossUtubSearchHistoryState();

  exitCrossUtubSearchMode({
    trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.RESULT_NAV,
  });

  // Deck already built for this UTub: select the card directly.
  if (getState().activeUTubID === utubID) {
    // selectURLCard pushes no history of its own, so add the UTub entry
    // explicitly — otherwise Back would skip the search entry just recorded.
    if (recordedSearch) pushUTubHistoryState(utubID);
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
    if (rebuiltSelector.length === 0) {
      // UTub vanished between search and click; selectUTub will never fire the
      // one-shot UTUB_SELECTED listener, so unsubscribe it explicitly here.
      unsubscribe();
      return;
    }
    selectUTub(utubID, rebuiltSelector);
  });
}

// Shared handler for both result-access anchors (.crossSearchUrl text and
// .crossSearchGoTo corner icon). Only live (http/https) anchors carry an href;
// a non-openable URL falls through to the card's navigate handler. For an
// openable link, stop propagation (so the card's navigate-to-source-UTub
// handler never runs) and record the access with the supplied trigger.
function recordResultAccess({
  event,
  trigger,
}: {
  event: JQuery.TriggeredEvent;
  trigger: (typeof CROSS_UTUB_SEARCH_RESULT_ACCESS_TRIGGER)[keyof typeof CROSS_UTUB_SEARCH_RESULT_ACCESS_TRIGGER];
}): void {
  if (!$(event.currentTarget).attr("href")) return;
  event.stopPropagation();
  recordUIEvent({
    event: UI_EVENTS.UI_CROSS_UTUB_SEARCH_RESULT_ACCESS,
    target: CROSS_UTUB_SEARCH_RESULT_ACCESS_TARGET.CROSS_UTUB,
    trigger,
  });
}

export function initCrossUtubSearch(): void {
  $("#crossUtubSearchInput").attr(
    "placeholder",
    APP_CONFIG.strings.CROSS_SEARCH_PLACEHOLDER,
  );

  // The navbar trigger toggles search mode: tapping the (now morphed) close
  // glyph while search is open closes it (mirrors the ESC close).
  $("#toCrossUtubSearch").offAndOnExact("click.crossSearch", () => {
    if (_searchModeActive) {
      exitCrossUtubSearchMode({
        trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.TRIGGER_ICON,
      });
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
  // Both the URL text (.crossSearchUrl) and the top-right corner icon
  // (.crossSearchGoTo) open the same link in a new tab; they differ only by the
  // `trigger` dimension on the access metric. Only live (http/https) anchors
  // carry an href — a non-openable URL has neither, so the click falls through
  // to the card's navigate-to-source-UTub handler. Tapping an openable link
  // opens it (target=_blank) natively; we stop propagation so the card's
  // navigate handler never runs, then record the access with its trigger.
  $("#crossUtubSearchResults")
    .off("click.crossSearchUrl")
    .on(
      "click.crossSearchUrl",
      ".crossSearchUrl",
      (event: JQuery.TriggeredEvent) =>
        recordResultAccess({
          event,
          trigger: CROSS_UTUB_SEARCH_RESULT_ACCESS_TRIGGER.URL_TEXT,
        }),
    );
  $("#crossUtubSearchResults")
    .off("click.crossSearchGoTo")
    .on(
      "click.crossSearchGoTo",
      ".crossSearchGoTo",
      (event: JQuery.TriggeredEvent) =>
        recordResultAccess({
          event,
          trigger: CROSS_UTUB_SEARCH_RESULT_ACCESS_TRIGGER.CORNER_BUTTON,
        }),
    );
  $("#crossUtubSearchSettingsBtn").offAndOnExact("click.crossSearch", () =>
    $("#crossUtubSearchSettingsModal").modal("show"),
  );
  $("#crossUtubSearchSubmit").offAndOnExact("click.crossSearch", () =>
    submitCurrentSearch(),
  );
  $("#crossUtubSearchClear").offAndOnExact("click.crossSearch", () =>
    clearSearchInput(),
  );

  $("#crossUtubSearchInput").offAndOn("input.crossSearch", handleSearchInput);
  // Enter submits the current query (the keyboard equivalent of the submit
  // button). preventDefault stops any implicit form submission / native search.
  $("#crossUtubSearchInput").offAndOn(
    "keydown.crossSearchSubmit",
    (event: JQuery.TriggeredEvent) => {
      if (event.key !== KEYS.ENTER) return;
      event.preventDefault();
      submitCurrentSearch();
    },
  );

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
      const activeTagName = active?.tagName;
      if (
        activeTagName === "INPUT" ||
        activeTagName === "TEXTAREA" ||
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
      exitCrossUtubSearchMode({
        trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.ESCAPE_KEY,
      });
    },
  );

  // Crossing the mobile/desktop breakpoint while open: drop search-mode state,
  // hide the overlay, normalize the trigger + Return Home, and restore focus to
  // the trigger. mobile.ts owns ALL panel layout, so do NOT call
  // exitCrossUtubSearchMode() here (avoids listener registration-order coupling).
  if (_breakpointQuery !== null && _onBreakpointChange !== null) {
    _breakpointQuery.removeEventListener("change", _onBreakpointChange);
  }
  _breakpointQuery = matchMedia("(max-width: " + TABLET_WIDTH + "px)");
  _onBreakpointChange = () => {
    if (!_searchModeActive) return;
    _searchModeActive = false;
    // Sync the shared resolver: enterCrossUtubSearchMode() set search mode
    // active via setSearchModeActive, so release it here too. This clears the
    // search-mode intent and lets the resolver reconcile; mobile.ts's own
    // breakpoint listener owns the final panel layout.
    setSearchModeActive({ active: false });
    $("#crossUtubSearchMode")
      .removeClass("cross-search-visible")
      .addClass("cross-search-hidden");
    setTriggerToOpenState();
    $("#navReturnHome").addClass("hidden");
    _lastSubmitted = null;
    updateSubmitButtonState();
    $("#toCrossUtubSearch").trigger("focus");
  };
  _breakpointQuery.addEventListener("change", _onBreakpointChange);

  if (getState().utubs.length > 0) {
    $("#toCrossUtubSearch").removeClass("hidden");
  }
}
