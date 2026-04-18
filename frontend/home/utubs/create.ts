import type { Schema, SuccessResponse } from "../../types/api-helpers.d.ts";

import { $, getInputValue } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { ajaxCall } from "../../lib/ajax.js";
import type { RateLimitedXHR } from "../../lib/ajax.js";
import { highlightInput } from "../btns-forms.js";
import {
  getAllAccessibleUTubNames,
  sameNameWarningHideModal,
} from "./utils.js";
import { createUTubSelector, selectUTub } from "./selectors.js";
import { closeUTubSearchAndEraseInput } from "./search.js";
import { removeCreateUTubEventListeners } from "./deck.js";
import { getState, setState } from "../../store/app-store.js";

type CreateUtubRequest = Schema<"CreateUTubRequest">;
type CreateUtubResponse = SuccessResponse<"createUtub">;
type CreateUtubError = Schema<"ErrorResponse_UTubErrorCodes">;

function checkSameNameUTubOnCreate(name: string): void {
  if (getAllAccessibleUTubNames().includes(name)) {
    // UTub with same name exists. Confirm action with user
    sameUTubNameOnNewUTubWarningShowModal();
  } else {
    // UTub name is unique. Proceed with requested action
    createUTub();
  }
}

export function setCreateUTubEventListeners(): void {
  // Create new UTub
  const utubBtnCreate = $("#utubBtnCreate");
  utubBtnCreate.offAndOnExact("click.createUTub", function () {
    createUTubShowInput();
    closeUTubSearchAndEraseInput();
  });
}

// Attaches appropriate event listeners to the add UTub and cancel add UTub buttons
function createNewUTubEventListeners(): void {
  const utubSubmitBtnCreate = $("#utubSubmitBtnCreate");
  const utubCancelBtnCreate = $("#utubCancelBtnCreate");
  utubSubmitBtnCreate.offAndOnExact("click.createUTub", function () {
    checkSameNameUTubOnCreate(getInputValue("#utubNameCreate"));
  });

  utubCancelBtnCreate.offAndOnExact("click.createUTub", function () {
    createUTubHideInput();
  });

  const utubNameInput = $("#utubNameCreate");
  const utubDescriptionInput = $("#utubDescriptionCreate");

  utubNameInput.on("focus.createUTub", function () {
    utubNameInput.on(
      "keydown.createUTubName",
      function (event: JQuery.TriggeredEvent) {
        if ((event.originalEvent as KeyboardEvent).repeat) return;
        handleOnFocusEventListenersForCreateUTub(event);
      },
    );
  });

  utubNameInput.on("blur.createUTub", function () {
    utubNameInput.off(".createUTubName");
  });

  utubDescriptionInput.on("focus.createUTub", function () {
    utubDescriptionInput.on(
      "keydown.createUTubDescription",
      function (event: JQuery.TriggeredEvent) {
        handleOnFocusEventListenersForCreateUTub(event);
      },
    );
  });

  utubDescriptionInput.on("blur.createUTub", function () {
    utubDescriptionInput.off(".createUTubDescription");
  });
}

function removeNewUTubEventListeners(): void {
  $("#utubNameCreate").off("keydown.createUTubName");
  $("#utubDescriptionCreate").off("keydown.createUTubDescription");
  $("#utubNameCreate").off(".createUTub");
  $("#utubDescriptionCreate").off(".createUTub");
  $("#utubSubmitBtnCreate").off(".createUTub");
  $("#utubCancelBtnCreate").off(".createUTub");
}

function handleOnFocusEventListenersForCreateUTub(
  event: JQuery.TriggeredEvent,
): void {
  switch (event.key) {
    case KEYS.ENTER:
      // Handle enter key pressed
      checkSameNameUTubOnCreate(getInputValue("#utubNameCreate"));
      break;
    case KEYS.ESCAPE:
      // Handle escape key pressed
      $("#utubNameCreate").trigger("blur");
      $("#utubDescriptionCreate").trigger("blur");
      createUTubHideInput();
      break;
    default:
    /* no-op */
  }
}

function sameUTubNameOnNewUTubWarningShowModal(): void {
  const modalTitle = "Create a new UTub with this name?";
  const modalBody = `${APP_CONFIG.strings.UTUB_CREATE_SAME_NAME}`;
  const buttonTextDismiss = "Go Back to Editing";
  const buttonTextSubmit = "Create";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-secondary")
    .text(buttonTextDismiss)
    .offAndOnExact("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      sameNameWarningHideModal();
      highlightInput($("#utubNameCreate"));
    });

  $("#modalRedirect").hideClass();
  $("#modalRedirect").hide();

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .offAndOnExact("click", function (event: JQuery.TriggeredEvent) {
      event.preventDefault();
      createUTub();
      $("#utubNameCreate").val("");
      $("#utubDescriptionCreate").val("");
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").on("hidden.bs.modal", function () {
    // Refocus on the name's input box
    highlightInput($("#utubNameCreate"));
  });
}

// Shows new UTub input fields
function createUTubShowInput(): void {
  $("#createUTubWrap").showClassFlex();
  createNewUTubEventListeners();
  $("#utubNameCreate").trigger("focus");
  $("#listUTubs").hideClass();
  $("#UTubDeck").find(".button-container").hideClass();
  removeCreateUTubEventListeners();
}

// Hides new UTub input fields
export function createUTubHideInput(): void {
  $("#createUTubWrap").hideClass();
  $("#listUTubs").showClassFlex();
  $("#utubNameCreate").val("");
  $("#utubDescriptionCreate").val("");
  removeNewUTubEventListeners();
  resetUTubFailErrors();
  $("#UTubDeck").find(".button-container").showClassFlex();
  setCreateUTubEventListeners();
}

// Handles preparation for post request to create a new UTub
function createUTubSetup(): [string, CreateUtubRequest] {
  const postURL = APP_CONFIG.routes.createUTub;
  const newUTubName = getInputValue("#utubNameCreate");
  const newUTubDescription = getInputValue("#utubDescriptionCreate") || null;
  const data: CreateUtubRequest = {
    utubName: newUTubName,
    utubDescription: newUTubDescription,
  };

  return [postURL, data];
}

// Handles post request and response for adding a new UTub
function createUTub(): void {
  // Extract data to submit in POST request
  const [postURL, data] = createUTubSetup();
  resetUTubFailErrors();

  const request = ajaxCall("post", postURL, data);

  // Handle response
  request.done(function (
    response: CreateUtubResponse,
    _textStatus: JQuery.Ajax.SuccessTextStatus,
    xhr: JQuery.jqXHR,
  ) {
    if (xhr.status === 200) {
      createUTubSuccess(response);
      $("#listUTubs").showClassNormal();
    }
  });

  request.fail(function (xhr: JQuery.jqXHR) {
    createUTubFail(xhr);
  });
}

// Handle creation of new UTub
function createUTubSuccess(response: CreateUtubResponse): void {
  // DP 12/28/23 One problem is that confirmed DB changes aren't yet reflected on the page. Ex. 1. User makes UTub name change UTub1 -> UTub2. 2. User attempts to create new UTub UTub1. 3. Warning modal is thrown because no AJAX call made to update the passed UTubs json.
  const utubID = response.utubID;

  setState({
    utubs: [
      ...getState().utubs,
      {
        id: response.utubID,
        name: response.utubName,
        memberRole: APP_CONFIG.constants.MEMBER_ROLES.CREATOR,
      },
    ],
  });

  $("#confirmModal").modal("hide");

  // Remove createDiv; Reattach after addition of new UTub
  createUTubHideInput();

  // Create and append newly created UTub selector
  const index = parseInt($(".UTubSelector").first().attr("position") as string);
  const newUTubSelector = createUTubSelector(
    response.utubName,
    utubID,
    APP_CONFIG.constants.MEMBER_ROLES.CREATOR,
    index - 1,
  );
  $("#listUTubs").prepend(newUTubSelector);

  selectUTub(utubID, newUTubSelector);
}

// Handle error response display to user
function createUTubFail(xhr: JQuery.jqXHR): void {
  if ((xhr as RateLimitedXHR)._429Handled) return;

  if (!("responseJSON" in xhr)) {
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
  switch (xhr.status) {
    case 400: {
      // Backend always sends non-empty values for message/errors when present
      const responseJSON = xhr.responseJSON as CreateUtubError;
      if (responseJSON.message) {
        if (responseJSON.errors) {
          createUTubFailErrors(
            responseJSON.errors as Partial<
              Record<"utubName" | "utubDescription", string[]>
            >,
          );
        }
        break;
      }
    }
    // falls through
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

// Cycle through the valid errors for adding a UTub
function createUTubFailErrors(
  errors: Partial<Record<"utubName" | "utubDescription", string[]>>,
): void {
  for (const key in errors) {
    switch (key) {
      case "utubName":
      case "utubDescription": {
        const errorMessage = errors[key]![0];
        displayUTubFailErrors(key, errorMessage);
      }
    }
  }
}

// Show the error message and highlight the input box border red on error of field
function displayUTubFailErrors(key: string, errorMessage: string): void {
  $("#" + key + "Create-error")
    .addClass("visible")
    .text(errorMessage);
  $("#" + key + "Create").addClass("invalid-field");
}

function resetUTubFailErrors(): void {
  const newUTubFields = ["utubName", "utubDescription"];
  newUTubFields.forEach((fieldName) => {
    $("#" + fieldName + "Create").removeClass("invalid-field");
    $("#" + fieldName + "Create-error").removeClass("visible");
  });
}
