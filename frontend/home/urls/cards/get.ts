import type { SuccessResponse } from "../../../types/api-helpers.d.ts";
import type { UtubUrlDetail, UtubTagOnAddDelete } from "../../../types/url.js";

import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { showNewPageOnAJAXHTMLResponse } from "../../../lib/page-utils.js";
import { modifyURLStringForDisplay } from "./url-string.js";
import { updateTagFilteringOnURLOrURLTagDeletion } from "./filtering.js";
import { isTagInUTubTagDeck } from "../../tags/utils.js";
import { removeTagFromTagDeckGivenTagID } from "../../tags/deck.js";
import { buildTagFilterInDeck } from "../../tags/tags.js";
import { createTagBadgeInURL } from "../tags/tags.js";
import { showURLDeckBannerError } from "../deck.js";

type GetUrlResponse = SuccessResponse<"getUrl">;

export async function getUpdatedURL(
  utubID: number,
  utubUrlID: number,
  urlCard: JQuery,
): Promise<void | JQuery.jqXHR> {
  return new Promise<void | JQuery.jqXHR>((resolve, reject) => {
    $.ajax({
      url: APP_CONFIG.routes.getURL(utubID, utubUrlID),
      type: "GET",
      dataType: "json",
      success: (
        response: GetUrlResponse,
        _: JQuery.Ajax.SuccessTextStatus,
        xhr: JQuery.jqXHR,
      ) => {
        if (xhr.status === 200 && "URL" in response) {
          updateURLBasedOnGetData(response.URL, urlCard, utubID);
          resolve();
        }
        resolve(xhr);
      },
      error: (xhr: JQuery.jqXHR) => {
        reject(xhr);
      },
    });
  });
}

function updateURLBasedOnGetData(
  urlUpdateResponse: UtubUrlDetail,
  urlCard: JQuery,
  utubID: number,
): void {
  const urlTitleElem = urlCard.find(".urlTitle");
  const urlStringElem = urlCard.find(".urlString");
  const urlTags = urlCard.find(".tagBadge");

  if (urlTitleElem.text() !== urlUpdateResponse.urlTitle) {
    urlTitleElem.text(urlUpdateResponse.urlTitle);
  }

  if (urlStringElem.attr("href") !== urlUpdateResponse.urlString) {
    const displayURL = modifyURLStringForDisplay(urlUpdateResponse.urlString);

    urlStringElem.attr({ href: urlUpdateResponse.urlString }).text(displayURL);
  }

  updateURLTagsAndUTubTagsBasedOnGetURLData(
    urlTags,
    urlUpdateResponse.urlTags,
    urlCard,
    utubID,
  );
}

function updateURLTagsAndUTubTagsBasedOnGetURLData(
  currentTags: JQuery,
  receivedTags: UtubTagOnAddDelete[],
  urlCard: JQuery,
  utubID: number,
): void {
  const receivedTagIDs = receivedTags.map((tag) => tag.utubTagID);
  const removedTagIDs: number[] = [];

  // Remove current tags that are not in received tags
  currentTags.each(function () {
    const utubTagID = parseInt($(this).attr("data-utub-tag-id") as string);
    if (!receivedTagIDs.includes(utubTagID)) {
      $(this).remove();
      removedTagIDs.push(utubTagID);
    }
  });

  // Based on IDs, find if tag still exists in UTub - if not, remove from tag deck
  for (
    let removedTagIndex = 0;
    removedTagIndex < removedTagIDs.length;
    removedTagIndex++
  ) {
    if (!isTagInUTubTagDeck(removedTagIDs[removedTagIndex])) {
      removeTagFromTagDeckGivenTagID(removedTagIDs[removedTagIndex]);
    }
  }

  // Add tags that are in received tags but not in current tags
  let exists: boolean;
  let receivedTag: UtubTagOnAddDelete;
  let currentTag: HTMLElement;
  for (
    let receivedTagIndex = 0;
    receivedTagIndex < receivedTags.length;
    receivedTagIndex++
  ) {
    exists = false;
    receivedTag = receivedTags[receivedTagIndex];

    for (
      let existingTagIndex = 0;
      existingTagIndex < currentTags.length;
      existingTagIndex++
    ) {
      currentTag = currentTags[existingTagIndex];
      exists =
        parseInt($(currentTag).attr("data-utub-tag-id") as string) ===
        receivedTag.utubTagID;
      if (exists) break;
    }

    if (!exists) {
      // Add tag to URL
      urlCard
        .find(".urlTagsContainer")
        .append(
          createTagBadgeInURL(
            receivedTag.utubTagID,
            receivedTag.tagString,
            urlCard,
            utubID,
          ),
        );

      // Add tag to UTub if it doesn't already exist
      if (!isTagInUTubTagDeck(receivedTag.utubTagID)) {
        $("#listTags").append(
          buildTagFilterInDeck(
            utubID,
            receivedTag.utubTagID,
            receivedTag.tagString,
          ),
        );
      }
    }
  }
}

export function handleRejectFromGetURL(
  xhr: JQuery.jqXHR,
  urlCard: JQuery,
  errorMessage: { showError: boolean; message?: string },
): void {
  switch (xhr.status) {
    case 429:
      const contentType = xhr.getResponseHeader("Content-Type");
      if (contentType && contentType.includes("text/html")) {
        showNewPageOnAJAXHTMLResponse(xhr.responseText);
      }
      break;
    case 403:
      // User not authorized for this UTub
      window.location.assign(APP_CONFIG.routes.errorPage);
      break;
    case 404:
      if (
        (xhr.getResponseHeader("content-type") || "").indexOf("text/html") >= 0
      ) {
        // UTub does not exist
        window.location.assign(APP_CONFIG.routes.errorPage);
        break;
      }
      // URL no longer exists
      if (errorMessage.showError) {
        showURLDeckBannerError(errorMessage.message ?? "");
      }
      deleteURLOnStale(urlCard);
      break;

    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
      break;
  }
}

function deleteURLOnStale(urlCard: JQuery): void {
  // Close modal in case URL was found stale while it's shown
  $("#confirmModal").modal("hide");
  urlCard.fadeOut("slow", function () {
    urlCard.remove();
    if ($("#listURLs .urlRow").length > 0) {
      updateTagFilteringOnURLOrURLTagDeletion();
    }
  });
}
