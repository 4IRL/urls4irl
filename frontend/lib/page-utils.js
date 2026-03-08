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

    // Hide body initially, then fade in on next frame
    // (window.load fires before a listener can be added for simple HTML)
    document.body.style.opacity = "0";
    requestAnimationFrame(function () {
      document.body.style.transition = "opacity 0.15s";
      document.body.style.opacity = "1";
    });
  });
}
