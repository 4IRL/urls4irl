import { $ } from "../../lib/globals.js";
import { KEYS } from "../../lib/constants.js";
import { AppEvents, on } from "../../lib/event-bus.js";
import { emit as recordUIEvent } from "../../lib/metrics-client.js";
import { TAG_SHEET_TOGGLE_ACTION } from "../../types/metrics-dim-values.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { isCrossUtubSearchActive } from "../search/cross-utub-search.js";
import { isMobile } from "../mobile.js";

// Module-local open flag — no cross-module reader needs it, so it lives here
// rather than the app store (mirrors `userCollapsedLHS` in left-panel-toggle.ts).
let sheetOpen = false;
// Tracks which element last opened the sheet so focus returns to it on close
// (WCAG 2.4.3).
let _opener: HTMLElement | null = null;

const SHEET_SELECTOR = "#tagDeckSheet";
const SHEET_BODY_SELECTOR = "#tagSheetBody";
const BACKDROP_SELECTOR = "#tagSheetBackdrop";
const HANDLE_ID = "tagSheetHandle";
const HANDLE_SELECTOR = `#${HANDLE_ID}`;
const HANDLE_COUNT_SELECTOR = "#tagSheetHandleCount";
const GRABBER_ID = "tagSheetGrabber";
const GRABBER_SELECTOR = `#${GRABBER_ID}`;
const EMPTY_STATE_SELECTOR = "#tagSheetEmpty";
const MAIN_PANEL_SELECTOR = "#mainPanel";
const TAG_DECK_SELECTOR = "#TagDeck";
const LIST_TAGS_SELECTOR = "#listTags";
const TAG_FILTER_SELECTOR = ".tagFilter";
const SHEET_OPEN_CLASS = "tag-sheet-open";
const BACKDROP_SHOW_CLASS = "tag-sheet-backdrop-show";
const HIDDEN_CLASS = "hidden";
const ESCAPE_KEYDOWN_NAMESPACE = "keydown.tagSheetEscape";
// Siblings of these two are made inert while the sheet is open; the pair is
// excluded so the sheet and its backdrop remain interactive.
const INERT_EXCLUDE_SELECTOR = `${SHEET_SELECTOR}, ${BACKDROP_SELECTOR}`;

/**
 * Toggle the inline empty-state message based on the current `#listTags` child
 * count. Reads only the DOM; independent of `sheetOpen`. The "No tags in this
 * UTub." literal lives in the Jinja template (TS only toggles `.hidden`), so no
 * APP_CONFIG bridge is warranted.
 */
function _updateEmptyState(): void {
  const hasTags =
    $(LIST_TAGS_SELECTOR).children(TAG_FILTER_SELECTOR).length > 0;
  $(EMPTY_STATE_SELECTOR).toggleClass(HIDDEN_CLASS, hasTags);
}

/**
 * The handle shows only when mobile + a UTub is selected + the URL deck is
 * showing + cross-search is not open. Exported so mobile-state subscribers can
 * re-sync it after a deck transition.
 */
export function refreshTagSheetHandleVisibility(): void {
  const utubSelected = $(".UTubSelector.active").length > 0;
  const urlDeckShowing = $(".panel#centerPanel").hasClass("visible-flex");
  const shouldShow =
    isMobile() && utubSelected && urlDeckShowing && !isCrossUtubSearchActive();
  $(HANDLE_SELECTOR).toggleClass(HIDDEN_CLASS, !shouldShow);
}

/**
 * Move `#TagDeck` into the sheet on mobile and back into `#leftPanel` (as the
 * 3rd child, after `#MemberDeck`) on desktop. Moving the whole node keeps
 * `#listTags` + its `.tagFilter` children intact so `sortTagFiltersInPlace`
 * stays valid.
 */
export function relocateTagDeckForViewport(): void {
  const tagDeckInSheet =
    $(`${SHEET_BODY_SELECTOR} ${TAG_DECK_SELECTOR}`).length > 0;

  if (isMobile()) {
    if (!tagDeckInSheet) {
      $(TAG_DECK_SELECTOR).appendTo(SHEET_BODY_SELECTOR);
    }
    _updateEmptyState();
    return;
  }

  if (tagDeckInSheet) {
    $(TAG_DECK_SELECTOR).insertAfter("#leftPanel #MemberDeck");
    // Close first (the handle's JS hidden-state must also reset), then refresh
    // handle visibility so a later return to mobile re-shows it correctly.
    closeTagSheet({ returnFocus: false });
    refreshTagSheetHandleVisibility();
  }
}

export function openTagSheet(): void {
  if (!isMobile()) return;

  // Capture the element that had focus at open time so focus can be returned to
  // it on close (covers both #toTags and #tagSheetHandle openers; WCAG 2.4.3).
  _opener = document.activeElement as HTMLElement | null;

  $(SHEET_SELECTOR).addClass(SHEET_OPEN_CLASS).attr("aria-hidden", "false");
  // Defer the backdrop class one tick so the CSS opacity transition fires.
  setTimeout(() => $(BACKDROP_SELECTOR).addClass(BACKDROP_SHOW_CLASS), 0);
  $(HANDLE_SELECTOR).attr("aria-expanded", "true");
  sheetOpen = true;

  // Trap focus: mark every #mainPanel direct child inert except the sheet and
  // its backdrop. Native inert focus containment needs no custom Tab interceptor
  // (Chrome 120+, Firefox 121+, Safari 16+).
  $(MAIN_PANEL_SELECTOR)
    .children()
    .not(INERT_EXCLUDE_SELECTOR)
    .prop("inert", true);

  document.getElementById(GRABBER_ID)?.focus();

  $(document).on(ESCAPE_KEYDOWN_NAMESPACE, (event: JQuery.TriggeredEvent) => {
    if (event.key !== KEYS.ESCAPE) return;
    closeTagSheet();
  });

  _updateEmptyState();

  recordUIEvent({
    event: UI_EVENTS.UI_TAG_SHEET_TOGGLE,
    action: TAG_SHEET_TOGGLE_ACTION.OPEN,
  });
}

export function closeTagSheet({
  returnFocus = true,
}: { returnFocus?: boolean } = {}): void {
  // Capture prior-open state so the CLOSE metric only fires for a real
  // open→close transition. Several programmatic callers (deck-switch, desktop
  // relocate) invoke this on an already-closed sheet; emitting there would
  // inflate close counts with no matching open.
  const wasOpen = sheetOpen;

  $(SHEET_SELECTOR).removeClass(SHEET_OPEN_CLASS).attr("aria-hidden", "true");
  $(BACKDROP_SELECTOR).removeClass(BACKDROP_SHOW_CLASS);
  $(document).off(ESCAPE_KEYDOWN_NAMESPACE);

  // Unconditional removal is safe: no #mainPanel child carries independent inert state.
  // If that changes, snapshot which siblings were already inert in openTagSheet and restore selectively.
  $(MAIN_PANEL_SELECTOR)
    .children()
    .not(INERT_EXCLUDE_SELECTOR)
    .prop("inert", false);

  $(HANDLE_SELECTOR).attr("aria-expanded", "false");
  sheetOpen = false;

  if (returnFocus) {
    if (_opener !== null && document.contains(_opener)) {
      _opener.focus();
    } else {
      document.getElementById(HANDLE_ID)?.focus();
    }
  }
  _opener = null;

  if (wasOpen) {
    recordUIEvent({
      event: UI_EVENTS.UI_TAG_SHEET_TOGGLE,
      action: TAG_SHEET_TOGGLE_ACTION.CLOSE,
    });
  }
}

export function toggleTagSheet(): void {
  if (sheetOpen) {
    closeTagSheet();
  } else {
    openTagSheet();
  }
}

export function isTagSheetOpen(): boolean {
  return sheetOpen;
}

export function initTagSheet(): void {
  // Place #TagDeck correctly for the load-time viewport (one-shot; viewport
  // crossings are owned by initMobileLayout's matchMedia listener in mobile.ts).
  relocateTagDeckForViewport();

  $(HANDLE_SELECTOR).on("click", toggleTagSheet);
  $(GRABBER_SELECTOR).on("click", () => closeTagSheet());
  $(BACKDROP_SELECTOR).on("click", () => closeTagSheet());

  on(AppEvents.UTUB_SELECTED, () => {
    if (sheetOpen) closeTagSheet({ returnFocus: false });
    refreshTagSheetHandleVisibility();
    _updateEmptyState();
  });

  on(AppEvents.UTUB_DELETED, () => {
    if (sheetOpen) closeTagSheet({ returnFocus: false });
    refreshTagSheetHandleVisibility();
  });

  on(AppEvents.CROSS_UTUB_SEARCH_VISIBILITY_CHANGED, ({ active }) => {
    if (active) closeTagSheet({ returnFocus: false });
    refreshTagSheetHandleVisibility();
  });

  on(AppEvents.MOBILE_DECK_SWITCHED, ({ target }) => {
    if (target === "desktop") {
      relocateTagDeckForViewport();
      return;
    }
    // Any explicit mobile deck navigation dismisses an open sheet — including
    // navigating (back) to the URL deck via the navbar. closeTagSheet is a safe
    // no-op when the sheet is already closed (the common UTub-select path), so
    // the url-deck target is no longer special-cased: leaving it open would keep
    // #mainPanel siblings inert and break navbar re-open over the URL deck.
    closeTagSheet({ returnFocus: false });
    refreshTagSheetHandleVisibility();
  });

  // Stateless show/hide of the handle's count badge from selectedTagIDs.length.
  // Registered once permanently — no per-UTub teardown (unlike deck.ts), so it
  // never accumulates duplicates across UTub changes.
  on(AppEvents.TAG_FILTER_CHANGED, ({ selectedTagIDs }) => {
    const count = selectedTagIDs.length;
    $(HANDLE_COUNT_SELECTOR)
      .toggleClass(HIDDEN_CLASS, count === 0)
      .text(count > 0 ? String(count) : "");
  });
}
