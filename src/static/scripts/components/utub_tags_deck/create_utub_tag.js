"use strict";

$(document).ready(function () {
  /* Bind click functions */
  const utubTagBtnCreate = $("#utubTagBtnCreate");

  // Add tag to UTub
  utubTagBtnCreate.on("click.createUTubTag", function () {
    createUTubTagShowInput();
  });

  utubTagBtnCreate.on("focus", function () {
    $(document).on("keyup.createUTubTag", function (e) {
      if (e.which === 13) createUTubTagShowInput();
    });
  });

  utubTagBtnCreate.on("blur", function () {
    $(document).off(".createUTubTag");
  });
});

// Clear tag input form
function resetNewUTubTagForm() {
  $("#utubTagCreate").val(null);
}

// Shows new UTub Tag input fields
function createUTubTagShowInput() {
  showIfHidden($("#createUTubTagWrap"));
  hideIfShown($("#listTags"));
  hideIfShown($("#utubTagBtnCreate"));
  setupCreateUTubTagEventListeners();
  $("#utubTagCreate").trigger("focus");
}

function setupCreateUTubTagEventListeners() {
  const utubTagSubmitBtnCreate = $("#utubTagSubmitBtnCreate");
  const utubTagCancelBtnCreate = $("#utubTagCancelBtnCreate");

  utubTagSubmitBtnCreate.offAndOn("click.createUTubTagSubmit", function (e) {
    if ($(e.target).closest("#utubTagSubmitBtnCreate").length > 0)
      createUTubTag();
  });

  utubTagSubmitBtnCreate.offAndOn("focus.createUTubTagSubmit", function () {
    $(document).on("keyup.createUTubTagSubmit", function (e) {
      if (e.which === 13) createUTubTag();
    });
  });

  utubTagSubmitBtnCreate.offAndOn("blur.createUTubTagSubmit", function () {
    $(document).off("keyup.createUTubTagSubmit");
  });

  utubTagCancelBtnCreate.offAndOn("click.createUTubTagEscape", function (e) {
    if ($(e.target).closest("#utubTagCancelBtnCreate").length > 0)
      createUTubTagHideInput();
  });

  utubTagCancelBtnCreate.offAndOn("focus.createUTubTagEscape", function () {
    $(document).on("keyup.createUTubTagEscape", function (e) {
      if (e.which === 13) createUTubTagHideInput();
    });
  });

  utubTagCancelBtnCreate.offAndOn("blur.createUTubTagEscape", function () {
    $(document).off("keyup.createUTubTagEscape");
  });

  const utubTagInput = $("#utubTagCreate");
  utubTagInput.on("focus.createUTubTagSubmitEscape", function () {
    bindCreateUTubTagFocusEventListeners();
  });
  utubTagInput.on("blur.createUTubTagSubmitSubmitEscape", function () {
    unbindCreateUTubTagFocusEventListeners();
  });
}

function removeCreateUTubTagEventListeners() {
  $("#memberCreate").off(".createUTubTagSubmitEscape");
}

function bindCreateUTubTagFocusEventListeners() {
  // Allow closing by pressing escape key
  $(document).on("keyup.createUTubTagSubmitEscape", function (e) {
    switch (e.which) {
      case 13:
        // Handle enter key pressed
        createUTubTag();
        break;
      case 27:
        // Handle escape  key pressed
        createUTubTagHideInput();
        break;
      default:
      /* no-op */
    }
  });
}

function unbindCreateUTubTagFocusEventListeners() {
  $(document).off(".createUTubTagSubmitEscape");
}

// Hides new UTubTag input fields
function createUTubTagHideInput() {
  hideIfShown($("#createUTubTagWrap"));
  $("#createUTubTagWrap").hide();
  showIfHidden($("#listTags"));
  if (getNumOfUTubs() !== 0) showIfHidden($("#utubTagBtnCreate"));
  removeCreateUTubTagEventListeners();
  resetCreateUTubTagFailErrors();
  resetNewUTubTagForm();
}

function createUTubTagSetup() {
  const postURL = routes.createUTubTag(getActiveUTubID());

  const newUTubTag = $("#utubTagCreate").val();
  const data = {
    tagString: newUTubTag,
  };

  return [postURL, data];
}

function createUTubTag() {
  // Extract data to submit in POST request
  let postURL, data;
  [postURL, data] = createUTubTagSetup();
  resetCreateUTubTagFailErrors();

  const request = ajaxCall("post", postURL, data);

  // Handle response
  request.done(function (response, _, xhr) {
    if (xhr.status === 200) {
      createUTubTagSuccess(response);
    }
  });

  request.fail(function (xhr, _, textStatus) {
    createUTubTagFail(xhr);
  });
}

function createUTubTagSuccess(response) {
  resetNewUTubTagForm();

  // Create and append the new tag in the tag deck
  $("#listTags").append(
    buildTagFilterInDeck(
      response.utubTag.utubTagID,
      response.utubTag.tagString,
    ),
  );

  // Show unselect all button if not already shown
  showIfHidden($("#unselectAllTagFilters"));

  createUTubTagHideInput();
}

function createUTubTagFail(xhr) {
  if (!xhr.hasOwnProperty("responseJSON")) {
    if (
      xhr.status === 403 &&
      xhr.getResponseHeader("Content-Type") === "text/html; charset=utf-8"
    ) {
      // Handle invalid CSRF token error response
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
        createUTubTagFailErrors(responseJSON.errors);
        break;
      } else if (hasMessage) {
        // Show message
        displayCreateUTubTagFailErrors("utubTag", responseJSON.message);
        break;
      }
    case 403:
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}

function createUTubTagFailErrors(errors) {
  for (let key in errors) {
    switch (key) {
      case "tagString":
        let errorMessage = errors[key][0];
        displayCreateUTubTagFailErrors(key, errorMessage);
        return;
    }
  }
}

function displayCreateUTubTagFailErrors(_, errorMessage) {
  $("#utubTagCreate-error").addClass("visible").text(errorMessage);
  $("#utubTagCreate").addClass("invalid-field");
}

function resetCreateUTubTagFailErrors() {
  const createUTubTagFields = ["utubTag"];
  createUTubTagFields.forEach((fieldName) => {
    $("#" + fieldName + "Create-error").removeClass("visible");
    $("#" + fieldName + "Create").removeClass("invalid-field");
  });
}
