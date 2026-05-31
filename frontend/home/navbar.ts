import { $, bootstrap } from "../lib/globals.js";
import { emit } from "../lib/metrics-client.js";
import { UI_EVENTS } from "../lib/metrics-events.js";
import { initNavbarRouting } from "../lib/navbar-shared.js";
import {
  setMobileUIWhenMemberDeckSelected,
  setMobileUIWhenUTubSelectedOrURLNavSelected,
  setMobileUIWhenUTubDeckSelected,
  setMobileUIWhenTagDeckSelected,
} from "./mobile.js";

export const NAVBAR_TOGGLER: { toggler: bootstrap.Collapse | null } = {
  toggler: null,
};

let _suppressNextNavbarCloseEmit: boolean = false;

function suppressNextNavbarCloseEmit(): void {
  _suppressNextNavbarCloseEmit = true;
}

/**
 * Initialize navbar and mobile navigation buttons
 */
export function initNavbar(): void {
  $("button#toMembers").on("click", () => {
    suppressNextNavbarCloseEmit();
    emit({ event: UI_EVENTS.UI_MOBILE_NAV, target: "members" });
    setMobileUIWhenMemberDeckSelected();
  });
  $("button#toURLs").on("click", () => {
    suppressNextNavbarCloseEmit();
    emit({ event: UI_EVENTS.UI_MOBILE_NAV, target: "urls" });
    setMobileUIWhenUTubSelectedOrURLNavSelected();
  });
  $("button#toUTubs").on("click", () => {
    suppressNextNavbarCloseEmit();
    emit({ event: UI_EVENTS.UI_MOBILE_NAV, target: "utubs" });
    setMobileUIWhenUTubDeckSelected();
  });
  $("button#toTags").on("click", () => {
    suppressNextNavbarCloseEmit();
    emit({ event: UI_EVENTS.UI_MOBILE_NAV, target: "tags" });
    setMobileUIWhenTagDeckSelected();
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
  emit({ event: UI_EVENTS.UI_NAVBAR_MOBILE_MENU_OPEN });
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
    emit({ event: UI_EVENTS.UI_NAVBAR_MOBILE_MENU_CLOSE });
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
