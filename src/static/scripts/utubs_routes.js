/** UTub UI Interactions **/

$(document).ready(function () {
  /* Bind click functions */
  setCreateDeleteUTubEventListeners();

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

/* Add UTub */

// Shows new UTub input fields
function createUTubShowInput() {
  showIfHidden($("#createUTubWrap"));
  createNewUTubEventListeners();
  $("#utubNameCreate").trigger("focus");
  hideIfShown($("#listUTubs"));
  $("#UTubDeck").find(".icon-holder").hide();
  removeCreateDeleteUTubEventListeners();
}

// Hides new UTub input fields
function createUTubHideInput() {
  hideIfShown($("#createUTubWrap"));
  showIfHidden($("#listUTubs"));
  $("#utubNameCreate").val(null);
  $("#utubDescriptionCreate").val(null);
  removeNewUTubEventListeners();
  resetUTubFailErrors();
  $("#UTubDeck").find(".icon-holder").show();
  setCreateDeleteUTubEventListeners();
}

// Handles post request and response for adding a new UTub
function createUTub() {
  // Extract data to submit in POST request
  [postURL, data] = createUTubSetup();
  resetUTubFailErrors();

  let request = ajaxCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      createUTubSuccess(response);
      showIfHidden($("#listUTubs"));
    }
  });

  request.fail(function (xhr, _, textStatus) {
    createUTubFail(xhr);
  });
}

// Handles preparation for post request to create a new UTub
function createUTubSetup() {
  const postURL = routes.createUTub;
  const newUTubName = $("#utubNameCreate").val();
  const newUTubDescription = $("#utubDescriptionCreate").val();
  data = { utubName: newUTubName, utubDescription: newUTubDescription };

  return [postURL, data];
}

// Handle creation of new UTub
function createUTubSuccess(response) {
  // DP 12/28/23 One problem is that confirmed DB changes aren't yet reflected on the page. Ex. 1. User makes UTub name change UTub1 -> UTub2. 2. User attempts to create new UTub UTub1. 3. Warning modal is thrown because no AJAX call made to update the passed UTubs json.
  const UTubID = response.utubID;

  $("#confirmModal").modal("hide");

  // Remove createDiv; Reattach after addition of new UTub
  createUTubHideInput();

  // Create and append newly created UTub selector
  const index = parseInt($(".UTubSelector").first().attr("position"));
  const newUTubSelector = createUTubSelector(
    response.utubName,
    UTubID,
    index - 1,
  );
  $("#listUTubs").prepend(newUTubSelector);

  selectUTub(UTubID, newUTubSelector);
}

// Handle error response display to user
function createUTubFail(xhr) {
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
      window.location.assign(routes.errorPage);
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

/* Update UTub */

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

// Hides input fields for updating an exiting UTub's name
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
  data = { utubName: updatedUTubName };

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

/* Update UTub Description */

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
  data = { utubDescription: updatedUTubDescription };

  return [postURL, data];
}

// Handle updateion of UTub's description
function updateUTubDescriptionSuccess(response) {
  const utubDescription = response.utubDescription;

  // Change displayed and updateable value for utub description
  $("#URLDeckSubheader").text(utubDescription);
  $("#utubDescriptionUpdate").val(utubDescription);

  // Hide all inputs on success
  updateUTubDescriptionHideInput();
}

// Handle error response display to user
function updateUTubDescriptionFail(xhr) {
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

/* Delete UTub */

// Hide confirmation modal for deletion of the current UTub
function deleteUTubHideModal() {
  $("#confirmModal").modal("hide");
}

// Show confirmation modal for deletion of the current UTub
function deleteUTubShowModal() {
  let modalTitle = "Are you sure you want to delete this UTub?";
  let modalBody = "This action is irreverisible!";
  let buttonTextDismiss = "Nevermind...";
  let buttonTextSubmit = "Delete this sucka!";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-secondary")
    .offAndOn("click", function (e) {
      e.preventDefault();
      deleteUTubHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-danger")
    .text(buttonTextSubmit)
    .offAndOn("click", function (e) {
      e.preventDefault();
      deleteUTub();
    });

  $("#confirmModal").modal("show");
  $("#modalRedirect").hide();
}

// Handles deletion of a current UTub
function deleteUTub() {
  // Extract data to submit in POST request
  postURL = deleteUTubSetup();

  const request = ajaxCall("delete", postURL, []);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      deleteUTubSuccess();
    }
  });

  request.fail(function (xhr, textStatus, errorThrown) {
    window.location.assign(routes.errorPage);
  });
}

// Prepares post request inputs to delete the current UTub
function deleteUTubSetup() {
  let postURL = routes.deleteUTub(getActiveUTubID());

  return postURL;
}

function deleteUTubSuccess() {
  hideInputs();

  // Close modal
  $("#confirmModal").modal("hide");
  $("#utubBtnDelete").hide();

  // Update UTub Deck
  const currentUTubID = getActiveUTubID();
  const UTubSelector = $(".UTubSelector[utubid=" + currentUTubID + "]");
  UTubSelector.fadeOut();
  UTubSelector.remove();

  // Reset all panels
  setUIWhenNoUTubSelected();

  hideInputsAndSetUTubDeckSubheader();

  if (getNumOfUTubs() === 0) {
    resetUTubDeckIfNoUTubs();
  }
}
