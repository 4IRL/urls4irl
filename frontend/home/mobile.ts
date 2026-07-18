import { $ } from "../lib/globals.js";
import { APP_CONFIG } from "../lib/config.js";
import { TABLET_WIDTH } from "../lib/constants.js";
import { emit, on, AppEvents } from "../lib/event-bus.js";
import { NAVBAR_TOGGLER } from "./navbar.js";
import {
  resetAllDecksIfCollapsed,
  removeCollapsibleClickableHeaderClass,
  addCollapsibleClickableHeaderClass,
} from "./collapsible-decks.js";
import { getState } from "../store/app-store.js";
import { reapplyLeftPanelVisibilityForViewport } from "./left-panel-toggle.js";
import { makeUTubSelectableAgainIfMobile } from "./utubs/selectors.js";
import { debug } from "../lib/debug.js";

const log = debug("home-shell");

/**
 * The three persisted mobile panels a UTub can be viewed through. Mirrors the
 * `MOBILE_NAV_TARGET` values, minus `tags` — the Tags bottom-sheet is not a
 * persisted panel (its history entry is handled separately in the Tags sheet
 * module), it is an overlay on top of whichever panel is active.
 */
export type MobilePanel = "utubs" | "urls" | "members";

// Module-local tracking of the panel currently shown on mobile, mirroring the
// `isTagSheetOpen()`/`isCrossUtubSearchActive()` module-local-state convention.
// The tap/popstate call sites (steps 3–4) keep this in sync via the setter.
let _currentMobilePanel: MobilePanel = "utubs";

export function getCurrentMobilePanel(): MobilePanel {
  return _currentMobilePanel;
}

export function setCurrentMobilePanel({
  mobilePanel,
}: {
  mobilePanel: MobilePanel;
}): void {
  _currentMobilePanel = mobilePanel;
}

/**
 * Push a merged `{ UTubID, mobilePanel }` browser-history entry for a mobile
 * panel switch so Back/Forward unwind the panel navigation stack. Unconditional
 * — call-site dedup guards (steps 3–4) decide whether a push is warranted.
 * Deliberately does NOT set the `fullyLoaded` sessionStorage flag that
 * `buildSelectedUTub` sets alongside `pushUTubHistoryState` — that side effect
 * is specific to UTub selection, not panel switching.
 */
export function pushMobilePanelHistoryState({
  mobilePanel,
  UTubID,
}: {
  mobilePanel: MobilePanel;
  UTubID: number;
}): void {
  const utubidKey = APP_CONFIG.strings.UTUB_QUERY_PARAM;
  const panelKey = APP_CONFIG.strings.MOBILE_PANEL_QUERY_PARAM;
  log("pushMobilePanelHistoryState — pushing merged panel history entry", {
    UTubID,
    mobilePanel,
  });
  window.history.pushState(
    { UTubID, mobilePanel },
    "",
    `/home?${utubidKey}=${UTubID}&${panelKey}=${mobilePanel}`,
  );
}

/**
 * Replace the current browser-history entry with a merged
 * `{ UTubID, mobilePanel }` entry — same shape as `pushMobilePanelHistoryState`
 * but without adding a stack entry. Used (steps 3–4) to overwrite a freshly
 * pushed bare-`{ UTubID }` entry with the landing panel of a newly-selected UTub.
 */
export function replaceMobilePanelHistoryState({
  mobilePanel,
  UTubID,
}: {
  mobilePanel: MobilePanel;
  UTubID: number;
}): void {
  const utubidKey = APP_CONFIG.strings.UTUB_QUERY_PARAM;
  const panelKey = APP_CONFIG.strings.MOBILE_PANEL_QUERY_PARAM;
  log("replaceMobilePanelHistoryState — replacing current history entry", {
    UTubID,
    mobilePanel,
  });
  window.history.replaceState(
    { UTubID, mobilePanel },
    "",
    `/home?${utubidKey}=${UTubID}&${panelKey}=${mobilePanel}`,
  );
}

/**
 * Check if current viewport is mobile/tablet size
 */
export function isMobile(): boolean {
  return ($(window).width() ?? 0) < TABLET_WIDTH;
}

/**
 * Check if the device has a coarse pointer (touch). Mirrors the
 * `@media (any-pointer: coarse)` query that gates touch-only affordances in CSS,
 * so JS and CSS agree regardless of viewport width.
 */
export function isCoarsePointer(): boolean {
  return window.matchMedia("(any-pointer: coarse)").matches;
}

/**
 * Initialize mobile layout event listeners
 */
export function initMobileLayout(): void {
  on(AppEvents.UTUB_SELECTED, () => {
    if (isMobile()) setMobileUIWhenUTubSelectedOrURLNavSelected();
  });

  // Use matchMedia instead of resize when just need to determine if > or < than
  // specific size
  // https://webdevetc.com/blog/matchmedia-events-for-window-resizes/
  const query = matchMedia("(max-width: " + TABLET_WIDTH + "px)");
  query.addEventListener("change", function () {
    const width = $(window).width() ?? 0;
    log("viewport crossed TABLET_WIDTH threshold", {
      width,
      isMobileNow: width < TABLET_WIDTH,
      activeUTubID: getState().activeUTubID,
    });

    // Handle size changes when tablet or smaller
    if (width < TABLET_WIDTH) {
      resetAllDecksIfCollapsed();
      // If UTub selected, show URL Deck
      // If no UTub selected, show UTub deck
      // Set tablet-mobile navbar depending on UTub selected or not
      if (getState().activeUTubID !== null) {
        setMobileUIWhenUTubSelectedOrURLNavSelected();
      } else {
        setMobileUIWhenUTubNotSelectedOrUTubDeleted();
      }
      removeCollapsibleClickableHeaderClass();
      reapplyLeftPanelVisibilityForViewport();
    } else {
      // Set full screen navbar
      // Show all panels and decks
      revertMobileUIToFullScreenUI();
      addCollapsibleClickableHeaderClass();
      reapplyLeftPanelVisibilityForViewport();
    }
  });
}

export function setMobileUIWhenUTubSelectedOrURLNavSelected(): void {
  $(".panel#leftPanel").addClass("hidden");
  $(".panel#centerPanel").addClass("visible-flex");
  $("button#toUTubs").removeClass("hidden");
  $("button#toMembers").removeClass("hidden");
  $("button#toTags").removeClass("hidden");
  $("button#toURLs").addClass("hidden");

  $(".deck#MemberDeck").removeClass("visible-flex");

  NAVBAR_TOGGLER.toggler?.hide();
  emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "url-deck" });
}

export function setMobileUIWhenUTubNotSelectedOrUTubDeleted(): void {
  $("button#toUTubs").addClass("hidden");
  $("button#toMembers").addClass("hidden");
  $("button#toTags").addClass("hidden");
  $("button#toURLs").addClass("hidden");

  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#MemberDeck").removeClass("visible-flex");

  $(".deck#UTubDeck").removeClass("hidden");

  NAVBAR_TOGGLER.toggler?.hide();
  emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "no-utub" });
}

export function setMobileUIWhenUTubDeckSelected(): void {
  $("button#toUTubs").addClass("hidden");
  $("button#toMembers").removeClass("hidden");
  $("button#toTags").removeClass("hidden");
  $("button#toURLs").removeClass("hidden");

  $(".panel#leftPanel").removeClass("hidden");
  // Desktop LHS-collapse state is re-asserted by the matchMedia resize handler
  // (initMobileLayout) on viewport change — not here, since this function only
  // runs while isMobile().

  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#MemberDeck").removeClass("visible-flex");

  $(".deck#UTubDeck").removeClass("hidden");

  NAVBAR_TOGGLER.toggler?.hide();
  if ($(".UTubSelector.active").length) {
    makeUTubSelectableAgainIfMobile($(".UTubSelector.active"));
  }
  emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "utub-deck" });
}

export function setMobileUIWhenMemberDeckSelected(): void {
  $("button#toMembers").addClass("hidden");
  $(".deck#MemberDeck").addClass("visible-flex").removeClass("hidden");

  $(".panel#leftPanel").removeClass("hidden");
  // Desktop LHS-collapse state is re-asserted by the matchMedia resize handler
  // (initMobileLayout) on viewport change — not here, since this function only
  // runs while isMobile().
  $(".panel#centerPanel").removeClass("visible-flex");
  $(".deck#UTubDeck").addClass("hidden");

  $("button#toUTubs").removeClass("hidden");
  $("button#toTags").removeClass("hidden");
  $("button#toURLs").removeClass("hidden");

  NAVBAR_TOGGLER.toggler?.hide();
  emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "member-deck" });
}

export function revertMobileUIToFullScreenUI(): void {
  NAVBAR_TOGGLER.toggler?.hide();

  $("button#toUTubs").addClass("hidden");
  $("button#toMembers").addClass("hidden");
  $("button#toTags").addClass("hidden");
  $("button#toURLs").addClass("hidden");

  $(".panel#centerPanel").removeClass("hidden");
  $(".panel#leftPanel").removeClass("hidden");

  $(".deck#UTubDeck").removeClass("hidden");
  $(".deck#MemberDeck").removeClass("hidden");

  emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "desktop" });
}
