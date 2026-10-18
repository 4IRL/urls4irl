import type { SuccessResponse } from "../../../types/api-helpers.d.ts";

import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { isUtubLockedHandled } from "../../utub-locked.js";
import { getUpdatedURL, handleRejectFromGetURL } from "./get.js";
import {
  focusTargetAfterURLRowRemoval,
  removeURLCardFromDeck,
} from "./card-deck.js";
import { showURLDeletedToast } from "./delete-undo.js";
import { debug } from "../../../lib/debug.js";
import { refreshTrashCount } from "../../trash/count.js";

const log = debug("urls:cards");

type DeleteUrlResponse = SuccessResponse<"deleteUrl">;

const _deletesInFlight = new Set<number>();

/** True while any single-URL delete request is outstanding. */
export function isURLDeleteInFlight(): boolean {
  return _deletesInFlight.size > 0;
}

// Handles the request and response for moving an existing URL to Trash. Resolves
// true once the URL was deleted, false on any failure or stale/duplicate attempt.
export async function deleteURL({
  utubUrlID,
  urlCard,
  utubID,
  beforeFocus,
}: {
  utubUrlID: number;
  urlCard: JQuery;
  utubID: number;
  beforeFocus?: (target: JQuery) => void;
}): Promise<boolean> {
  // A second DELETE for the same id would 404 into the error page.
  if (_deletesInFlight.has(utubUrlID)) return false;
  _deletesInFlight.add(utubUrlID);
  // aria-disabled (not disabled) so the button keeps focus.
  const deleteBtn = urlCard.find(".urlBtnDelete");
  deleteBtn.attr("aria-disabled", "true");

  const settle = (): void => {
    _deletesInFlight.delete(utubUrlID);
  };
  const reenable = (): void => {
    deleteBtn.removeAttr("aria-disabled");
  };

  try {
    log("deleteURL flow start — verifying URL still exists before delete", {
      utubUrlID,
      utubID,
    });
    // Check for stale data
    await getUpdatedURL(utubID, utubUrlID, urlCard);
    // Extract data to submit in POST request
    const deleteURLRoute = APP_CONFIG.routes.deleteURL(utubID, utubUrlID);

    const request = ajaxCall("delete", deleteURLRoute, []);

    return await new Promise<boolean>((resolve) => {
      // Handle response
      request.done(function (
        response: DeleteUrlResponse,
        _: JQuery.Ajax.SuccessTextStatus,
        xhr: JQuery.jqXHR,
      ) {
        settle();
        if (xhr.status === 200) {
          try {
            deleteURLSuccess({ response, urlCard, utubID, beforeFocus });
          } catch (error) {
            log("deleteURLSuccess threw", error);
            reenable();
            resolve(false);
            return;
          }
          resolve(true);
          return;
        }
        reenable();
        resolve(false);
      });

      request.fail(function (xhr: JQuery.jqXHR) {
        settle();
        reenable();
        // Reroute to custom U4I 404 error page
        deleteURLFail(xhr);
        resolve(false);
      });
    });
  } catch (error) {
    settle();
    reenable();
    handleRejectFromGetURL(error as JQuery.jqXHR, urlCard, {
      showError: false,
    });
    return false;
  }
}

// Displays changes related to a successful removal of a URL
function deleteURLSuccess({
  response,
  urlCard,
  utubID,
  beforeFocus,
}: {
  response: DeleteUrlResponse;
  urlCard: JQuery;
  utubID: number;
  beforeFocus?: (target: JQuery) => void;
}): void {
  log("deleteURLSuccess — removing card and decrementing tag counts", {
    utubUrlID: response.URL.utubUrlID,
    affectedTagCount: (urlCard.attr("data-utub-url-tag-ids") ?? "")
      .split(",")
      .filter(Boolean).length,
  });
  void refreshTrashCount();
  const focusTarget = focusTargetAfterURLRowRemoval({ urlCard });
  removeURLCardFromDeck({
    urlCard,
    utubUrlID: response.URL.utubUrlID,
    animate: true,
    onRemoved: () => {
      // Only restore focus when the removed card held it (focus fell to body).
      const active = document.activeElement;
      const focusLost = active === null || active === document.body;
      if (
        focusTarget.length > 0 &&
        document.contains(focusTarget[0]) &&
        focusLost
      ) {
        beforeFocus?.(focusTarget);
        focusTarget.trigger("focus");
      }
    },
  });
  // Shown after the removal is started: deselecting a card clears the banner.
  showURLDeletedToast({
    utubID,
    deletedIDs: [response.URL.utubUrlID],
    skippedCount: 0,
    hiddenCount: 0,
    returnFocusTo: focusTarget,
  });
}

// Displays appropriate prompts and options to user following a failed removal of a URL
function deleteURLFail(xhr: JQuery.jqXHR): void {
  if (is429Handled(xhr)) return;
  if (isUtubLockedHandled(xhr)) return;

  if (
    xhr.status === 403 &&
    xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
  ) {
    // Handle invalid CSRF token error response
    $("body").html(xhr.responseText);
    return;
  }

  switch (xhr.status) {
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}
