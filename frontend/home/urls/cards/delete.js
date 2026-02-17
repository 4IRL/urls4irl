import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { ajaxCall } from "../../../lib/ajax.js";
import { getUpdatedURL, handleRejectFromGetURL } from "./get.js";
import { updateTagFilteringOnURLOrURLTagDeletion } from "./filtering.js";

// Hide confirmation modal for removal of the selected URL
export function deleteURLHideModal() {
  $("#confirmModal").modal("hide").removeClass("deleteUrlModal");
}

// Show confirmation modal for removal of the selected existing URL from current UTub
export function deleteURLShowModal(utubUrlID, urlCard, utubID) {
  const modalTitle = "Are you sure you want to delete this URL from the UTub?";
  const modalText = `${APP_CONFIG.strings.DELETE_URL_WARNING}`;
  const buttonTextDismiss = "Just kidding";
  const buttonTextSubmit = "Delete URL";

  $("#confirmModalTitle").text(modalTitle);
  $("#confirmModalBody").text(modalText);

  $("#modalDismiss")
    .offAndOn("click", function (e) {
      e.preventDefault();
      deleteURLHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .offAndOn("click", function (e) {
      e.preventDefault();
      deleteURL(utubUrlID, urlCard, utubID);
    })
    .text(buttonTextSubmit);

  $("#confirmModal")
    .addClass("deleteUrlModal")
    .modal("show")
    .on("hidden.bs.modal", () => {
      $("#confirmModal").removeClass("deleteUrlModal");
    });
  $("#modalRedirect").hide();
  $("#modalRedirect").hideClass();
}

// Prepares post request inputs for removal of a URL
function deleteURLSetup(utubID, utubUrlID) {
  const deleteURL = APP_CONFIG.routes.deleteURL(utubID, utubUrlID);
  return deleteURL;
}

// Handles post request and response for removing an existing URL from current UTub, after confirmation
async function deleteURL(utubUrlID, urlCard, utubID) {
  try {
    // Check for stale data
    await getUpdatedURL(utubID, utubUrlID, urlCard);
    // Extract data to submit in POST request
    const deleteURL = deleteURLSetup(utubID, utubUrlID);

    const request = ajaxCall("delete", deleteURL, []);

    // Handle response
    request.done(function (response, textStatus, xhr) {
      if (xhr.status === 200) {
        deleteURLSuccess(response, urlCard);
      }
    });

    request.fail(function (xhr, _, textStatus) {
      // Reroute to custom U4I 404 error page
      deleteURLFail(xhr);
    });
  } catch (error) {
    handleRejectFromGetURL(error, urlCard, { showError: false });
  }
}

// Displays changes related to a successful removal of a URL
function deleteURLSuccess(response, urlCard) {
  // Close modal
  $("#confirmModal").modal("hide");
  const currentURLTagIDs = urlCard.attr("data-utub-url-tag-ids") || "";
  if (currentURLTagIDs.trim()) {
    let tagIDs = currentURLTagIDs.split(",").map((s) => s.trim());
    let tagCountElem, tagID, tagCountText;
    for (let i = 0; i < tagIDs.length; i++) {
      tagID = tagIDs[i];
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
function deleteURLFail(xhr) {
  if (xhr._429Handled) return;

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
