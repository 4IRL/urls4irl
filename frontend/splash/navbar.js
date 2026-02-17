import { $, bootstrap } from "../lib/globals.js";
import { initNavbarRouting } from "../lib/navbar-shared.js";

// Navbar toggler object (shared state)
export const NAVBAR_TOGGLER = { toggler: null };

/**
 * Initialize the navbar toggler and event listeners
 * Called on document ready
 */
export function initNavbar() {
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

/**
 * Handle mobile navbar opening
 * Creates and displays backdrop, adds z-index classes
 */
function onMobileNavbarOpened() {
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

/**
 * Handle mobile navbar closing
 * Removes backdrop and z-index classes
 */
function onMobileNavbarClosed() {
  const navbarBackdrop = $(".navbar-backdrop");
  navbarBackdrop.addClass("navbar-backdrop-fade");

  setTimeout(function () {
    navbarBackdrop.remove();
  }, 300);

  $(".navbar-brand").removeClass("z9999");
  $(".navbar-toggler").removeClass("z9999");
  $("#NavbarNavDropdown").removeClass("z9999");
}
