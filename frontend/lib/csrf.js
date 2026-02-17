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
export function setupCSRF() {
  const csrftoken = $("meta[name=csrf-token]").attr("content");

  // Global ajaxSetup for non-modal requests
  $.ajaxSetup({
    beforeSend: function (xhr, settings) {
      if (
        !/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) &&
        !this.crossDomain
      ) {
        xhr.setRequestHeader("X-CSRFToken", csrftoken);
      }
      return true;
    },
  });

  // Global ajaxPrefilter for 429 rate limit handling
  $.ajaxPrefilter(function (options, originalOptions, jqXHR) {
    let originalError = options.error;

    options.error = function (jqXHR, textStatus, errorThrown) {
      if (jqXHR.status === 429) {
        showNewPageOnAJAXHTMLResponse(jqXHR.responseText);
        return; // Prevents both .error and .fail() from being called
      }

      if (originalError) {
        originalError.call(this, jqXHR, textStatus, errorThrown);
      }
    };
  });
}

/**
 * Global beforeSend callback for manual AJAX requests
 */
export const globalBeforeSend = function (xhr, settings) {
  const csrftoken = $("meta[name=csrf-token]").attr("content");
  if (!/^(GET|HEAD|OPTIONS|TRACE)$/i.test(settings.type) && !this.crossDomain) {
    xhr.setRequestHeader("X-CSRFToken", csrftoken);
  }
};
