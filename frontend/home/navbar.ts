import { $, bootstrap } from "../lib/globals.js";
import { emit } from "../lib/metrics-client.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import { initNavbarRouting } from "../lib/navbar-shared.js";
import {
  setMobileUIWhenMemberDeckSelected,
  setMobileUIWhenUTubSelectedOrURLNavSelected,
  setMobileUIWhenUTubDeckSelected,
} from "./mobile.js";
import { openTagSheet } from "./tags/sheet.js";
import {
  exitCrossUtubSearchMode,
  isCrossUtubSearchActive,
} from "./search/cross-utub-search.js";
import {
  CROSS_UTUB_SEARCH_CLOSE_TRIGGER,
  MOBILE_NAV_TARGET,
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

/**
 * Initialize navbar and mobile navigation buttons
 */
export function initNavbar(): void {
  $("button#toMembers").on("click", () => {
    closeCrossUtubSearchIfOpen();
    _suppressNextNavbarCloseEmit = true;
    emit({ event: UI_EVENTS.UI_MOBILE_NAV, target: MOBILE_NAV_TARGET.MEMBERS });
    setMobileUIWhenMemberDeckSelected();
  });
  $("button#toURLs").on("click", () => {
    closeCrossUtubSearchIfOpen();
    _suppressNextNavbarCloseEmit = true;
    emit({ event: UI_EVENTS.UI_MOBILE_NAV, target: MOBILE_NAV_TARGET.URLS });
    setMobileUIWhenUTubSelectedOrURLNavSelected();
  });
  $("button#toUTubs").on("click", () => {
    closeCrossUtubSearchIfOpen();
    _suppressNextNavbarCloseEmit = true;
    emit({ event: UI_EVENTS.UI_MOBILE_NAV, target: MOBILE_NAV_TARGET.UTUBS });
    setMobileUIWhenUTubDeckSelected();
  });
  $("button#toTags").on("click", () => {
    closeCrossUtubSearchIfOpen();
    _suppressNextNavbarCloseEmit = true;
    emit({ event: UI_EVENTS.UI_MOBILE_NAV, target: MOBILE_NAV_TARGET.TAGS });
    // The tag sheet overlays the URL deck, so first switch to the URL deck —
    // otherwise tapping Tags from the Member/UTub deck opens the sheet over the
    // wrong deck. This also collapses the hamburger (it calls toggler.hide()),
    // which must happen before openTagSheet() moves focus into the sheet and
    // marks #mainPanel siblings inert (a still-open Bootstrap collapse would
    // otherwise desync and become unreopenable). Then open the sheet over it.
    setMobileUIWhenUTubSelectedOrURLNavSelected();
    openTagSheet();
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
