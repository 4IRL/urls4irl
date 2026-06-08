import { $, bootstrap } from "./globals.js";
import { APP_CONFIG } from "./config.js";
import type { RouteId } from "./config.js";

const BACKDROP_FADE_REMOVE_MS = 300;

/**
 * Initialize navigation buttons with data-route attributes
 * Shared between all entry points that need navbar functionality
 */
export function initNavbarRouting(): void {
  $("[data-route]").each(function () {
    const $btn = $(this);
    const route = $btn.data("route") as RouteId;
    $btn.on("click", () => {
      window.location.assign(APP_CONFIG.routes[route] as string);
    });
  });
}

/**
 * Wire the mobile navbar dropdown's open/close transitions to:
 *   - inject a `.navbar-backdrop` overlay so the dimmed page background
 *     visually separates the dropdown from the underlying content
 *   - lift the brand, toggler, and dropdown above the backdrop via the
 *     shared `.z9999` utility so they stay tappable
 *   - close the dropdown when the user taps anywhere on the backdrop
 *
 * Pure DOM wiring; safe to call on any page whose layout includes the
 * standard `#mainNavbar` + `#NavbarNavDropdown` structure. The home
 * entry point has its own equivalent inside `home/navbar.ts` (wrapped
 * around `UI_NAVBAR_MOBILE_MENU_OPEN/CLOSE` metrics emits + suppression
 * for deck-switcher clicks); this helper covers pages whose navbar
 * does not need that metrics layer (admin, etc.).
 */
export function initMobileNavbarBackdrop(): void {
  const toggler = new bootstrap.Collapse("#NavbarNavDropdown", {
    toggle: false,
  });

  $("#NavbarNavDropdown")
    .on("show.bs.collapse", () => {
      const backdrop = $(document.createElement("div")).addClass(
        "navbar-backdrop",
      );
      backdrop.on("click", () => toggler.hide());
      setTimeout(() => {
        backdrop.addClass("navbar-backdrop-show");
      }, 0);
      $(".navbar-brand").addClass("z9999");
      $(".navbar-toggler").addClass("z9999");
      $("#NavbarNavDropdown").addClass("z9999");
      $("#mainNavbar").append(backdrop);
    })
    .on("hide.bs.collapse", () => {
      const backdrop = $(".navbar-backdrop");
      backdrop.addClass("navbar-backdrop-fade");
      setTimeout(() => {
        backdrop.remove();
      }, BACKDROP_FADE_REMOVE_MS);
      $(".navbar-brand").removeClass("z9999");
      $(".navbar-toggler").removeClass("z9999");
      $("#NavbarNavDropdown").removeClass("z9999");
    });
}
