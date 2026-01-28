"use strict";

function setupUpdateUTubDescriptionEventListeners(utubID) {
  const utubDescriptionSubmitBtnUpdate = $("#utubDescriptionSubmitBtnUpdate");
  const utubDescriptionCancelBtnUpdate = $("#utubDescriptionCancelBtnUpdate");

  // Update UTub description
  $("#updateUTubDescriptionBtn").offAndOnExact("click", function (e) {
    deselectAllURLs();
    updateUTubNameHideInput();
    updateUTubDescriptionShowInput(utubID);
  });

  utubDescriptionSubmitBtnUpdate.offAndOnExact("click", function (e) {
    updateUTubDescription(utubID);
  });

  utubDescriptionCancelBtnUpdate.onExact("click", function (e) {
    updateUTubDescriptionHideInput(utubID);
  });
}

// Create event listeners to escape from updating UTub name
function setEventListenersToEscapeUpdateUTubDescription(utubID) {
  // Allow user to still click in the text box
  $("#utubDescriptionUpdate")
    .offAndOn("focus.updateUTubDescription", function () {
      $("#utubDescriptionUpdate").on(
        "keyup.updateUTubDescription",
        function (e) {
          if (e.originalEvent.repeat) return;
          switch (e.key) {
            case KEYS.ENTER:
              // Handle enter key pressed
              updateUTubDescription(utubID);
              break;
            case KEYS.ESCAPE:
              // Handle escape key pressed
              updateUTubDescriptionHideInput(utubID);
              break;
            default:
            /* no-op */
          }
        },
      );
    })
    .on("blur.updateUTubDescription", function () {
      $("#utubDescriptionUpdate").off("keyup.updateUTubDescription");
    });

  // Bind clicking outside the window
  $(window).offAndOn("click.updateUTubDescription", function (e) {
    // Ignore clicks on the creation object
    if ($(e.target).closest("#updateUTubDescriptionBtn").length) return;

    if (
      $(e.target).is($("#utubDescriptionUpdate")) ||
      $(e.target).is($("#URLDeckSubheaderCreateDescription")) ||
      $(e.target).closest($("#utubDescriptionSubmitBtnUpdate").length) ||
      $(e.target).closest($("#utubDescriptionCancelBtnUpdate").length)
    )
      return;

    // Hide UTub description update fields
    updateUTubDescriptionHideInput(utubID);
  });
}

function removeEventListenersToEscapeUpdateUTubDescription() {
  $(window).off(".updateUTubDescription");
  $(document).off(".updateUTubDescription");
}

function allowUserToCreateDescriptionIfEmptyOnTitleUpdate(utubID) {
  const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
  clickToCreateDesc.showClassNormal();
  clickToCreateDesc.offAndOnExact("click.createUTubdescription", function (e) {
    clickToCreateDesc
      .removeClass("opa-1 height-2rem")
      .addClass("opa-0 height-0");
    updateUTubNameHideInput();
    updateUTubDescriptionShowInput(utubID);
    clickToCreateDesc.off("click.createUTubdescription");
  });
}

function allowHoverOnUTubTitleToCreateDescriptionIfDescEmpty(utubID) {
  const utubTitle = $("#URLDeckHeader");
  const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
  clickToCreateDesc.enableTab();

  utubTitle.offAndOn("mouseenter.createUTubdescription", function (e) {
    clickToCreateDesc
      .removeClass("opa-0 height-0")
      .addClass("opa-1 height-2rem");
    clickToCreateDesc.offAndOnExact(
      "click.createUTubdescription",
      function (e) {
        clickToCreateDesc
          .removeClass("opa-1 height-2rem")
          .addClass("opa-0 height-0 width-0");

        updateUTubDescriptionShowInput(utubID);
        clickToCreateDesc.off("click.createUTubdescription");
      },
    );

    hideCreateUTubDescriptionButtonOnMouseExit();
  });
}

function hideCreateUTubDescriptionButtonOnMouseExit() {
  const urlHeaderWrap = $("#URLDeckHeaderWrap");
  const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
  urlHeaderWrap.offAndOn("mouseleave.createUTubdescription", function (e) {
    if (!isHidden($(clickToCreateDesc))) {
      clickToCreateDesc
        .removeClass("opa-1 height-2rem")
        .addClass("opa-0 height-0");
      clickToCreateDesc.off("click.createUTubdescription");
      urlHeaderWrap.off("mouseleave.createUTubdescription");
    }
  });
}

function removeEventListenersForShowCreateUTubDescIfEmptyDesc() {
  const utubTitle = $("#URLDeckHeader");
  utubTitle.off("mouseenter.createUTubdescription");
  const urlHeaderWrap = $("#URLDeckHeaderWrap");
  urlHeaderWrap.off("mouseleave.createUTubdescription");
}

// Shows input fields for updating an exiting UTub's description
function updateUTubDescriptionShowInput(utubID) {
  // Setup event listeners for window click and escape/enter keys
  setEventListenersToEscapeUpdateUTubDescription(utubID);

  // Show update fields
  const utubDescriptionUpdate = $("#utubDescriptionUpdate");
  utubDescriptionUpdate.val($("#URLDeckSubheader").text());
  showInput("#utubDescriptionUpdate");
  utubDescriptionUpdate.trigger("focus");
  $("#utubDescriptionSubmitBtnUpdate").showClassNormal();

  // Handle hiding the button on mobile when hover events stay after touch
  $("#updateUTubDescriptionBtn").removeClass("visibleBtn");

  // Hide current description and update button
  $("#UTubDescription").hideClass();
  $("#updateUTubDescriptionBtn").hideClass();
  $("#URLDeckSubheader").hideClass();
  $("#URLDeckSubheaderCreateDescription").addClass("width-0");

  removeEventListenersForShowCreateUTubDescIfEmptyDesc();
}

// Hides input fields for updating an exiting UTub's description
function updateUTubDescriptionHideInput(utubID = null) {
  // Hide update fields
  hideInput("#utubDescriptionUpdate");
  $("#utubDescriptionSubmitBtnUpdate").hideClass();

  // Handle giving mobile devices ability to see button again
  $("#updateUTubDescriptionBtn").addClass("visibleBtn");

  // Remove event listeners for window click and escape/enter keys
  removeEventListenersToEscapeUpdateUTubDescription();

  // Show values and update button
  $("#URLDeckSubheader").showClassNormal();
  $("#updateUTubDescriptionBtn").showClassNormal();

  // Reset errors on hiding of inputs
  resetUpdateUTubDescriptionFailErrors();
  $("#URLDeckSubheaderCreateDescription").removeClass("width-0");
  if (!$("#URLDeckSubheader").text().length && utubID != null) {
    allowHoverOnUTubTitleToCreateDescriptionIfDescEmpty(utubID);
  }
}

// Handles post request and response for updating an existing UTub's description
function updateUTubDescription(utubID) {
  // Skip if identical
  if ($("#URLDeckSubheader").text() === $("#utubDescriptionUpdate").val()) {
    updateUTubDescriptionHideInput(utubID);
    return;
  }

  // Extract data to submit in POST request
  let postURL, data;
  [postURL, data] = updateUTubDescriptionSetup(utubID);

  const request = ajaxCall("patch", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      updateUTubDescriptionSuccess(response, utubID);
    }
  });

  request.fail(function (xhr, _, textStatus) {
    updateUTubDescriptionFail(xhr);
  });
}

// Handles preparation for post request to update an existing UTub
function updateUTubDescriptionSetup(utubID) {
  const postURL = APP_CONFIG.routes.updateUTubDescription(utubID);

  const updatedUTubDescription = $("#utubDescriptionUpdate").val();
  let data = { utubDescription: updatedUTubDescription };

  return [postURL, data];
}

// Handle updateion of UTub's description
function updateUTubDescriptionSuccess(response, utubID) {
  const utubDescription = response.utubDescription;
  const utubDescriptionElem = $("#URLDeckSubheader");
  const originalUTubDescriptionLength = utubDescriptionElem.text().length;

  // Change displayed and updateable value for utub description
  $("#URLDeckSubheader").text(utubDescription);
  $("#utubDescriptionUpdate").val(utubDescription);

  if (utubDescription.length === 0) {
    allowHoverOnUTubTitleToCreateDescriptionIfDescEmpty(utubID);
    $("#UTubDescriptionSubheaderOuterWrap").removeClass("height-2rem");
    $("#UTubDescriptionSubheaderWrap").hideClass();
    $("#URLDeckSubheaderCreateDescription").enableTab();
  } else if (originalUTubDescriptionLength === 0) {
    removeEventListenersForShowCreateUTubDescIfEmptyDesc();
    $("#UTubDescriptionSubheaderOuterWrap").removeClass("height-2rem");
    $("#UTubDescriptionSubheaderWrap").showClassFlex();
    $("#URLDeckSubheaderCreateDescription").disableTab();
  }

  // Hide all inputs on success
  updateUTubDescriptionHideInput();
}

// Handle error response display to user
function updateUTubDescriptionFail(xhr) {
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
      if (responseJSON.hasOwnProperty("message")) {
        if (responseJSON.hasOwnProperty("errors"))
          updateUTubDescriptionFailErrors(responseJSON.errors);
        break;
      }
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

// Cycle through the valid errors for updating a UTub name
function updateUTubDescriptionFailErrors(errors) {
  for (let key in errors) {
    switch (key) {
      case "utubDescription":
        let errorMessage = errors[key][0];
        displayUpdateUTubDescriptionFailErrors(key, errorMessage);
    }
  }
}

// Show the error message and highlight the input box border red on error of field
function displayUpdateUTubDescriptionFailErrors(key, errorMessage) {
  $("#" + key + "Update-error")
    .addClass("visible")
    .text(errorMessage);
  $("#" + key + "Update").addClass("invalid-field");
}

function resetUpdateUTubDescriptionFailErrors() {
  const updateUTubNameFields = ["utubDescription"];
  updateUTubNameFields.forEach((fieldName) => {
    $("#" + fieldName + "Update-error").removeClass("visible");
    $("#" + fieldName + "Update").removeClass("invalid-field");
  });
}
