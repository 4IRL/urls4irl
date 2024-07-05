/** UTub UI Interactions **/

$(document).ready(function () {
  /* Bind click functions */
  setCreateDeleteUTubEventListeners();

  // Update UTub name
  $("#utubNameBtnUpdate").on("click", function (e) {
    hideInputs();
    deselectAllURLs();
    updateUTubDescriptionHideInput();
    updateUTubNameShowInput();
    // Prevent this event from bubbling up to the window to allow event listener creation
    e.stopPropagation();
  });

  $("#utubNameSubmitBtnUpdate").on("click", function (e) {
    // Prevent event from bubbling up to window which would exit the input box
    e.stopPropagation();
    // Skip if update is identical to original
    if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
      updateUTubNameHideInput();
      return;
    }
    checkSameNameUTub(false, $("#utubNameUpdate").val());
  });

  // Update UTub description
  $("#updateUTubDescriptionBtn").on("click", function (e) {
    hideInputs();
    deselectAllURLs();
    updateUTubNameHideInput();
    updateUTubDescriptionShowInput();
    // Prevent this event from bubbling up to the window to allow event listener creation
    e.stopPropagation();
  });

  $("#utubDescriptionSubmitBtnUpdate").on("click", function (e) {
    e.stopPropagation();
    updateUTubDescription();
  });
});

/* Add UTub */

// Shows new UTub input fields
function createUTubShowInput() {
  showInput("#createUTubWrap");
  highlightInput($("#utubNameCreate"));
  createNewUTubEventListeners();
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

  let request = AJAXCall("post", postURL, data);

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
  let UTubID = response.utubID;

  $("#confirmModal").modal("hide");

  // Remove createDiv; Reattach after addition of new UTub
  createUTubHideInput();

  // Create and append newly created UTub selector
  let index = parseInt($(".UTubSelector").first().attr("position"));
  $("#listUTubs").prepend(
    createUTubSelector(response.utubName, UTubID, index - 1),
  );

  selectUTub(UTubID);
}

// Handle error response display to user
function createUTubFail(xhr) {
  switch (xhr.status) {
    case 400:
      const responseJSON = xhr.responseJSON;
      if (responseJSON.hasOwnProperty("message")) {
        if (responseJSON.hasOwnProperty("errors"))
          createUTubFailShowErrors(responseJSON.errors);
        break;
      }
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}

// Cycle through the valid errors for adding a UTub
function createUTubFailShowErrors(errors) {
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
  // Show update fields
  $("#utubNameUpdate").text(getCurrentUTubName());
  showInput("#utubNameUpdate");

  // Hide current name and update button
  hideIfShown($("#URLDeckHeader"));
  hideIfShown($("#utubNameBtnUpdate"));
  hideIfShown($("#urlBtnCreate"));

  // Handle hiding the button on mobile when hover events stay after touch
  $("#utubNameBtnUpdate").removeClass("visibleBtn");

  // Setup event listeners on window and escape/enter keys to escape the input box
  setEventListenersToEscapeUpdateUTubName();

  // Prevent URL keyboard selection while updating name
  unbindURLKeyboardEventListenersWhenUpdatesOccurring();

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

  // Allow URL selection with keyboard again
  bindURLKeyboardEventListenersWhenUpdatesNotOccurring();

  if ($("#URLDeckSubheader").text().length === 0) {
    hideIfShown($("#URLDeckSubheaderCreateDescription"));
  }

  // Remove any errors if shown
  resetUpdateUTubNameFailErrors();
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

  let request = AJAXCall("patch", postURL, data);

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
  displayState1UTubDeck(getActiveUTubID(), getCurrentUTubOwnerUserID());
  displayState1URLDeck(UTubName);
}

// Handle error response display to user
function updateUTubNameFail(xhr) {
  switch (xhr.status) {
    case 400:
      const responseJSON = xhr.responseJSON;
      if (responseJSON.hasOwnProperty("message")) {
        if (responseJSON.hasOwnProperty("errors"))
          updateUTubNameFailShowErrors(responseJSON.errors);
        break;
      }
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}

// Cycle through the valid errors for updating a UTub name
function updateUTubNameFailShowErrors(errors) {
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
  // Show update fields
  $("#utubDescriptionUpdate").val($("#URLDeckSubheader").text());
  showInput("#utubDescriptionUpdate");
  showIfHidden($("#utubDescriptionSubmitBtnUpdate"));

  // Setup event listeners for window click and escape/enter keys
  setEventListenersToEscapeUpdateUTubDescription();

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

  const request = AJAXCall("patch", postURL, data);

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
          updateUTubDescriptionFailShowErrors(responseJSON.errors);
        break;
      }
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}

// Cycle through the valid errors for updating a UTub name
function updateUTubDescriptionFailShowErrors(errors) {
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
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      deleteUTubHideModal();
    })
    .text(buttonTextDismiss);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-danger")
    .text(buttonTextSubmit)
    .off("click")
    .on("click", function (e) {
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

  let request = AJAXCall("delete", postURL, []);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status === 200) {
      deleteUTubSuccess();
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    deleteUTubFail(response, textStatus, xhr);
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

  // Update UTub Deck
  let currentUTubID = getActiveUTubID();
  let UTubSelector = $(".UTubSelector[utubid=" + currentUTubID + "]");
  UTubSelector.fadeOut();
  UTubSelector.remove();

  // Reset all panels
  displayState0();

  displayState1UTubDeck(null, null);

  if ($("#listUTubs").find(".UTubSelector").length === 0)
    displayState0UTubDeck();
}

function deleteUTubFail(response, textStatus, xhr) {
  console.log("Error: Could not delete UTub");

  if (xhr.status === 409) {
    console.log(
      "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
    );
    // const flashMessage = xhr.responseJSON.error;
    // const flashCategory = xhr.responseJSON.category;

    // let flashElem = flashMessageBanner(flashMessage, flashCategory);
    // flashElem.insertBefore('#modal-body').show();
  } else if (xhr.status === 404) {
    $(".invalid-feedback").remove();
    $(".alert").remove();
    $(".form-control").removeClass("is-invalid");
    const error = JSON.parse(xhr.responseJSON);
    for (var key in error) {
      $('<div class="invalid-feedback"><span>' + error[key] + "</span></div>")
        .insertAfter("#" + key)
        .show();
      $("#" + key).addClass("is-invalid");
    }
  }
  console.log(
    "Failure. Error code: " +
      response.error.errorCode +
      ". Status: " +
      response.error.Message,
  );
}
