import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { ajaxCall } from "../../lib/ajax.js";
import {
  setTagDeckBtnsOnUpdateAllUTubTagsOpened,
  openUTubTagBtnMenuOnUTubTags,
  setTagDeckBtnsOnUpdateAllUTubTagsClosed,
  closeUTubTagBtnMenuOnUTubTags,
  setUnselectUpdateUTubTagEventListeners,
} from "./update-all.js";
import { KEYS } from "../../lib/constants.js";
import { updateURLsAndTagSubheaderWhenTagSelected } from "../urls/cards/filtering.js";

function deleteUTubTagHideModal() {
  $("#confirmModal").modal("hide");
}

export function deleteUTubTagShowModal(utubID, utubTagID, string) {
  const modalTitle = "Are you sure you want to delete this Tag?";
  const $strong = $("<strong>").text(`'${string}'`);
  const modalBody = `${APP_CONFIG.strings.UTUB_TAG_DELETE_WARNING}`.replace(
    "{{ tag_string }}",
    $strong.prop("outerHTML"),
  );
  const buttonTextDismiss = "Nevermind...";
  const buttonTextSubmit = "Delete this sucka!";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").html(modalBody);

  $("#modalDismiss")
    .removeClass()
    .addClass("btn btn-secondary")
    .offAndOn("click", function (e) {
      e.preventDefault();
      deleteUTubTagHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-danger")
    .text(buttonTextSubmit)
    .offAndOn("click", function (e) {
      e.preventDefault();
      deleteUTubTag(utubID, utubTagID);
    });

  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();
}

function deleteUTubTagSetup(utubID, utubTagID) {
  let deleteURL = APP_CONFIG.routes.deleteUTubTag(utubID, utubTagID);

  return deleteURL;
}

function deleteUTubTag(utubID, utubTagID) {
  let deleteUTubTagURL = deleteUTubTagSetup(utubID, utubTagID);

  const request = ajaxCall("delete", deleteUTubTagURL, []);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      deleteUTubTagSuccess(response);
    }
  });

  request.fail(function (xhr, textStatus, errorThrown) {
    deleteUTubTagFail(xhr);
  });
}

function deleteUTubTagSuccess(response) {
  // Close the modal
  $("#confirmModal").modal("hide");

  // Remove the UTub Tag
  const utubTagID = response.utubTag.utubTagID;

  const utubTagSelector = $(".tagFilter[data-utub-tag-id=" + utubTagID + "]");

  utubTagSelector.fadeOut("fast", () => {
    // Remove the tag from associated URLs
    const urlTagBadges = $(".tagBadge[data-utub-tag-id=" + utubTagID + "]");
    urlTagBadges.remove();

    utubTagSelector.remove();

    // If no tags are left then reset back to only showing Create UTub Tag Button
    if ($(".tagFilter").length === 0) {
      $("#utubTagBtnUpdateAllOpen").hideClass();
      $("#unselectAllTagFilters").hideClass();
      $("#utubTagCloseUpdateTagBtnContainer").hideClass();
      $("#utubTagStandardBtns").showClassFlex();
    }

    updateURLsAndTagSubheaderWhenTagSelected();
  });
}

function deleteUTubTagFail(xhr) {
  if (xhr._429Handled) return;

  if (
    xhr.status === 403 &&
    xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
  ) {
    // Handle invalid CSRF token error response
    $("body").html(xhr.responseText);
    return;
  }

  $("#HomeModalAlertBanner")
    .showClassNormal()
    .append(`${APP_CONFIG.strings.MAY_HAVE_ALREADY_BEEN_DELETED}<br>`)
    .append("Click ")
    .append(
      $(document.createElement("a"))
        .attr({
          href: "#",
          id: "Reloader",
        })
        .text("here"),
    )
    .append(" to reload the UTub.");

  $("#Reloader").offAndOn("click", (e) => {
    e.preventDefault();
    window.location.reload();
  });

  $("#modalSubmit").addClass("disabled");
  return;
}
