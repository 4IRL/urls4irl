/**
 * CSRF token handling for AJAX requests
 * Consolidated from extensions.js and splash.js
 */

import { $ } from "./globals.js";
import { showNewPageOnAJAXHTMLResponse } from "./page-utils.js";

/**
 * Sets up CSRF token for all AJAX requests
 * Must be called after DOM is ready
 */
export function setupCSRF(): void {
  const csrftoken: string | undefined = $("meta[name=csrf-token]").attr(
    "content",
  );

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

  // Global ajaxPrefilter for 429 rate limit handling
  $.ajaxPrefilter(function (options: JQuery.AjaxSettings): string | void {
    let originalError: typeof options.error = options.error;

    options.error = function (jqXHR, textStatus, errorThrown) {
      if (jqXHR.status === 429) {
        showNewPageOnAJAXHTMLResponse(jqXHR.responseText);
        return; // Intercepts 429 to show rate-limit page; .fail() handlers still fire separately
      }

      if (typeof originalError === "function") {
        originalError.call(this, jqXHR, textStatus, errorThrown);
      }
    };
  });
}
