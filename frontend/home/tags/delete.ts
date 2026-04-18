import type { SuccessResponse } from "../../types/api-helpers.d.ts";

import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { APP_CONFIG } from "../../lib/config.js";
import { emit, AppEvents } from "../../lib/event-bus.js";
import { $ } from "../../lib/globals.js";
import { getState, setState } from "../../store/app-store.js";

type DeleteUtubTagResponse = SuccessResponse<"deleteUtubTag">;

function deleteUTubTagHideModal(): void {
  $("#confirmModal").modal("hide");
}

export function deleteUTubTagShowModal(
  utubID: number,
  utubTagID: number,
  tagString: string,
): void {
  const modalTitle = "Are you sure you want to delete this Tag?";
  const $strong = $("<strong>").text(`'${tagString}'`);
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
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      deleteUTubTagHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-danger")
    .text(buttonTextSubmit)
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      deleteUTubTag(utubID, utubTagID);
    });

  $("#modalSubmit").prop("disabled", false);
  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();
}

function deleteUTubTag(utubID: number, utubTagID: number): void {
  $("#modalSubmit").prop("disabled", true);

  const deleteUTubTagURL = APP_CONFIG.routes.deleteUTubTag(utubID, utubTagID);

  const request = ajaxCall("delete", deleteUTubTagURL, []);

  // Handle response
  request.done(function (
    response: DeleteUtubTagResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status === 200) {
      deleteUTubTagSuccess(response);
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    deleteUTubTagFail(xhr);
  });
}

function deleteUTubTagSuccess(response: DeleteUtubTagResponse): void {
  // Close the modal
  $("#confirmModal").modal("hide");

  // Remove the UTub Tag
  const deletedTagID = response.utubTag.utubTagID;
  const affectedUrlIDs = new Set(response.utubUrlIDs);
  const filteredTags = getState().tags.filter((tag) => tag.id !== deletedTagID);
  const updatedUrls = getState().urls.map((url) =>
    affectedUrlIDs.has(url.utubUrlID)
      ? {
          ...url,
          utubUrlTagIDs: url.utubUrlTagIDs.filter((id) => id !== deletedTagID),
        }
      : url,
  );
  const filteredSelected = getState().selectedTagIDs.filter(
    (id) => id !== deletedTagID,
  );
  setState({
    tags: filteredTags,
    urls: updatedUrls,
    selectedTagIDs: filteredSelected,
  });

  const utubTagSelector = $(
    ".tagFilter[data-utub-tag-id=" + deletedTagID + "]",
  );

  utubTagSelector.fadeOut("fast", () => {
    // Remove the tag from associated URLs
    const urlTagBadges = $(".tagBadge[data-utub-tag-id=" + deletedTagID + "]");
    urlTagBadges.remove();

    utubTagSelector.remove();

    // If no tags are left then reset back to only showing Create UTub Tag Button
    if ($(".tagFilter").length === 0) {
      $("#utubTagBtnUpdateAllOpen").hideClass();
      $("#unselectAllTagFilters").hideClass();
      $("#utubTagCloseUpdateTagBtnContainer").hideClass();
      $("#utubTagStandardBtns").showClassFlex();
    }

    emit(AppEvents.TAG_DELETED, { utubTagID: deletedTagID });
  });
}

function deleteUTubTagFail(xhr: JQuery.jqXHR): void {
  $("#modalSubmit").prop("disabled", false);
  if (is429Handled(xhr)) return;

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

  $("#Reloader").offAndOn("click", (event: JQuery.TriggeredEvent) => {
    event.preventDefault();
    window.location.reload();
  });

  $("#modalSubmit").prop("disabled", true);
  return;
}
