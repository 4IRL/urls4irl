"use strict";

$(document).ready(function () {
  const utubDescriptionSubmitBtnUpdate = $("#utubDescriptionSubmitBtnUpdate");
  const utubDescriptionCancelBtnUpdate = $("#utubDescriptionCancelBtnUpdate");

  // Update UTub description
  $("#updateUTubDescriptionBtn")
    .on("click", function (e) {
      deselectAllURLs();
      updateUTubNameHideInput();
      updateUTubDescriptionShowInput();
      // Prevent this event from bubbling up to the window to allow event listener creation
      e.stopPropagation();
    })
    .on("focus.updateUTubdescription", function () {
      $(document).on("keyup.updateUTubdescription", function (e) {
        if (e.which === 13) {
          deselectAllURLs();
          updateUTubNameHideInput();
          updateUTubDescriptionShowInput();
        }
      });
    })
    .on("blur.updateUTubdescription", function () {
      $(document).off("keyup.updateUTubdescription");
    });

  utubDescriptionSubmitBtnUpdate
    .find(".submitButton")
    .on("click", function (e) {
      e.stopPropagation();
      updateUTubDescription();
    })
    .on("focus.updateUTubdescription", function () {
      $(document).offAndOn("keyup.updateUTubdescription", function (e) {
        if (e.which === 13) updateUTubDescription();
      });
    })
    .on("blur.updateUTubdescription", function () {
      $(document).off("keyup.updateUTubdescription");
    });

  utubDescriptionCancelBtnUpdate
    .find(".cancelButton")
    .on("click", function (e) {
      e.stopPropagation();
      updateUTubDescriptionHideInput();
    })
    .on("focus.updateUTubdescription", function () {
      $(document).offAndOn("keyup.updateUTubdescription", function (e) {
        if (e.which === 13) updateUTubDescriptionHideInput();
      });
    })
    .on("blur.updateUTubdescription", function () {
      $(document).off("keyup.updateUTubdescription");
    });
});

// Create event listeners to escape from updating UTub name
function setEventListenersToEscapeUpdateUTubDescription() {
  // Allow user to still click in the text box
  $("#utubDescriptionUpdate")
    .on("click.updateUTubDescription", function (e) {
      e.stopPropagation();
    })
    .offAndOn("focus.updateUTubDescription", function () {
      $(document).on("keyup.updateUTubDescription", function (e) {
        switch (e.which) {
          case 13:
            // Handle enter key pressed
            updateUTubDescription();
            break;
          case 27:
            // Handle escape key pressed
            updateUTubDescriptionHideInput();
            break;
          default:
          /* no-op */
        }
      });
    })
    .on("blur.updateUTubDescription", function () {
      $(document).off("keyup.updateUTubDescription");
    });

  // Bind clicking outside the window
  $(window).offAndOn("click.updateUTubDescription", function (e) {
    // Hide UTub description update fields
    updateUTubDescriptionHideInput();
  });
}

function removeEventListenersToEscapeUpdateUTubDescription() {
  $(window).off(".updateUTubDescription");
  $(document).off(".updateUTubDescription");
}

function allowUserToCreateDescriptionIfEmptyOnTitleUpdate() {
  const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
  showIfHidden(clickToCreateDesc);
  clickToCreateDesc.offAndOn("click.createUTubdescription", function (e) {
    e.stopPropagation();
    hideIfShown(clickToCreateDesc);
    updateUTubNameHideInput();
    updateUTubDescriptionShowInput();
    clickToCreateDesc.off("click.createUTubdescription");
  });
}

function allowHoverOnUTubTitleToCreateDescriptionIfDescEmpty() {
  const utubTitle = $("#URLDeckHeader");
  utubTitle.offAndOn("mouseenter.createUTubdescription", function () {
    const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
    showIfHidden(clickToCreateDesc);
    clickToCreateDesc.offAndOn("click.createUTubdescription", function (e) {
      e.stopPropagation();
      hideIfShown(clickToCreateDesc);
      updateUTubDescriptionShowInput();
      clickToCreateDesc.off("click.createUTubdescription");
    });
    hideCreateUTubDescriptionButtonOnMouseExit();
  });
}

function hideCreateUTubDescriptionButtonOnMouseExit() {
  const urlHeaderWrap = $("#URLDeckHeaderWrap");
  const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
  urlHeaderWrap.offAndOn("mouseleave.createUTubdescription", function () {
    if (!isHidden($(clickToCreateDesc))) {
      hideIfShown(clickToCreateDesc);
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
function updateUTubDescriptionShowInput() {
  // Setup event listeners for window click and escape/enter keys
  setEventListenersToEscapeUpdateUTubDescription();

  // Show update fields
  const utubDescriptionUpdate = $("#utubDescriptionUpdate");
  utubDescriptionUpdate.val($("#URLDeckSubheader").text());
  showInput("#utubDescriptionUpdate");
  utubDescriptionUpdate.trigger("focus");
  showIfHidden($("#utubDescriptionSubmitBtnUpdate"));

  // Handle hiding the button on mobile when hover events stay after touch
  $("#updateUTubDescriptionBtn").removeClass("visibleBtn");

  // Hide current description and update button
  hideIfShown($("#UTubDescription"));
  hideIfShown($("#updateUTubDescriptionBtn"));
  hideIfShown($("#URLDeckSubheader"));
}

// Hides input fields for updating an exiting UTub's description
function updateUTubDescriptionHideInput() {
  // Hide update fields
  hideInput("#utubDescriptionUpdate");
  hideIfShown($("#utubDescriptionSubmitBtnUpdate"));

  // Handle giving mobile devices ability to see button again
  $("#updateUTubDescriptionBtn").addClass("visibleBtn");

  // Remove event listeners for window click and escape/enter keys
  removeEventListenersToEscapeUpdateUTubDescription();

  // Show values and update button
  showIfHidden($("#URLDeckSubheader"));
  showIfHidden($("#updateUTubDescriptionBtn"));

  // Reset errors on hiding of inputs
  resetUpdateUTubDescriptionFailErrors();
}

// Handles post request and response for updating an existing UTub's description
function updateUTubDescription() {
  // Skip if identical
  if ($("#URLDeckSubheader").text() === $("#utubDescriptionUpdate").val()) {
    updateUTubDescriptionHideInput();
    return;
  }

  // Extract data to submit in POST request
  let postURL, data;
  [postURL, data] = updateUTubDescriptionSetup();

  const request = ajaxCall("patch", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      updateUTubDescriptionSuccess(response);
    }
  });

  request.fail(function (xhr, _, textStatus) {
    updateUTubDescriptionFail(xhr);
  });
}

// Handles preparation for post request to update an existing UTub
function updateUTubDescriptionSetup() {
  const postURL = routes.updateUTubDescription(getActiveUTubID());

  const updatedUTubDescription = $("#utubDescriptionUpdate").val();
  let data = { utubDescription: updatedUTubDescription };

  return [postURL, data];
}

// Handle updateion of UTub's description
function updateUTubDescriptionSuccess(response) {
  const utubDescription = response.utubDescription;
  const utubDescriptionElem = $("#URLDeckSubheader");
  const originalUTubDescriptionLength = utubDescriptionElem.text().length;
  if (utubDescription.length === 0) {
    allowHoverOnUTubTitleToCreateDescriptionIfDescEmpty();
  } else if (originalUTubDescriptionLength === 0) {
    removeEventListenersForShowCreateUTubDescIfEmptyDesc();
  }

  // Change displayed and updateable value for utub description
  $("#URLDeckSubheader").text(utubDescription);
  $("#utubDescriptionUpdate").val(utubDescription);

  // Hide all inputs on success
  updateUTubDescriptionHideInput();
}

// Handle error response display to user
function updateUTubDescriptionFail(xhr) {
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
      if (responseJSON.hasOwnProperty("message")) {
        if (responseJSON.hasOwnProperty("errors"))
          updateUTubDescriptionFailErrors(responseJSON.errors);
        break;
      }
    case 404:
    default:
      window.location.assign(routes.errorPage);
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
