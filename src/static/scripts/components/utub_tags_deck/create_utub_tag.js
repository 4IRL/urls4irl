"use strict";

function setupOpenCreateUTubTagEventListeners(utubID) {
  const utubTagBtnCreate = $("#utubTagBtnCreate");

  // Add tag to UTub
  utubTagBtnCreate.offAndOn("click.createUTubTag", function () {
    createUTubTagShowInput(utubID);
  });

  utubTagBtnCreate.offAndOn("focus", function () {
    $(document).on("keyup.createUTubTag", function (e) {
      if (e.key === KEYS.ENTER) createUTubTagShowInput(utubID);
    });
  });

  utubTagBtnCreate.offAndOn("blur", function () {
    $(document).off(".createUTubTag");
  });
}

// Clear tag input form
function resetNewUTubTagForm() {
  $("#utubTagCreate").val(null);
}

function setupCreateUTubTagEventListeners(utubID) {
  const utubTagSubmitBtnCreate = $("#utubTagSubmitBtnCreate");
  const utubTagCancelBtnCreate = $("#utubTagCancelBtnCreate");

  utubTagSubmitBtnCreate.offAndOn("click.createUTubTagSubmit", function (e) {
    if ($(e.target).closest("#utubTagSubmitBtnCreate").length > 0)
      createUTubTag(utubID);
  });

  utubTagSubmitBtnCreate.offAndOn("focus.createUTubTagSubmit", function () {
    $(document).offAndOn("keyup.createUTubTagSubmit", function (e) {
      if (e.key === KEYS.ENTER) createUTubTag(utubID);
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
      if (e.key === KEYS.ENTER) createUTubTagHideInput();
    });
  });

  utubTagCancelBtnCreate.offAndOn("blur.createUTubTagEscape", function () {
    $(document).off("keyup.createUTubTagEscape");
  });

  const utubTagInput = $("#utubTagCreate");
  utubTagInput.offAndOn("focus.createUTubTagSubmitEscape", function () {
    bindCreateUTubTagFocusEventListeners(utubID);
  });
  utubTagInput.offAndOn("blur.createUTubTagSubmitSubmitEscape", function () {
    unbindCreateUTubTagFocusEventListeners();
  });
}

function removeCreateUTubTagEventListeners() {
  $("#memberCreate").off(".createUTubTagSubmitEscape");
}

function bindCreateUTubTagFocusEventListeners(utubID) {
  // Allow closing by pressing escape key
  $(document).on("keyup.createUTubTagSubmitEscape", function (e) {
    switch (e.key) {
      case KEYS.ENTER:
        // Handle enter key pressed
        createUTubTag(utubID);
        break;
      case KEYS.ESCAPE:
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

function createUTubTagShowInput(utubID) {
  $("#createUTubTagWrap").showClassFlex();
  $("#listTags").hideClass();
  $("#utubTagStandardBtns").hideClass();
  setupCreateUTubTagEventListeners(utubID);
  $("#utubTagCreate").trigger("focus");
}

function createUTubTagHideInput() {
  $("#createUTubTagWrap").hideClass();
  $("#listTags").showClassNormal();
  if (getNumOfUTubs() !== 0) $("#utubTagStandardBtns").showClassFlex();
  removeCreateUTubTagEventListeners();
  resetCreateUTubTagFailErrors();
  resetNewUTubTagForm();
}

function createUTubTagSetup(utubID) {
  const postURL = APP_CONFIG.routes.createUTubTag(utubID);

  const newUTubTag = $("#utubTagCreate").val();
  const data = {
    tagString: newUTubTag,
  };

  return [postURL, data];
}

function createUTubTag(utubID) {
  // Extract data to submit in POST request
  let postURL, data;
  [postURL, data] = createUTubTagSetup(utubID);
  resetCreateUTubTagFailErrors();

  const request = ajaxCall("post", postURL, data);

  // Handle response
  request.done(function (response, _, xhr) {
    if (xhr.status === 200) {
      createUTubTagSuccess(response, utubID);
    }
  });

  request.fail(function (xhr, _, textStatus) {
    createUTubTagFail(xhr);
  });
}

function createUTubTagSuccess(response, utubID) {
  resetNewUTubTagForm();

  // Create and append the new tag in the tag deck
  $("#listTags").append(
    buildTagFilterInDeck(
      utubID,
      response.utubTag.utubTagID,
      response.utubTag.tagString,
    ),
  );

  // Show unselect all and update buttons if not already shown
  $("#unselectAllTagFilters").showClassNormal();
  $("#utubTagBtnUpdateAllOpen").showClassNormal();

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
      window.location.assign(APP_CONFIG.routes.errorPage);
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
