"use strict";

$(document).ready(function () {
  // Update UTub name
  $("#utubNameBtnUpdate").on("click", function (e) {
    deselectAllURLs();
    updateUTubDescriptionHideInput();
    updateUTubNameShowInput();
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
      checkSameNameUTub(false, $("#utubNameUpdate").val());
    })
    .on("focus.updateUTubname", function () {
      $(document).on("keyup.updateUTubname", function (e) {
        if (e.which === 13) {
          if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
            updateUTubNameHideInput();
            return;
          }
          checkSameNameUTub(false, $("#utubNameUpdate").val());
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
        if (e.which === 13) updateUTubNameHideInput();
      });
    })
    .on("blur.updateUTubname", function () {
      $(document).off("keyup.updateUTubname");
    });
});

// Create event listeners to escape from updating UTub name
function setEventListenersToEscapeUpdateUTubName() {
  // Allow user to still click in the text box
  $("#utubNameUpdate")
    .offAndOn("click.updateUTubname", function (e) {
      e.stopPropagation();
    })
    .offAndOn("focus.updateUTubname", function () {
      $(document).on("keyup.updateUTubname", function (e) {
        switch (e.which) {
          case 13:
            // Handle enter key pressed
            // Skip if update is identical
            if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
              updateUTubNameHideInput();
              return;
            }
            checkSameNameUTub(false, $("#utubNameUpdate").val());
            break;
          case 27:
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

function sameUTubNameOnUpdateUTubNameWarningShowModal() {
  const modalTitle = "Continue with this UTub name?";
  const modalBody = "You are a member of a UTub with an identical name.";
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
      setEventListenersToEscapeUpdateUTubName();
    });

  hideIfShown($("#modalRedirect"));
  $("#modalRedirect").hide();

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .offAndOn("click", function (e) {
      e.preventDefault();
      updateUTubName();
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").on("hidden.bs.modal", function (e) {
    e.stopPropagation();
    setEventListenersToEscapeUpdateUTubName();
  });
}

// Shows input fields for updating an exiting UTub's name
function updateUTubNameShowInput() {
  // Setup event listeners on window and escape/enter keys to escape the input box
  setEventListenersToEscapeUpdateUTubName();

  // Show update fields
  const utubNameUpdate = $("#utubNameUpdate");
  utubNameUpdate.val(getCurrentUTubName());
  showInput("#utubNameUpdate");
  utubNameUpdate.trigger("focus");

  // Hide current name and update button
  hideIfShown($("#URLDeckHeader"));
  hideIfShown($("#utubNameBtnUpdate"));
  hideIfShown($("#urlBtnCreate"));

  // Handle hiding the button on mobile when hover events stay after touch
  $("#utubNameBtnUpdate").removeClass("visibleBtn");

  if ($("#URLDeckSubheader").text().length === 0) {
    allowUserToCreateDescriptionIfEmptyOnTitleUpdate();
  }
}

// Hides input fields for updating an existing UTub's name
function updateUTubNameHideInput() {
  // Hide update fields
  hideInput("#utubNameUpdate");

  // Show values and update button
  showIfHidden($("#URLDeckHeader"));
  showIfHidden($("#utubNameBtnUpdate"));
  showIfHidden($("#urlBtnCreate"));

  // Remove event listeners on window and escape/enter keys
  removeEventListenersToEscapeUpdateUTubName();

  // Handle giving mobile devices ability to see button again
  $("#utubNameBtnUpdate").addClass("visibleBtn");

  if ($("#URLDeckSubheader").text().length === 0) {
    hideIfShown($("#URLDeckSubheaderCreateDescription"));
  }

  // Remove any errors if shown
  resetUpdateUTubNameFailErrors();

  // Replace default value
  $("#utubNameUpdate").val($("#URLDeckHeader").text());
}

// Handles post request and response for updating an existing UTub's name
function updateUTubName() {
  // Skip if update is identical
  if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
    updateUTubNameHideInput();
    return;
  }

  // Extract data to submit in POST request
  let postURL, data;
  [postURL, data] = updateUTubNameSetup();

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
function updateUTubNameSetup() {
  const postURL = routes.updateUTubName(getActiveUTubID());

  const updatedUTubName = $("#utubNameUpdate").val();
  let data = { utubName: updatedUTubName };

  return [postURL, data];
}

// Handle updateion of UTub's name
function updateUTubNameSuccess(response) {
  const UTubName = response.utubName;

  $("#confirmModal").modal("hide");

  // UTubDeck display updates
  const updatedUTubSelector = $("#listUTubs").find(".active");
  updatedUTubSelector.find(".UTubName").text(UTubName);

  // Display updates
  setUTubDeckOnUTubSelected(getActiveUTubID(), getCurrentUTubOwnerUserID());
  setUTubNameAndDescription(UTubName);
}

// Handle error response display to user
function updateUTubNameFail(xhr) {
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
          updateUTubNameFailErrors(responseJSON.errors);
        break;
      }
    case 404:
    default:
      window.location.assign(routes.errorPage);
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
