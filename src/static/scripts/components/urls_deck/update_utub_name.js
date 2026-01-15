"use strict";

function checkSameNameUTubOnUpdate(name, utubID) {
  if (getAllAccessibleUTubNames().includes(name)) {
    // UTub with same name exists. Confirm action with user
    sameUTubNameOnUpdateUTubNameWarningShowModal(utubID);
  } else {
    // UTub name is unique. Proceed with requested action
    updateUTubName(utubID);
  }
}

function setupUpdateUTubNameEventListeners(utubID) {
  // Update UTub name
  $("#utubNameBtnUpdate").on("click", function (e) {
    deselectAllURLs();
    updateUTubDescriptionHideInput();
    updateUTubNameShowInput(utubID);
    // Prevent this event from bubbling up to the window to allow event listener creation
    e.stopPropagation();
  });

  const utubNameSubmitBtnUpdate = $("#utubNameSubmitBtnUpdate");
  const utubNameCancelBtnUpdate = $("#utubNameCancelBtnUpdate");

  utubNameSubmitBtnUpdate
    .find(".submitButton")
    .on("click", function (e) {
      // Prevent event from bubbling up to window which would exit the input box
      e.stopPropagation();
      // Skip if update is identical to original
      if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
        updateUTubNameHideInput();
        return;
      }
      checkSameNameUTubOnUpdate($("#utubNameUpdate").val(), utubID);
    })
    .on("focus.updateUTubname", function () {
      $(document).on("keyup.updateUTubname", function (e) {
        if (e.key === KEYS.ENTER) {
          if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
            updateUTubNameHideInput();
            return;
          }
          checkSameNameUTubOnUpdate($("#utubNameUpdate").val(), utubID);
        }
      });
    })
    .on("blur.updateUTubname", function () {
      $(document).off("keyup.updateUTubname");
    });

  utubNameCancelBtnUpdate
    .find(".cancelButton")
    .on("click.updateUTubname", function (e) {
      e.stopPropagation();
      updateUTubNameHideInput();
    })
    .on("focus.updateUTubname", function () {
      $(document).on("keyup.updateUTubname", function (e) {
        if (e.key === KEYS.ENTER) updateUTubNameHideInput();
      });
    })
    .on("blur.updateUTubname", function () {
      $(document).off("keyup.updateUTubname");
    });
}

// Create event listeners to escape from updating UTub name
function setEventListenersToEscapeUpdateUTubName(utubID) {
  // Allow user to still click in the text box
  $("#utubNameUpdate")
    .offAndOn("click.updateUTubname", function (e) {
      e.stopPropagation();
    })
    .offAndOn("focus.updateUTubname", function () {
      $(document).on("keyup.updateUTubname", function (e) {
        switch (e.key) {
          case KEYS.ENTER:
            // Handle enter key pressed
            // Skip if update is identical
            if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
              updateUTubNameHideInput();
              return;
            }
            checkSameNameUTubOnUpdate($("#utubNameUpdate").val(), utubID);
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
      $(document).off("keyup.updateUTubname");
    });

  // Bind clicking outside the window
  $(window).offAndOn("click.updateUTubname", function () {
    // Hide UTub name update fields
    updateUTubNameHideInput();
  });
}

function removeEventListenersToEscapeUpdateUTubName() {
  $(window).off(".updateUTubname");
  $(document).off(".updateUTubname");
}

function sameUTubNameOnUpdateUTubNameWarningShowModal(utubID) {
  const modalTitle = "Continue with this UTub name?";
  const modalBody = `${APP_CONFIG.strings.UTUB_UPDATE_SAME_NAME}`;
  const buttonTextDismiss = "Go Back to Editing";
  const buttonTextSubmit = "Edit Name";

  removeEventListenersToEscapeUpdateUTubName();

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-secondary")
    .text(buttonTextDismiss)
    .offAndOn("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      sameNameWarningHideModal();
      highlightInput($("#utubNameUpdate"));
      setEventListenersToEscapeUpdateUTubName(utubID);
    });

  $("#modalRedirect").hideClass();
  $("#modalRedirect").hide();

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .offAndOn("click", function (e) {
      e.preventDefault();
      updateUTubName(utubID);
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").on("hidden.bs.modal", function (e) {
    e.stopPropagation();
    setEventListenersToEscapeUpdateUTubName(utubID);
  });
}

// Shows input fields for updating an exiting UTub's name
function updateUTubNameShowInput(utubID) {
  // Setup event listeners on window and escape/enter keys to escape the input box
  setEventListenersToEscapeUpdateUTubName(utubID);

  // Show update fields
  const utubNameUpdate = $("#utubNameUpdate");
  const parentTitleElem = utubNameUpdate.closest(".titleElement");
  parentTitleElem.addClass("m-top-bot-0-5rem");
  utubNameUpdate.val(getCurrentUTubName());
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
function updateUTubNameHideInput() {
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
    $("#URLDeckSubheaderCreateDescription").hideClass();
  }

  // Remove any errors if shown
  resetUpdateUTubNameFailErrors();

  // Replace default value
  $("#utubNameUpdate").val($("#URLDeckHeader").text());
}

// Handles post request and response for updating an existing UTub's name
function updateUTubName(utubID) {
  // Skip if update is identical
  if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
    updateUTubNameHideInput();
    return;
  }

  // Extract data to submit in POST request
  let postURL, data;
  [postURL, data] = updateUTubNameSetup(utubID);

  let request = ajaxCall("patch", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      updateUTubNameSuccess(response);
    }
  });

  request.fail(function (xhr, _, textStatus) {
    updateUTubNameFail(xhr);
  });
}

// Handles preparation for post request to update an existing UTub
function updateUTubNameSetup(utubID) {
  const postURL = APP_CONFIG.routes.updateUTubName(utubID);

  const updatedUTubName = $("#utubNameUpdate").val();
  let data = { utubName: updatedUTubName };

  return [postURL, data];
}

// Handle update of UTub's name
function updateUTubNameSuccess(response) {
  const utubName = response.utubName;

  $("#confirmModal").modal("hide");

  // UTubDeck display updates
  const updatedUTubSelector = $("#listUTubs").find(".active");
  updatedUTubSelector.find(".UTubName").text(utubName);

  // Display updates
  setUTubNameAndDescription(utubName);
}

// Handle error response display to user
function updateUTubNameFail(xhr) {
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
          updateUTubNameFailErrors(responseJSON.errors);
        break;
      }
    case 404:
    default:
      window.location.assign(APP_CONFIG.routes.errorPage);
  }
}

// Cycle through the valid errors for updating a UTub name
function updateUTubNameFailErrors(errors) {
  for (let key in errors) {
    switch (key) {
      case "utubName":
        let errorMessage = errors[key][0];
        displayUpdateUTubNameFailErrors(key, errorMessage);
        return;
    }
  }
}

// Show the error message and highlight the input box border red on error of field
function displayUpdateUTubNameFailErrors(key, errorMessage) {
  $("#" + key + "Update-error")
    .addClass("visible")
    .text(errorMessage);
  $("#" + key + "Update").addClass("invalid-field");
}

function resetUpdateUTubNameFailErrors() {
  const updateUTubNameFields = ["utubName"];
  updateUTubNameFields.forEach((fieldName) => {
    $("#" + fieldName + "Update-error").removeClass("visible");
    $("#" + fieldName + "Update").removeClass("invalid-field");
  });
}
