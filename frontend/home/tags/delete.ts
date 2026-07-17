import type { SuccessResponse } from "../../types/api-helpers.d.ts";

import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { emit, AppEvents } from "../../lib/event-bus.js";
import { $ } from "../../lib/globals.js";
import { emit as recordUIEvent } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { getState, setState } from "../../store/app-store.js";
import { applyAlternatingTagBackground } from "./search.js";
import { TAG_SCOPE } from "../../types/metrics-dim-values.js";

type DeleteUtubTagResponse = SuccessResponse<"deleteUtubTag">;

const log = debug("tags");

// scope: "url" is currently unused — a future per-URL tag-delete confirmation
// modal would activate the literal in _DimTagDelete* dimension models.
let _tagDeleteConfirmed: boolean = false;

function deleteUTubTagHideModal(): void {
  $("#confirmModal").modal("hide");
}

export function deleteUTubTagShowModal(
  utubID: number,
  utubTagID: number,
  tagString: string,
): void {
  _tagDeleteConfirmed = false;
  recordUIEvent({ event: UI_EVENTS.UI_TAG_DELETE_OPEN, scope: TAG_SCOPE.UTUB });

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
      _tagDeleteConfirmed = true;
      recordUIEvent({
        event: UI_EVENTS.UI_TAG_DELETE_CONFIRM,
        scope: TAG_SCOPE.UTUB,
      });
      deleteUTubTag(utubID, utubTagID);
    });

  $("#confirmModal").offAndOnExact("hidden.bs.modal.tagDelete", function () {
    if (!_tagDeleteConfirmed) {
      recordUIEvent({
        event: UI_EVENTS.UI_TAG_DELETE_CANCEL,
        scope: TAG_SCOPE.UTUB,
      });
    }
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

  log("deleteUTubTagSuccess — removed tag from UTub deck and all URLs", {
    deletedTagID: response.utubTag.utubTagID,
    affectedUrlCount: response.utubUrlIDs.length,
    wasInSelectedFilters: getState().selectedTagIDs.includes(
      response.utubTag.utubTagID,
    ),
  });

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

    // Removing a row shifts the visible parity, so re-stripe the survivors (this
    // path bypasses reapplyTagFilter, which handles striping on add/update).
    applyAlternatingTagBackground();

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

  log(
    "deleteUTubTag failed — likely already deleted by another user, showing reload banner",
    { status: xhr.status },
  );

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
