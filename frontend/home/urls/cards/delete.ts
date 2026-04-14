import type { operations } from "../../../types/api.d.ts";
import type { UtubUrlItem } from "../../../types/url.js";

import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall } from "../../../lib/ajax.js";
import type { RateLimitedXHR } from "../../../lib/ajax.js";
import { getUpdatedURL, handleRejectFromGetURL } from "./get.js";
import { updateTagFilteringOnURLOrURLTagDeletion } from "./filtering.js";
import { getState, setState } from "../../../store/app-store.js";

type DeleteUrlResponse =
  operations["deleteUrl"]["responses"][200]["content"]["application/json"];

// Hide confirmation modal for removal of the selected URL
export function deleteURLHideModal(): void {
  $("#confirmModal").modal("hide").removeClass("deleteUrlModal");
}

// Show confirmation modal for removal of the selected existing URL from current UTub
export function deleteURLShowModal(
  utubUrlID: number,
  urlCard: JQuery,
  utubID: number,
): void {
  const modalTitle = "Are you sure you want to delete this URL from the UTub?";
  const modalText = `${APP_CONFIG.strings.DELETE_URL_WARNING}`;
  const buttonTextDismiss = "Just kidding";
  const buttonTextSubmit = "Delete URL";

  $("#confirmModalTitle").text(modalTitle);
  $("#confirmModalBody").text(modalText);

  $("#modalDismiss")
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      deleteURLHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      deleteURL(utubUrlID, urlCard, utubID);
    })
    .text(buttonTextSubmit);

  $("#modalSubmit").prop("disabled", false);
  $("#confirmModal")
    .addClass("deleteUrlModal")
    .modal("show")
    .on("hidden.bs.modal", () => {
      $("#confirmModal").removeClass("deleteUrlModal");
    });
  $("#modalRedirect").hide();
  $("#modalRedirect").hideClass();
}

// Handles post request and response for removing an existing URL from current UTub, after confirmation
async function deleteURL(
  utubUrlID: number,
  urlCard: JQuery,
  utubID: number,
): Promise<void> {
  $("#modalSubmit").prop("disabled", true);

  try {
    // Check for stale data
    await getUpdatedURL(utubID, utubUrlID, urlCard);
    // Extract data to submit in POST request
    const deleteURL = APP_CONFIG.routes.deleteURL(utubID, utubUrlID);

    const request = ajaxCall("delete", deleteURL, []);

    // Handle response
    request.done(function (
      response: DeleteUrlResponse,
      _: JQuery.Ajax.SuccessTextStatus,
      xhr: JQuery.jqXHR,
    ) {
      if (xhr.status === 200) {
        deleteURLSuccess(response, urlCard);
      }
    });

    request.fail(function (xhr: JQuery.jqXHR) {
      // Reroute to custom U4I 404 error page
      deleteURLFail(xhr);
    });
  } catch (error) {
    $("#modalSubmit").prop("disabled", false);
    handleRejectFromGetURL(error as JQuery.jqXHR, urlCard, {
      showError: false,
    });
  }
}

// Displays changes related to a successful removal of a URL
function deleteURLSuccess(response: DeleteUrlResponse, urlCard: JQuery): void {
  // Close modal
  $("#confirmModal").modal("hide");
  setState({
    urls: getState().urls.filter(
      (url: UtubUrlItem) => url.utubUrlID !== response.URL.utubUrlID,
    ),
  });
  const currentURLTagIDs = urlCard.attr("data-utub-url-tag-ids") || "";
  if (currentURLTagIDs.trim()) {
    const tagIDs = currentURLTagIDs.split(",").map((part) => part.trim());
    let tagCountElem: JQuery;
    let tagID: string;
    let tagCountText: string[];
    for (let tagIdIndex = 0; tagIdIndex < tagIDs.length; tagIdIndex++) {
      tagID = tagIDs[tagIdIndex];
      tagCountElem = $(
        `.tagFilter[data-utub-tag-id=${tagID}]` + " .tagAppliedToUrlsCount",
      );
      tagCountText = tagCountElem.text().split(" / ");
      if (!tagCountText || tagCountText.length !== 2) continue;
      tagCountElem.text(
        `${parseInt(tagCountText[0]) - 1}` +
          " / " +
          `${parseInt(tagCountText[1]) - 1}`,
      );
    }
  }

  urlCard.fadeOut("slow", function () {
    urlCard.remove();
    if ($("#listURLs .urlRow").length === 0) {
      $("#accessAllURLsBtn").hideClass();
      $("#NoURLsSubheader").showClassFlex();
      $("#urlBtnDeckCreateWrap").showClassFlex();
    } else {
      updateTagFilteringOnURLOrURLTagDeletion();
    }
  });
}

// Displays appropriate prompts and options to user following a failed removal of a URL
function deleteURLFail(xhr: JQuery.jqXHR): void {
  $("#modalSubmit").prop("disabled", false);
  if ((xhr as RateLimitedXHR)._429Handled) return;

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
