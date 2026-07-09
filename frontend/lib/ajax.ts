/**
 * AJAX utility functions
 * From extensions.js
 */

import { $ } from "./globals.js";

export interface RateLimitedXHR extends JQuery.jqXHR {
  _429Handled: boolean;
}

/**
 * Returns true if the jqXHR failure has already been handled by the global
 * 429 rate-limit handler in the `$.ajaxPrefilter` registered in `csrf.ts`.
 * Callers can early-return on this to avoid double-dispatching user-visible
 * error UI for HTML 429 responses (the page is being replaced).
 */
export function is429Handled(xhr: JQuery.jqXHR): boolean {
  return !!(xhr as RateLimitedXHR)._429Handled;
}

/**
 * Makes an AJAX request. The global `$.ajaxPrefilter` in `csrf.ts` is the
 * single canonical handler for 429 rate-limit responses (emits
 * `ui_rate_limit_hit` and replaces the page on HTML 429s); this wrapper
 * is now purely a JSON-body convenience helper.
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

  return $.ajax({
    type: type,
    url: url,
    ...(isJsonBody
      ? { data: JSON.stringify(data), contentType: "application/json" }
      : {}),
    timeout: timeout,
  });
}

/**
 * Makes a GET request for an HTML fragment and returns the raw HTML string.
 * Use `.done((html: string) => { el.innerHTML = html; })` on the returned
 * jqXHR. The global `$.ajaxPrefilter` in `csrf.ts` handles 429s; call
 * `is429Handled` at the top of any `.fail()` handler.
 * @param {string} url - Fragment endpoint URL (may include query params)
 * @param {number} timeout - Request timeout in ms (default: 5000)
 * @returns {JQuery.jqXHR} jQuery AJAX promise
 */
export function ajaxCallFragment(
  url: string,
  timeout: number = 5_000,
): JQuery.jqXHR {
  return $.ajax({
    type: "GET",
    url,
    dataType: "text",
    timeout,
  });
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
