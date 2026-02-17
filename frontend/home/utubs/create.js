import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { ajaxCall } from "../../lib/ajax.js";
import { highlightInput } from "../btns-forms.js";
import {
  getAllAccessibleUTubNames,
  sameNameWarningHideModal,
} from "./utils.js";
import { createUTubSelector, selectUTub } from "./selectors.js";
import { closeUTubSearchAndEraseInput } from "./search.js";
import { removeCreateUTubEventListeners } from "./deck.js";

function checkSameNameUTubOnCreate(name) {
  if (getAllAccessibleUTubNames().includes(name)) {
    // UTub with same name exists. Confirm action with user
    sameUTubNameOnNewUTubWarningShowModal();
  } else {
    // UTub name is unique. Proceed with requested action
    createUTub();
  }
}

export function setCreateUTubEventListeners() {
  // Create new UTub
  const utubBtnCreate = $("#utubBtnCreate");
  utubBtnCreate.offAndOnExact("click.createUTub", function (e) {
    createUTubShowInput();
    closeUTubSearchAndEraseInput();
  });
}

// Attaches appropriate event listeners to the add UTub and cancel add UTub buttons
function createNewUTubEventListeners() {
  const utubSubmitBtnCreate = $("#utubSubmitBtnCreate");
  const utubCancelBtnCreate = $("#utubCancelBtnCreate");
  utubSubmitBtnCreate.offAndOnExact("click.createUTub", function (e) {
    checkSameNameUTubOnCreate($("#utubNameCreate").val());
  });

  utubCancelBtnCreate.offAndOnExact("click.createUTub", function (e) {
    createUTubHideInput();
  });

  const utubNameInput = $("#utubNameCreate");
  const utubDescriptionInput = $("#utubDescriptionCreate");

  utubNameInput.on("focus.createUTub", function (e) {
    utubNameInput.on("keydown.createUTubName", function (e) {
      if (e.originalEvent.repeat) return;
      handleOnFocusEventListenersForCreateUTub(e);
    });
  });

  utubNameInput.on("blur.createUTub", function () {
    utubNameInput.off(".createUTubName");
  });

  utubDescriptionInput.on("focus.createUTub", function () {
    utubDescriptionInput.on("keydown.createUTubDescription", function (e) {
      handleOnFocusEventListenersForCreateUTub(e);
    });
  });

  utubDescriptionInput.on("blur.createUTub", function () {
    utubDescriptionInput.off(".createUTubDescription");
  });
}

function removeNewUTubEventListeners() {
  $("#utubNameCreate").off("keydown.createUTubName");
  $("#utubDescriptionCreate").off("keydown.createUTubDescription");
  $("#utubNameCreate").off(".createUTub");
  $("#utubDescriptionCreate").off(".createUTub");
  $("#utubSubmitBtnCreate").off(".createUTub");
  $("#utubCancelBtnCreate").off(".createUTub");
}

function handleOnFocusEventListenersForCreateUTub(e) {
  switch (e.key) {
    case KEYS.ENTER:
      // Handle enter key pressed
      checkSameNameUTubOnCreate($("#utubNameCreate").val());
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

function sameUTubNameOnNewUTubWarningShowModal() {
  const modalTitle = "Create a new UTub with this name?";
  const modalBody = `${APP_CONFIG.strings.UTUB_CREATE_SAME_NAME}`;
  const buttonTextDismiss = "Go Back to Editing";
  const buttonTextSubmit = "Create";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-secondary")
    .text(buttonTextDismiss)
    .offAndOnExact("click", function (e) {
      e.preventDefault();
      sameNameWarningHideModal();
      highlightInput($("#utubNameCreate"));
    });

  $("#modalRedirect").hideClass();
  $("#modalRedirect").hide();

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .offAndOnExact("click", function (e) {
      e.preventDefault();
      createUTub();
      $("#utubNameCreate").val(null);
      $("#utubDescriptionCreate").val(null);
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").on("hidden.bs.modal", function (e) {
    // Refocus on the name's input box
    highlightInput($("#utubNameCreate"));
  });
}

// Shows new UTub input fields
function createUTubShowInput() {
  $("#createUTubWrap").showClassFlex();
  createNewUTubEventListeners();
  $("#utubNameCreate").trigger("focus");
  $("#listUTubs").hideClass();
  $("#UTubDeck").find(".button-container").hideClass();
  removeCreateUTubEventListeners();
}

// Hides new UTub input fields
export function createUTubHideInput() {
  $("#createUTubWrap").hideClass();
  $("#listUTubs").showClassFlex();
  $("#utubNameCreate").val(null);
  $("#utubDescriptionCreate").val(null);
  removeNewUTubEventListeners();
  resetUTubFailErrors();
  $("#UTubDeck").find(".button-container").showClassFlex();
  setCreateUTubEventListeners();
}

// Handles preparation for post request to create a new UTub
function createUTubSetup() {
  const postURL = APP_CONFIG.routes.createUTub;
  const newUTubName = $("#utubNameCreate").val();
  const newUTubDescription = $("#utubDescriptionCreate").val();
  let data = { utubName: newUTubName, utubDescription: newUTubDescription };

  return [postURL, data];
}

// Handles post request and response for adding a new UTub
function createUTub() {
  // Extract data to submit in POST request
  let postURL, data;
  [postURL, data] = createUTubSetup();
  resetUTubFailErrors();

  let request = ajaxCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      createUTubSuccess(response);
      $("#listUTubs").showClassNormal();
    }
  });

  request.fail(function (xhr, _, textStatus) {
    createUTubFail(xhr);
  });
}

// Handle creation of new UTub
function createUTubSuccess(response) {
  // DP 12/28/23 One problem is that confirmed DB changes aren't yet reflected on the page. Ex. 1. User makes UTub name change UTub1 -> UTub2. 2. User attempts to create new UTub UTub1. 3. Warning modal is thrown because no AJAX call made to update the passed UTubs json.
  const utubID = response.utubID;

  $("#confirmModal").modal("hide");

  // Remove createDiv; Reattach after addition of new UTub
  createUTubHideInput(utubID);

  // Create and append newly created UTub selector
  const index = parseInt($(".UTubSelector").first().attr("position"));
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
function createUTubFail(xhr) {
  if (xhr._429Handled) return;

  if (!xhr.hasOwnProperty("responseJSON")) {
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
    case 400:
      const responseJSON = xhr.responseJSON;
      if (responseJSON.hasOwnProperty("message")) {
        if (responseJSON.hasOwnProperty("errors"))
          createUTubFailErrors(responseJSON.errors);
        break;
      }
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

// Cycle through the valid errors for adding a UTub
function createUTubFailErrors(errors) {
  for (let key in errors) {
    switch (key) {
      case "utubName":
      case "utubDescription":
        let errorMessage = errors[key][0];
        displayUTubFailErrors(key, errorMessage);
    }
  }
}

// Show the error message and highlight the input box border red on error of field
function displayUTubFailErrors(key, errorMessage) {
  $("#" + key + "Create-error")
    .addClass("visible")
    .text(errorMessage);
  $("#" + key + "Create").addClass("invalid-field");
}

function resetUTubFailErrors() {
  const newUTubFields = ["utubName", "utubDescription"];
  newUTubFields.forEach((fieldName) => {
    $("#" + fieldName + "Create").removeClass("invalid-field");
    $("#" + fieldName + "Create-error").removeClass("visible");
  });
}
