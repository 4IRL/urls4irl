import type { SuccessResponse } from "../../types/api-helpers.d.ts";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { ajaxCall } from "../../lib/ajax.js";
import type { RateLimitedXHR } from "../../lib/ajax.js";
import { hideInputs } from "../btns-forms.js";
import {
  isMobile,
  setMobileUIWhenUTubNotSelectedOrUTubDeleted,
} from "../mobile.js";
import { setUIWhenNoUTubSelected } from "../init.js";
import {
  hideInputsAndSetUTubDeckSubheader,
  resetUTubDeckIfNoUTubs,
} from "./deck.js";
import { emit, AppEvents } from "../../lib/event-bus.js";
import { getNumOfUTubs } from "./utils.js";
import { getState, setState } from "../../store/app-store.js";
import { closeUTubSearchAndEraseInput } from "./search.js";

type DeleteUtubResponse = SuccessResponse<"deleteUtub">;

export function setDeleteEventListeners(utubID: number): void {
  const utubBtnDelete = $("#utubBtnDelete");

  // Delete UTub
  utubBtnDelete.offAndOn("click.deleteUTub", function () {
    deleteUTubShowModal(utubID);
  });

  // Removes the keydown listener from the document once the button is blurred
  utubBtnDelete.offAndOn("blur.deleteUTub", function () {
    utubBtnDelete.off("keydown.deleteUTub");
  });
}

// Hide confirmation modal for deletion of the current UTub
function deleteUTubHideModal(): void {
  $("#confirmModal").modal("hide");
}

// Show confirmation modal for deletion of the current UTub
function deleteUTubShowModal(utubID: number): void {
  const modalTitle = "Are you sure you want to delete this UTub?";
  const modalBody = `${APP_CONFIG.strings.UTUB_DELETE_WARNING}`;
  const buttonTextDismiss = "Nevermind...";
  const buttonTextSubmit = "Delete this sucka!";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .removeClass()
    .addClass("btn btn-secondary")
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      deleteUTubHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-danger")
    .text(buttonTextSubmit)
    .offAndOn("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      deleteUTub(utubID);
      closeUTubSearchAndEraseInput();
    });

  $("#modalSubmit").prop("disabled", false);
  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();
}

// Handles deletion of a current UTub
function deleteUTub(utubID: number): void {
  $("#modalSubmit").prop("disabled", true);

  // Extract data to submit in POST request
  const postURL = APP_CONFIG.routes.deleteUTub(utubID);

  const request = ajaxCall("delete", postURL, []);

  // Handle response
  request.done(function (
    _response: DeleteUtubResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status === 200) {
      deleteUTubSuccess(utubID);
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    deleteUTubFail(xhr);
  });
}

function deleteUTubSuccess(utubID: number): void {
  hideInputs();

  // Close modal
  $("#confirmModal").modal("hide");
  $("#utubBtnDelete").hideClass();

  // Update UTub Deck
  const utubSelector = $(".UTubSelector[utubid=" + utubID + "]");

  setTimeout(function () {
    window.history.pushState(null, null, "/home");
    window.history.replaceState(null, null, "/home");
  }, 0);

  utubSelector.fadeOut("slow", () => {
    utubSelector.remove();

    setState({
      utubs: getState().utubs.filter((utub) => utub.id !== utubID),
      activeUTubID: null,
      activeUTubName: null,
      activeUTubDescription: null,
      isCurrentUserOwner: false,
      urls: [],
      tags: [],
      members: [],
      selectedTagIDs: [],
      selectedURLCardID: null,
    });

    // Reset all panels
    setUIWhenNoUTubSelected();

    hideInputsAndSetUTubDeckSubheader();
    emit(AppEvents.UTUB_DELETED, { utubID });

    if (getNumOfUTubs() === 0) {
      resetUTubDeckIfNoUTubs();
      $("#utubTagBtnCreate").hideClass();
    }

    if (isMobile()) setMobileUIWhenUTubNotSelectedOrUTubDeleted();
  });
}

function deleteUTubFail(xhr: JQuery.jqXHR): void {
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
  window.location.assign(APP_CONFIG.routes.errorPage);
  return;
}
