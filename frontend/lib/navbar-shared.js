import { $ } from "./globals.js";
import { APP_CONFIG } from "./config.js";

/**
 * Initialize navigation buttons with data-route attributes
 * Shared between all entry points that need navbar functionality
 */
export function initNavbarRouting() {
  $("[data-route]").each(function () {
    const $btn = $(this);
    const route = $btn.data("route");
    $btn.on("click", () => {
      window.location.assign(APP_CONFIG.routes[route]);
    });
  });
}
