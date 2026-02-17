/**
 * AJAX utility functions
 * From extensions.js
 */

import { $ } from "./globals.js";
import { showNewPageOnAJAXHTMLResponse } from "./page-utils.js";

/**
 * Makes an AJAX request with global 429 rate limit handling
 * @param {string} type - HTTP method (GET, POST, etc.)
 * @param {string} url - Target URL
 * @param {Object} data - Request data
 * @param {number} timeout - Request timeout in ms (default: 1000)
 * @returns {jqXHR} jQuery AJAX promise
 */
export function ajaxCall(type, url, data, timeout = 1000) {
  let request = $.ajax({
    type: type,
    url: url,
    data: data,
    timeout: timeout,
  });

  request.fail(function (xhr) {
    // Global 429 HTML handler
    xhr._429Handled = false;
    if (xhr.status === 429) {
      let contentType = xhr.getResponseHeader("Content-Type");
      if (contentType && contentType.includes("text/html")) {
        xhr._429Handled = true;
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
export function debugCall(msg) {
  $.ajax({
    type: "POST",
    url: "/debug",
    data: JSON.stringify({
      msg: `${msg}`,
    }),
    contentType: "application/json",
  });
}
