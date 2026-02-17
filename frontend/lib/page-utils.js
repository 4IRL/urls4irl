/**
 * Page navigation utilities
 * Consolidated from home.js and splash.js
 */

import { $ } from "./globals.js";

/**
 * Replaces the current page with new HTML from an AJAX response
 * Used for rate limiting pages and full-page redirects
 * @param {string} htmlText - Full HTML document to display
 */
export function showNewPageOnAJAXHTMLResponse(htmlText) {
  $("body").fadeOut(150, function () {
    document.open();
    document.write(htmlText);
    document.close();

    // Hide body initially
    document.body.style.opacity = "0";

    // Wait for everything to load
    window.addEventListener("load", function () {
      $("body").css("opacity", "1").hide().fadeIn(150);
    });
  });
}
