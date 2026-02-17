import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { ajaxCall } from "../../lib/ajax.js";
import { createMemberBadge } from "./members.js";
import { setMemberDeckForUTub } from "./deck.js";

export function setupShowCreateMemberFormEventListeners(utubID) {
  /* Bind click functions */
  const memberBtnCreate = $("#memberBtnCreate");

  // Add member to UTub
  memberBtnCreate.offAndOn("click.createMember", function () {
    createMemberShowInput(utubID);
  });

  memberBtnCreate.offAndOn("focus", function () {
    memberBtnCreate.on("keydown.createMember", function (e) {
      if (e.key === KEYS.ENTER) createMemberShowInput(utubID);
    });
  });

  memberBtnCreate.offAndOn("blur", function () {
    memberBtnCreate.off(".createMember");
  });
}

function setupCreateMemberEventListeners(utubID) {
  const memberSubmitBtnCreate = $("#memberSubmitBtnCreate");
  const memberCancelBtnCreate = $("#memberCancelBtnCreate");

  memberSubmitBtnCreate.offAndOnExact("click.createMemberSubmit", function (e) {
    createMember(utubID);
  });

  memberCancelBtnCreate.offAndOnExact("click.createMemberEscape", function (e) {
    createMemberHideInput();
  });

  const memberInput = $("#memberCreate");
  memberInput.on("focus.createMemberSubmitEscape", function () {
    bindCreateMemberFocusEventListeners(utubID, memberInput);
  });
  memberInput.on("blur.createMemberSubmitSubmitEscape", function () {
    unbindCreateMemberFocusEventListeners();
  });
}

function removeCreateMemberEventListeners() {
  $("#memberCreate").off(".createMemberSubmitEscape");
}

function bindCreateMemberFocusEventListeners(utubID, memberInput) {
  // Allow closing by pressing escape key
  memberInput.on("keydown.createMemberSubmitEscape", function (e) {
    if (e.originalEvent.repeat) return;
    switch (e.key) {
      case KEYS.ENTER:
        // Handle enter key pressed
        createMember(utubID);
        break;
      case KEYS.ESCAPE:
        // Handle escape  key pressed
        createMemberHideInput();
        break;
      default:
      /* no-op */
    }
  });
}

function unbindCreateMemberFocusEventListeners() {
  $("#memberCreate").off(".createMemberSubmitEscape");
}

// Clear member creation
function resetNewMemberForm() {
  $("#memberCreate").val(null);
}

// Shows new Member input fields
function createMemberShowInput(utubID) {
  $("#createMemberWrap").showClassFlex();
  $("#displayMemberWrap").hideClass();
  $("#memberBtnCreate").hideClass();
  setupCreateMemberEventListeners(utubID);
  $("#memberCreate").trigger("focus");
}

// Hides new Member input fields
export function createMemberHideInput() {
  $("#createMemberWrap").hideClass();
  $("#displayMemberWrap").showClassFlex();
  $("#memberBtnCreate").showClassNormal();
  removeCreateMemberEventListeners();
  resetCreateMemberFailErrors();
  resetNewMemberForm();
}

// This function will extract the current selection data needed for POST request (member ID)
function createMemberSetup(utubID) {
  const postURL = APP_CONFIG.routes.createMember(utubID);

  const newMemberUsername = $("#memberCreate").val();
  const data = {
    username: newMemberUsername,
  };

  return [postURL, data];
}

function createMember(utubID) {
  // Extract data to submit in POST request
  let postURL, data;
  [postURL, data] = createMemberSetup(utubID);
  resetCreateMemberFailErrors();

  const request = ajaxCall("post", postURL, data);

  // Handle response
  request.done(function (response, _, xhr) {
    if (xhr.status === 200) {
      createMemberSuccess(response, utubID);
    }
  });

  request.fail(function (xhr, _, textStatus) {
    createMemberFail(xhr);
  });
}

// Perhaps update a scrollable/searchable list of members?
function createMemberSuccess(response, utubID) {
  resetNewMemberForm();

  // Create and append newly created Member badge - only creators can add members
  $("#listMembers").append(
    createMemberBadge(
      response.member.id,
      response.member.username,
      true,
      utubID,
    ),
  );

  createMemberHideInput();
  setMemberDeckForUTub(true);
}

function createMemberFail(xhr) {
  if (xhr._429Handled) return;

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
    case 400:
      const responseJSON = xhr.responseJSON;
      const hasErrors = responseJSON.hasOwnProperty("errors");
      const hasMessage = responseJSON.hasOwnProperty("message");
      if (hasErrors) {
        // Show form errors
        createMemberFailErrors(responseJSON.errors);
        break;
      } else if (hasMessage) {
        // Show message
        displayCreateMemberFailErrors("username", responseJSON.message);
        break;
      }
    case 403:
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

function createMemberFailErrors(errors) {
  for (let key in errors) {
    switch (key) {
      case "username":
        let errorMessage = errors[key][0];
        displayCreateMemberFailErrors(key, errorMessage);
        return;
    }
  }
}

function displayCreateMemberFailErrors(_, errorMessage) {
  $("#memberCreate-error").addClass("visible").text(errorMessage);
  $("#memberCreate").addClass("invalid-field");
}

function resetCreateMemberFailErrors() {
  const createMemberFields = ["member"];
  createMemberFields.forEach((fieldName) => {
    $("#" + fieldName + "Create-error").removeClass("visible");
    $("#" + fieldName + "Create").removeClass("invalid-field");
  });
}
