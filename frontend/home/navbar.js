import { $, bootstrap } from "../lib/globals.js";
import { initNavbarRouting } from "../lib/navbar-shared.js";
import {
  setMobileUIWhenMemberDeckSelected,
  setMobileUIWhenUTubSelectedOrURLNavSelected,
  setMobileUIWhenUTubDeckSelected,
  setMobileUIWhenTagDeckSelected,
} from "./mobile.js";

export const NAVBAR_TOGGLER = { toggler: null };

/**
 * Initialize navbar and mobile navigation buttons
 */
export function initNavbar() {
  $("button#toMembers").on("click", () => {
    setMobileUIWhenMemberDeckSelected();
  });
  $("button#toURLs").on("click", () => {
    setMobileUIWhenUTubSelectedOrURLNavSelected();
  });
  $("button#toUTubs").on("click", () => {
    setMobileUIWhenUTubDeckSelected();
  });
  $("button#toTags").on("click", () => {
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

export function onMobileNavbarOpened() {
  const navbarBackdrop = $(document.createElement("div")).addClass(
    "navbar-backdrop",
  );

  navbarBackdrop.on("click", function () {
    NAVBAR_TOGGLER.toggler.hide();
  });

  setTimeout(function () {
    navbarBackdrop.addClass("navbar-backdrop-show");
  }, 0);

  $(".navbar-brand").addClass("z9999");
  $(".navbar-toggler").addClass("z9999");
  $("#NavbarNavDropdown").addClass("z9999");

  $("#mainNavbar").append(navbarBackdrop);
}

export function onMobileNavbarClosed() {
  const navbarBackdrop = $(".navbar-backdrop");
  navbarBackdrop.addClass("navbar-backdrop-fade");

  setTimeout(function () {
    navbarBackdrop.remove();
  }, 300);

  $(".navbar-brand").removeClass("z9999");
  $(".navbar-toggler").removeClass("z9999");
  $("#NavbarNavDropdown").removeClass("z9999");
}
