import { $, bootstrap } from "../lib/globals.js";
import { emit } from "../lib/metrics-client.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import { initNavbarRouting } from "../lib/navbar-shared.js";
import {
  setMobileUIWhenMemberDeckSelected,
  setMobileUIWhenUTubSelectedOrURLNavSelected,
  setMobileUIWhenUTubDeckSelected,
  pushMobilePanelHistoryState,
  setCurrentMobilePanel,
  type MobilePanel,
} from "./mobile.js";
import { getState } from "../store/app-store.js";
import { openTagSheetFromUserAction } from "./tags/sheet.js";
import {
  exitCrossUtubSearchMode,
  isCrossUtubSearchActive,
} from "./search/cross-utub-search.js";
import {
  CROSS_UTUB_SEARCH_CLOSE_TRIGGER,
  MOBILE_NAV_TARGET,
  MOBILE_NAV_TRIGGER,
} from "../types/metrics-dim-values.js";

export const NAVBAR_TOGGLER: { toggler: bootstrap.Collapse | null } = {
  toggler: null,
};

let _suppressNextNavbarCloseEmit: boolean = false;

// Selecting a deck from the hamburger while cross-UTub search is open should also
// leave search (otherwise the user navigates "under" the open overlay). Exit
// first; the caller's setMobileUIWhen* runs after as the authoritative layout.
function closeCrossUtubSearchIfOpen(): void {
  if (isCrossUtubSearchActive()) {
    exitCrossUtubSearchMode({
      trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.DECK_SWITCH,
    });
  }
}

// Push a merged `{ UTubID, mobilePanel }` history entry when a deck-switch tap
// changes the active mobile panel, and keep `_currentMobilePanel` in sync.
// Call-site dedup guard: skip the push when the current history entry already
// carries the identical `{ UTubID, mobilePanel }` (a redundant re-tap of the
// same deck) so Back does not have to unwind duplicate consecutive entries.
function pushMobilePanelHistoryOnTap({
  mobilePanel,
}: {
  mobilePanel: MobilePanel;
}): void {
  const activeUTubID = getState().activeUTubID;
  if (activeUTubID === null) return;
  setCurrentMobilePanel({ mobilePanel });
  const state = window.history.state;
  if (state?.UTubID === activeUTubID && state?.mobilePanel === mobilePanel) {
    return;
  }
  pushMobilePanelHistoryState({ mobilePanel, UTubID: activeUTubID });
}

/**
 * Initialize navbar and mobile navigation buttons
 */
export function initNavbar(): void {
  $("button#toMembers").on("click", () => {
    closeCrossUtubSearchIfOpen();
    _suppressNextNavbarCloseEmit = true;
    emit({
      event: UI_EVENTS.UI_MOBILE_NAV,
      target: MOBILE_NAV_TARGET.MEMBERS,
      trigger: MOBILE_NAV_TRIGGER.TAP,
    });
    setMobileUIWhenMemberDeckSelected();
    pushMobilePanelHistoryOnTap({ mobilePanel: "members" });
  });
  $("button#toURLs").on("click", () => {
    closeCrossUtubSearchIfOpen();
    _suppressNextNavbarCloseEmit = true;
    emit({
      event: UI_EVENTS.UI_MOBILE_NAV,
      target: MOBILE_NAV_TARGET.URLS,
      trigger: MOBILE_NAV_TRIGGER.TAP,
    });
    setMobileUIWhenUTubSelectedOrURLNavSelected();
    pushMobilePanelHistoryOnTap({ mobilePanel: "urls" });
  });
  $("button#toUTubs").on("click", () => {
    closeCrossUtubSearchIfOpen();
    _suppressNextNavbarCloseEmit = true;
    emit({
      event: UI_EVENTS.UI_MOBILE_NAV,
      target: MOBILE_NAV_TARGET.UTUBS,
      trigger: MOBILE_NAV_TRIGGER.TAP,
    });
    setMobileUIWhenUTubDeckSelected();
    pushMobilePanelHistoryOnTap({ mobilePanel: "utubs" });
  });
  $("button#toTags").on("click", () => {
    closeCrossUtubSearchIfOpen();
    _suppressNextNavbarCloseEmit = true;
    emit({
      event: UI_EVENTS.UI_MOBILE_NAV,
      target: MOBILE_NAV_TARGET.TAGS,
      trigger: MOBILE_NAV_TRIGGER.TAP,
    });
    // The tag sheet overlays the URL deck, so first switch to the URL deck —
    // otherwise tapping Tags from the Member/UTub deck opens the sheet over the
    // wrong deck. This also collapses the hamburger (it calls toggler.hide()),
    // which must happen before openTagSheet() moves focus into the sheet and
    // marks #mainPanel siblings inert (a still-open Bootstrap collapse would
    // otherwise desync and become unreopenable). Then open the sheet over it.
    setMobileUIWhenUTubSelectedOrURLNavSelected();
    setCurrentMobilePanel({ mobilePanel: "urls" });
    openTagSheetFromUserAction();
  });

  // "Return Home" inside the hamburger — only visible while cross-UTub search is
  // open (the labeled exit, and the only reachable one on mobile). Closes the
  // overlay and the dropdown; the deck layout is restored by exit itself.
  $("button#navReturnHome").on("click", () => {
    exitCrossUtubSearchMode({
      trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.RETURN_HOME,
    });
    NAVBAR_TOGGLER.toggler?.hide();
  });

  // Initialize data-route buttons (shared functionality)
  initNavbarRouting();

  // Grab toggler for the navbar
  NAVBAR_TOGGLER.toggler = new bootstrap.Collapse("#NavbarNavDropdown", {
    toggle: false,
  });

  // Event listeners when hiding and showing the mobile navbar
  $("#NavbarNavDropdown")
    .on("show.bs.collapse", () => {
      onMobileNavbarOpened();
    })
    .on("hide.bs.collapse", () => {
      onMobileNavbarClosed();
    });
}

export function onMobileNavbarOpened(): void {
  emit({ event: UI_EVENTS.UI_NAVBAR_DROPDOWN_OPEN });
  const navbarBackdrop = $(document.createElement("div")).addClass(
    "navbar-backdrop",
  );

  navbarBackdrop.on("click", function () {
    NAVBAR_TOGGLER.toggler?.hide();
  });

  setTimeout(function () {
    navbarBackdrop.addClass("navbar-backdrop-show");
  }, 0);

  $(".navbar-brand").addClass("z9999");
  $(".navbar-toggler").addClass("z9999");
  $("#NavbarNavDropdown").addClass("z9999");

  $("#mainNavbar").append(navbarBackdrop);
}

export function onMobileNavbarClosed(): void {
  if (_suppressNextNavbarCloseEmit) {
    _suppressNextNavbarCloseEmit = false;
  } else {
    emit({ event: UI_EVENTS.UI_NAVBAR_DROPDOWN_CLOSE });
  }
  const navbarBackdrop = $(".navbar-backdrop");
  navbarBackdrop.addClass("navbar-backdrop-fade");

  setTimeout(function () {
    navbarBackdrop.remove();
  }, 300);

  $(".navbar-brand").removeClass("z9999");
  $(".navbar-toggler").removeClass("z9999");
  $("#NavbarNavDropdown").removeClass("z9999");
}
