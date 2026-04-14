import type { operations } from "../../../types/api.d.ts";
import type { UtubTag, UtubUrlItem } from "../../../types/url.js";

import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall } from "../../../lib/ajax.js";
import type { RateLimitedXHR } from "../../../lib/ajax.js";
import { isTagInURL } from "./tags.js";
import {
  setTimeoutAndShowURLCardLoadingIcon,
  clearTimeoutIDAndHideLoadingIcon,
} from "../cards/loading.js";
import { getUpdatedURL, handleRejectFromGetURL } from "../cards/get.js";
import {
  updateTagFilterCount,
  TagCountOperation,
  updateTagFilteringOnURLOrURLTagDeletion,
} from "../cards/filtering.js";
import { getState, setState } from "../../../store/app-store.js";

type DeleteUrlTagResponse =
  operations["deleteUtubUrlTag"]["responses"][200]["content"]["application/json"];

/**
 * Prepares post request inputs for removal of a URL - tag
 */
function deleteURLTagSetup(
  utubID: number,
  utubUrlID: number,
  utubTagID: number,
): string {
  const deleteURLTag = APP_CONFIG.routes.deleteURLTag(
    utubID,
    utubUrlID,
    utubTagID,
  );

  return deleteURLTag;
}

/**
 * Remove tag from selected URL
 */
export async function deleteURLTag(
  utubTagID: number,
  tagBadge: JQuery,
  urlCard: JQuery,
  utubID: number,
): Promise<void> {
  const utubUrlID = parseInt(urlCard.attr("utuburlid") as string);
  const timeoutID: ReturnType<typeof setTimeout> =
    setTimeoutAndShowURLCardLoadingIcon(urlCard);
  try {
    await getUpdatedURL(utubID, utubUrlID, urlCard);

    // If tag was already deleted on update of URL, exit early
    if (!isTagInURL(utubTagID, urlCard)) {
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
      return;
    }

    // Extract data to submit in POST request
    const deleteURL = deleteURLTagSetup(utubID, utubUrlID, utubTagID);

    const request = ajaxCall("delete", deleteURL, []);

    // Handle response
    request.done(function (
      response: DeleteUrlTagResponse,
      _: JQuery.Ajax.SuccessTextStatus,
      xhr: JQuery.jqXHR,
    ) {
      if (xhr.status === 200) {
        deleteURLTagSuccess(response, tagBadge, urlCard);
      }
    });

    request.fail(function (xhr: JQuery.jqXHR) {
      deleteURLTagFail(xhr);
    });

    request.always(function () {
      clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    });
  } catch (error) {
    clearTimeoutIDAndHideLoadingIcon(timeoutID, urlCard);
    handleRejectFromGetURL(error as JQuery.jqXHR, urlCard, {
      showError: true,
      message: "Another user has deleted this URL",
    });
  }
}

/**
 * Displays changes related to a successful removal of a URL
 */
function deleteURLTagSuccess(
  response: DeleteUrlTagResponse,
  tagBadge: JQuery,
  urlCard: JQuery,
): void {
  const tagID = response.utubTag.utubTagID;
  const urlID = parseInt(urlCard.attr("utuburlid") as string);
  setState({
    urls: getState().urls.map((existingUrl: UtubUrlItem) =>
      existingUrl.utubUrlID === urlID
        ? { ...existingUrl, utubUrlTagIDs: response.utubUrlTagIDs }
        : existingUrl,
    ),
    // TODO: remove cast when Phase 9 narrows AppState.tags
    tags: (getState().tags as UtubTag[]).map((tag) =>
      tag.id === tagID ? { ...tag, tagApplied: response.tagCountsInUtub } : tag,
    ),
  });

  updateTagFilterCount(
    tagID,
    response.tagCountsInUtub,
    TagCountOperation.DECREMENT,
  );

  const currentURLTagIDs = urlCard.attr("data-utub-url-tag-ids") || "";

  if (currentURLTagIDs.trim()) {
    const tagIDs = currentURLTagIDs.split(",").map((part) => part.trim());
    const index = tagIDs.findIndex(
      (tagIdString) => parseInt(tagIdString) === tagID,
    );

    if (index !== -1) {
      tagIDs.splice(index, 1);
    }
    urlCard.attr("data-utub-url-tag-ids", tagIDs.join(","));
  }

  // Remove the tag badge from the URL card
  tagBadge.remove();

  // Hide the URL if selected tag is filtering
  updateTagFilteringOnURLOrURLTagDeletion();
}

/**
 * Displays appropriate prompts and options to user following a failed removal of a URL
 */
function deleteURLTagFail(xhr: JQuery.jqXHR): void {
  if ((xhr as RateLimitedXHR)._429Handled) return;

  if (
    xhr.status === 403 &&
    xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
  ) {
    // Handle invalid CSRF token error response
    $("body").html(xhr.responseText);
    return;
  }
  window.location.assign(APP_CONFIG.routes.errorPage);
}
