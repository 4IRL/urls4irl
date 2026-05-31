import { $, bootstrap } from "../lib/globals.js";
import { emit } from "../lib/metrics-client.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import { initNavbarRouting } from "../lib/navbar-shared.js";

// Navbar toggler object (shared state)
export const NAVBAR_TOGGLER: { toggler: bootstrap.Collapse | null } = {
  toggler: null,
};

export function initNavbar(): void {
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

function onMobileNavbarOpened(): void {
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

function onMobileNavbarClosed(): void {
  emit({ event: UI_EVENTS.UI_NAVBAR_MOBILE_MENU_CLOSE });
  const navbarBackdrop = $(".navbar-backdrop");
  navbarBackdrop.addClass("navbar-backdrop-fade");

  setTimeout(function () {
    navbarBackdrop.remove();
  }, 300);

  $(".navbar-brand").removeClass("z9999");
  $(".navbar-toggler").removeClass("z9999");
  $("#NavbarNavDropdown").removeClass("z9999");
}
