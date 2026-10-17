import type { SuccessResponse } from "../../types/api-helpers.d.ts";

import { APP_CONFIG } from "../../lib/config.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { debug } from "../../lib/debug.js";
import { $ } from "../../lib/globals.js";
import { renderTrashList } from "./render.js";

const log = debug("trash:list");

type TrashListResponse = SuccessResponse<"getTrash">;

// Bumped by every load and by closeTrash(): a response carrying an older token
// belongs to a Trash view that is gone and must not render.
let requestToken = 0;

/** Drops any in-flight list response (called when Trash closes). */
export function invalidateTrashListRequests(): void {
  requestToken += 1;
}

function handleLoadFail(xhr: JQuery.jqXHR): void {
  if (is429Handled(xhr)) return;

  if (
    xhr.status === 403 &&
    xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
  ) {
    // Invalid CSRF token error response
    $("body").html(xhr.responseText);
    return;
  }
  window.location.assign(APP_CONFIG.routes.errorPage);
}

/** Fetches `GET /utubs/trash` and renders both tabs. */
export function loadTrashList(): Promise<void> {
  requestToken += 1;
  const token = requestToken;

  return new Promise((resolve) => {
    ajaxCall("get", APP_CONFIG.routes.getTrash, {})
      .done((response: TrashListResponse) => {
        if (token !== requestToken) {
          log("dropping stale trash list response");
          return;
        }
        renderTrashList({ list: response });
      })
      .fail((xhr: JQuery.jqXHR) => {
        if (token !== requestToken) return;
        handleLoadFail(xhr);
      })
      .always(() => resolve());
  });
}
