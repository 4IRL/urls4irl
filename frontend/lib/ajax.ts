/**
 * AJAX utility functions
 * From extensions.js
 */

import { $ } from "./globals.js";
import { showNewPageOnAJAXHTMLResponse } from "./page-utils.js";

interface RateLimitedXHR extends JQuery.jqXHR {
  _429Handled: boolean;
}

/**
 * Makes an AJAX request with global 429 rate limit handling
 * @param {string} type - HTTP method (GET, POST, etc.)
 * @param {string} url - Target URL
 * @param {Record<string, unknown> | unknown[] | null | undefined} data - Request data
 * @param {number} timeout - Request timeout in ms (default: 1000)
 * @returns {JQuery.jqXHR} jQuery AJAX promise
 */
export function ajaxCall(
  type: string,
  url: string,
  data: Record<string, unknown> | unknown[] | null | undefined,
  timeout: number = 1000,
): JQuery.jqXHR {
  const isJsonBody =
    data !== null &&
    typeof data === "object" &&
    !Array.isArray(data) &&
    Object.keys(data).length > 0;

  let request = $.ajax({
    type: type,
    url: url,
    ...(isJsonBody
      ? { data: JSON.stringify(data), contentType: "application/json" }
      : {}),
    timeout: timeout,
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    const rateLimitedXhr = xhr as RateLimitedXHR;
    // Initialize _429Handled to false on every .fail() invocation so callers can
    // safely read the flag for any error response, not just 429s.
    rateLimitedXhr._429Handled = false;
    if (xhr.status === 429) {
      const contentType = xhr.getResponseHeader("Content-Type");
      if (contentType && contentType.includes("text/html")) {
        rateLimitedXhr._429Handled = true;
        showNewPageOnAJAXHTMLResponse(xhr.responseText);
      }
    }
  });

  return request;
}

/**
 * Sends a debug message to the server (dev only)
 * @param {string} msg - Debug message
 */
export function debugCall(msg: string): void {
  $.ajax({
    type: "POST",
    url: "/debug",
    data: JSON.stringify({
      msg: `${msg}`,
    }),
    contentType: "application/json",
  });
}
