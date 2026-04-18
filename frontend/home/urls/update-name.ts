import type { Schema, SuccessResponse } from "../../types/api-helpers.d.ts";
import type { UtubSummaryItem } from "../../types/utub.js";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { ajaxCall, is429Handled } from "../../lib/ajax.js";
import {
  getCurrentUTubName,
  getAllAccessibleUTubNames,
  sameNameWarningHideModal,
} from "../utubs/utils.js";
import { getState, setState } from "../../store/app-store.js";
import { highlightInput, showInput, hideInput } from "../btns-forms.js";
import {
  updateUTubDescriptionHideInput,
  updateUTubDescriptionShowInput,
} from "./update-description.js";
import { deselectAllURLs } from "./cards/selection.js";

type UpdateUtubNameRequest = Schema<"UpdateUTubNameRequest">;
type UpdateUtubNameResponse = SuccessResponse<"updateUtubName">;
type UpdateUtubNameError = Schema<"ErrorResponse_UTubErrorCodes">;

const UPDATE_UTUB_NAME_FIELD_NAMES = ["utubName"] as const;

type UpdateUtubNameFieldName = (typeof UPDATE_UTUB_NAME_FIELD_NAMES)[number];

function isUpdateUtubNameFieldName(
  key: string,
): key is UpdateUtubNameFieldName {
  return (UPDATE_UTUB_NAME_FIELD_NAMES as readonly string[]).includes(key);
}

function checkSameNameUTubOnUpdate(name: string, utubID: number): void {
  if (getAllAccessibleUTubNames().includes(name)) {
    // UTub with same name exists. Confirm action with user
    sameUTubNameOnUpdateUTubNameWarningShowModal(utubID);
  } else {
    // UTub name is unique. Proceed with requested action
    updateUTubName(utubID);
  }
}

export function setupUpdateUTubNameEventListeners(utubID: number): void {
  // Update UTub name
  $("#utubNameBtnUpdate").offAndOn("click", function (clickEvent) {
    deselectAllURLs();
    updateUTubDescriptionHideInput(utubID);
    updateUTubNameShowInput(utubID);
    // Prevent this event from bubbling up to the window to allow event listener creation
    if (!$(clickEvent.target).is(this)) return;
  });

  const utubNameSubmitBtnUpdate = $("#utubNameSubmitBtnUpdate");
  const utubNameCancelBtnUpdate = $("#utubNameCancelBtnUpdate");

  utubNameSubmitBtnUpdate.offAndOnExact("click.updateUTubname", function () {
    // Skip if update is identical to original
    if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
      updateUTubNameHideInput();
      return;
    }
    checkSameNameUTubOnUpdate($("#utubNameUpdate").val() as string, utubID);
  });

  utubNameCancelBtnUpdate.offAndOnExact("click.updateUTubname", function () {
    updateUTubNameHideInput();
  });
}

// Create event listeners to escape from updating UTub name
function setEventListenersToEscapeUpdateUTubName(utubID: number): void {
  // Allow user to still click in the text box
  $("#utubNameUpdate")
    .offAndOn("focus.updateUTubname", function () {
      $("#utubNameUpdate").on("keydown.updateUTubname", function (keyEvent) {
        if (keyEvent.originalEvent?.repeat) return;
        switch (keyEvent.key) {
          case KEYS.ENTER:
            // Handle enter key pressed
            // Skip if update is identical
            if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
              updateUTubNameHideInput();
              return;
            }
            checkSameNameUTubOnUpdate(
              $("#utubNameUpdate").val() as string,
              utubID,
            );
            break;
          case KEYS.ESCAPE:
            // Handle escape key pressed
            updateUTubNameHideInput();
            break;
          default:
          /* no-op */
        }
      });
    })
    .offAndOn("blur.updateUTubname", function () {
      $("#utubNameUpdate").off("keyup.updateUTubname");
    });

  // Bind clicking outside the window
  $(window).offAndOn("click.updateUTubname", function (windowClickEvent) {
    // Ignore clicks on the creation object
    if ($(windowClickEvent.target).closest("#utubNameBtnUpdate").length) return;

    // Ignore clicks on the input box
    if ($(windowClickEvent.target).is($("#utubNameUpdate"))) return;

    // Ignore clicks on the submit button
    if ($(windowClickEvent.target).closest("#utubNameSubmitBtnUpdate").length)
      return;

    // Ignore clicks on the cancel button
    if ($(windowClickEvent.target).closest("#utubNameCancelBtnUpdate").length)
      return;

    // Hide UTub name update fields
    updateUTubNameHideInput();
  });
}

function removeEventListenersToEscapeUpdateUTubName(): void {
  $(window).off(".updateUTubname");
  $("#utubNameUpdate").off(".updateUTubname");
}

function sameUTubNameOnUpdateUTubNameWarningShowModal(utubID: number): void {
  const modalTitle = "Continue with this UTub name?";
  const modalBody = `${APP_CONFIG.strings.UTUB_UPDATE_SAME_NAME}`;
  const buttonTextDismiss = "Go Back to Editing";
  const buttonTextSubmit = "Edit Name";
  let isSubmitting = false;

  removeEventListenersToEscapeUpdateUTubName();

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-secondary")
    .text(buttonTextDismiss)
    .offAndOnExact("click", function (dismissClickEvent) {
      dismissClickEvent.preventDefault();
      sameNameWarningHideModal();
      setEventListenersToEscapeUpdateUTubName(utubID);
      setTimeout(function () {
        highlightInput($("#utubNameUpdate"));
      }, 300);
    });

  $("#modalRedirect").hideClass();
  $("#modalRedirect").hide();

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .offAndOnExact("click", function () {
      isSubmitting = true;
      updateUTubName(utubID);
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").offAndOn("hidden.bs.modal", function (modalHiddenEvent) {
    modalHiddenEvent.stopPropagation();
    setEventListenersToEscapeUpdateUTubName(utubID);
    if (!isSubmitting) highlightInput($("#utubNameUpdate"));
  });
}

function allowUserToCreateDescriptionIfEmptyOnTitleUpdate(
  utubID: number,
): void {
  const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
  clickToCreateDesc.showClassNormal();
  clickToCreateDesc.offAndOnExact("click.createUTubdescription", function () {
    clickToCreateDesc
      .removeClass("opa-1 height-2rem")
      .addClass("opa-0 height-0");
    updateUTubNameHideInput();
    updateUTubDescriptionShowInput(utubID);
    clickToCreateDesc.off("click.createUTubdescription");
  });
}

// Shows input fields for updating an exiting UTub's name
function updateUTubNameShowInput(utubID: number): void {
  // Setup event listeners on window and escape/enter keys to escape the input box
  setEventListenersToEscapeUpdateUTubName(utubID);

  // Show update fields
  const utubNameUpdate = $("#utubNameUpdate");
  const parentTitleElem = utubNameUpdate.closest(".titleElement");
  parentTitleElem.addClass("m-top-bot-0-5rem");
  utubNameUpdate.val(getCurrentUTubName() ?? "");
  showInput("#utubNameUpdate");
  utubNameUpdate.trigger("focus");

  // Hide current name and update button
  $("#URLDeckHeader").hideClass();
  $("#utubNameBtnUpdate").hideClass();
  $("#urlBtnCreate").hideClass();

  // Handle hiding the button on mobile when hover events stay after touch
  $("#utubNameBtnUpdate").removeClass("visibleBtn");

  if ($("#URLDeckSubheader").text().length === 0) {
    allowUserToCreateDescriptionIfEmptyOnTitleUpdate(utubID);
  }
}

// Hides input fields for updating an existing UTub's name
export function updateUTubNameHideInput(): void {
  // Hide update fields
  hideInput("#utubNameUpdate");
  const utubNameUpdate = $("#utubNameUpdate");
  const parentTitleElem = utubNameUpdate.closest(".titleElement");
  parentTitleElem.removeClass("m-top-bot-0-5rem");

  // Show values and update button
  $("#URLDeckHeader").showClassNormal();
  $("#utubNameBtnUpdate").showClassNormal();
  $("#urlBtnCreate").showClassNormal();

  // Remove event listeners on window and escape/enter keys
  removeEventListenersToEscapeUpdateUTubName();

  // Handle giving mobile devices ability to see button again
  $("#utubNameBtnUpdate").addClass("visibleBtn");

  if ($("#URLDeckSubheader").text().length === 0) {
    $("#URLDeckSubheaderCreateDescription")
      .removeClass("opa-1 height-2rem")
      .addClass("opa-0 height-0");
  }

  // Remove any errors if shown
  resetUpdateUTubNameFailErrors();

  // Replace default value
  $("#utubNameUpdate").val($("#URLDeckHeader").text());
}

// Handles post request and response for updating an existing UTub's name
function updateUTubName(utubID: number): void {
  // Skip if update is identical
  if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
    updateUTubNameHideInput();
    return;
  }

  // Extract data to submit in POST request
  const [postURL, data] = updateUTubNameSetup(utubID);

  const request = ajaxCall("patch", postURL, data);

  // Handle response
  request.done(function (response: UpdateUtubNameResponse, _textStatus, xhr) {
    if (xhr.status === 200) {
      updateUTubNameSuccess(response);
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    updateUTubNameFail(xhr);
  });
}

// Handles preparation for post request to update an existing UTub
function updateUTubNameSetup(utubID: number): [string, UpdateUtubNameRequest] {
  const postURL = APP_CONFIG.routes.updateUTubName(utubID);

  const updatedUTubName = $("#utubNameUpdate").val() as string;
  const data: UpdateUtubNameRequest = { utubName: updatedUTubName };

  return [postURL, data];
}

// Handle update of UTub's name
function updateUTubNameSuccess(response: UpdateUtubNameResponse): void {
  const utubName = response.utubName;

  const utubs: UtubSummaryItem[] = getState().utubs;
  setState({
    activeUTubName: response.utubName,
    utubs: utubs.map((utub) =>
      utub.id === response.utubID ? { ...utub, name: response.utubName } : utub,
    ),
  });

  $("#confirmModal").modal("hide");

  // UTubDeck display updates
  const updatedUTubSelector = $("#listUTubs").find(".active");
  updatedUTubSelector.find(".UTubName").text(utubName);

  // Display updates
  setUTubNameAndDescription(utubName);
}

// Handle error response display to user
function updateUTubNameFail(xhr: JQuery.jqXHR): void {
  if (is429Handled(xhr)) return;

  if (!xhr.hasOwnProperty("responseJSON")) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      $("body").html(xhr.responseText);
      return;
    }
    window.location.assign(APP_CONFIG.routes.errorPage);
    return;
  }

  switch (xhr.status) {
    case 400: {
      const responseJSON = xhr.responseJSON as UpdateUtubNameError;
      if (responseJSON.hasOwnProperty("message")) {
        if (responseJSON.hasOwnProperty("errors"))
          updateUTubNameFailErrors(
            responseJSON.errors as Partial<
              Record<UpdateUtubNameFieldName, string[]>
            >,
          );
        break;
      }
    }
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

// Cycle through the valid errors for updating a UTub name
function updateUTubNameFailErrors(
  errors: Partial<Record<UpdateUtubNameFieldName, string[]>>,
): void {
  for (const errorFieldName in errors) {
    if (isUpdateUtubNameFieldName(errorFieldName)) {
      const errorMessage = errors[errorFieldName]![0];
      displayUpdateUTubNameFailErrors(errorFieldName, errorMessage);
      return;
    }
  }
}

// Show the error message and highlight the input box border red on error of field
function displayUpdateUTubNameFailErrors(
  key: string,
  errorMessage: string,
): void {
  $("#" + key + "Update-error")
    .addClass("visible")
    .text(errorMessage);
  $("#" + key + "Update").addClass("invalid-field");
}

function resetUpdateUTubNameFailErrors(): void {
  $("#utubNameUpdate-error").removeClass("visible");
  $("#utubNameUpdate").removeClass("invalid-field");
}

export function setUTubNameAndDescription(utubName: string): void {
  $("#URLDeckHeader").text(utubName);
  $("#utubNameUpdate").val(utubName);
  updateUTubNameHideInput();
}
