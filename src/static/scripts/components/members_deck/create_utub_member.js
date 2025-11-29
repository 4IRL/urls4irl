"use strict";

$(document).ready(function () {
  /* Bind click functions */
  const memberBtnCreate = $("#memberBtnCreate");

  // Add member to UTub
  memberBtnCreate.on("click.createMember", function () {
    createMemberShowInput();
  });

  memberBtnCreate.on("focus", function () {
    $(document).on("keyup.createMember", function (e) {
      if (e.key === KEYS.ENTER) createMemberShowInput();
    });
  });

  memberBtnCreate.on("blur", function () {
    $(document).off(".createMember");
  });
});

function setupCreateMemberEventListeners() {
  const memberSubmitBtnCreate = $("#memberSubmitBtnCreate");
  const memberCancelBtnCreate = $("#memberCancelBtnCreate");

  memberSubmitBtnCreate.offAndOn("click.createMemberSubmit", function (e) {
    if ($(e.target).closest("#memberSubmitBtnCreate").length > 0)
      createMember();
  });

  memberSubmitBtnCreate.offAndOn("focus.createMemberSubmit", function () {
    $(document).on("keyup.createMemberSubmit", function (e) {
      if (e.key === KEYS.ENTER) createMember();
    });
  });

  memberSubmitBtnCreate.offAndOn("blur.createMemberSubmit", function () {
    $(document).off("keyup.createMemberSubmit");
  });

  memberCancelBtnCreate.offAndOn("click.createMemberEscape", function (e) {
    if ($(e.target).closest("#memberCancelBtnCreate").length > 0)
      createMemberHideInput();
  });

  memberCancelBtnCreate.offAndOn("focus.createMemberEscape", function () {
    $(document).on("keyup.createMemberEscape", function (e) {
      if (e.key === KEYS.ENTER) createMemberHideInput();
    });
  });

  memberCancelBtnCreate.offAndOn("blur.createMemberEscape", function () {
    $(document).off("keyup.createMemberEscape");
  });

  const memberInput = $("#memberCreate");
  memberInput.on("focus.createMemberSubmitEscape", function () {
    bindCreateMemberFocusEventListeners();
  });
  memberInput.on("blur.createMemberSubmitSubmitEscape", function () {
    unbindCreateMemberFocusEventListeners();
  });
}

function removeCreateMemberEventListeners() {
  $("#memberCreate").off(".createMemberSubmitEscape");
}

function bindCreateMemberFocusEventListeners() {
  // Allow closing by pressing escape key
  $(document).on("keyup.createMemberSubmitEscape", function (e) {
    switch (e.key) {
      case KEYS.ENTER:
        // Handle enter key pressed
        createMember();
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
  $(document).off(".createMemberSubmitEscape");
}

// Clear member creation
function resetNewMemberForm() {
  $("#memberCreate").val(null);
}

// Shows new Member input fields
function createMemberShowInput() {
  $("#createMemberWrap").showClassFlex();
  $("#displayMemberWrap").hideClass();
  $("#memberBtnCreate").hideClass();
  setupCreateMemberEventListeners();
  $("#memberCreate").trigger("focus");
}

// Hides new Member input fields
function createMemberHideInput() {
  $("#createMemberWrap").hideClass();
  $("#displayMemberWrap").showClassFlex();
  $("#memberBtnCreate").showClassNormal();
  removeCreateMemberEventListeners();
  resetCreateMemberFailErrors();
  resetNewMemberForm();
}

// This function will extract the current selection data needed for POST request (member ID)
function createMemberSetup() {
  const postURL = routes.createMember(getActiveUTubID());

  const newMemberUsername = $("#memberCreate").val();
  const data = {
    username: newMemberUsername,
  };

  return [postURL, data];
}

function createMember() {
  // Extract data to submit in POST request
  let postURL, data;
  [postURL, data] = createMemberSetup();
  resetCreateMemberFailErrors();

  const request = ajaxCall("post", postURL, data);

  // Handle response
  request.done(function (response, _, xhr) {
    if (xhr.status === 200) {
      createMemberSuccess(response);
    }
  });

  request.fail(function (xhr, _, textStatus) {
    createMemberFail(xhr);
  });
}

// Perhaps update a scrollable/searchable list of members?
function createMemberSuccess(response) {
  resetNewMemberForm();

  // Create and append newly created Member badge - only creators can add members
  $("#listMembers").append(
    createMemberBadge(response.member.id, response.member.username, true),
  );

  createMemberHideInput();
  setMemberDeckForUTub(true);
}

function createMemberFail(xhr) {
  if (!xhr.hasOwnProperty("responseJSON")) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      $("body").html(xhr.responseText);
      return;
    }
    window.location.assign(routes.errorPage);
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
      window.location.assign(routes.errorPage);
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
