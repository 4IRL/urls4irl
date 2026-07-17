/**
 * CSRF token handling for AJAX requests
 * Consolidated from extensions.js and splash.js
 */

import type { RateLimitedXHR } from "./ajax.js";
import { debug } from "./debug.js";
import { $ } from "./globals.js";
import { emit } from "./metrics-client.js";
import { UI_EVENTS } from "../types/metrics-events.js";
import { showNewPageOnAJAXHTMLResponse } from "./page-utils.js";

const csrfLog = debug("csrf");
const ajaxLog = debug("ajax");

/**
 * Sets up CSRF token for all AJAX requests
 * Must be called after DOM is ready
 */
export function setupCSRF(): void {
  const csrftoken: string | undefined = $("meta[name=csrf-token]").attr(
    "content",
  );

  if (csrftoken === undefined) {
    csrfLog("CSRF meta tag missing — non-GET requests will go unsigned", {});
  }

  // Global ajaxSetup for non-modal requests
  $.ajaxSetup({
    beforeSend: function (
      this: JQuery.AjaxSettings,
      xhr: JQuery.jqXHR,
      settings: JQuery.AjaxSettings,
    ): false | void {
      if (
        !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type ?? "") &&
        !this.crossDomain
      ) {
        if (csrftoken !== undefined) {
          xhr.setRequestHeader("X-CSRFToken", csrftoken);
        }
      }
    },
  });

  // Global ajaxPrefilter for 429 rate limit handling. Owns the single canonical
  // emit site for `ui_rate_limit_hit` and the HTML-429 → full-page replacement.
  // Patches `options.error` (not `jqXHR.fail`) so this prefilter has uncontested
  // ownership of 429 detection — caller `.fail()` chains registered after the
  // prefilter would otherwise race the HTML-replace path.
  $.ajaxPrefilter(function (options: JQuery.AjaxSettings): string | void {
    const prevError: typeof options.error = options.error;

    options.error = function (jqXHR, textStatus, errorThrown) {
      if (jqXHR.status === 429) {
        csrfLog("ajaxPrefilter intercepted 429 — invoking page replacement", {
          url: options.url,
          status: jqXHR.status,
        });
        const contentType = jqXHR.getResponseHeader("Content-Type");
        // metrics-client uses raw fetch() (not jQuery AJAX), so a 429 from /api/metrics
        // never re-enters this prefilter. Retry-with-same-batch_id at the metrics
        // layer protects against double-counting. Safe to emit here.
        emit({ event: UI_EVENTS.UI_RATE_LIMIT_HIT });
        if (contentType && contentType.includes("text/html")) {
          ajaxLog("429 received, content-type=text/html — replacing page", {
            url: options.url,
            contentType,
          });
          // _429Handled is set only for HTML 429s so domain `.fail()` handlers
          // that read `is429Handled(xhr)` short-circuit before rendering a stale
          // error UI (the page is being replaced).
          (jqXHR as RateLimitedXHR)._429Handled = true;
          showNewPageOnAJAXHTMLResponse(jqXHR.responseText);
          return; // HTML 429: page is replaced — do not chain to caller's error handler.
        }
        ajaxLog("429 received but NOT marked _429Handled (non-HTML body)", {
          url: options.url,
          contentType,
        });
      }

      if (typeof prevError === "function") {
        prevError.call(this, jqXHR, textStatus, errorThrown);
      }
    };
  });
}
