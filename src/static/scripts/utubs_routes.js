/** UTub UI Interactions **/

$(document).ready(function () {
  /* Bind click functions */
  setAddDeleteUTubEventListeners();

  // Edit UTub name
  $("#editUTubNameBtn").on("click", function (e) {
    hideInputs();
    deselectAllURLs();
    editUTubDescriptionHideInput();
    editUTubNameShowInput();
    // Prevent this event from bubbling up to the window to allow event listener creation
    e.stopPropagation();
  });

  $("#submitEditUTubNameBtn").on("click", function (e) {
    // Prevent event from bubbling up to window which would exit the input box
    e.stopPropagation();
    // Skip if edit is identical to original
    if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
      editUTubNameHideInput();
      return;
    }
    checkSameNameUTub(false, $("#utubNameUpdate").val());
  });

  // Edit UTub description
  $("#editUTubDescriptionBtn").on("click", function (e) {
    hideInputs();
    deselectAllURLs();
    editUTubNameHideInput();
    editUTubDescriptionShowInput();
    // Prevent this event from bubbling up to the window to allow event listener creation
    e.stopPropagation();
  });

  $("#submitEditUTubDescriptionBtn").on("click", function (e) {
    e.stopPropagation();
    editUTubDescription();
  });
});

/* Add UTub */

// Shows new UTub input fields
function addUTubShowInput() {
  showInput("#createUTubWrap");
  highlightInput($("#utubNameCreate"));
  createNewUTubEventListeners();
  hideIfShown($("#listUTubs"));
  $("#UTubDeck").find(".icon-holder").hide();
  removeAddDeleteUTubEventListeners();
}

// Hides new UTub input fields
function addUTubHideInput() {
  hideIfShown($("#createUTubWrap"));
  showIfHidden($("#listUTubs"));
  $("#utubNameCreate").val(null);
  $("#utubDescriptionCreate").val(null);
  removeNewUTubEventListeners();
  resetUTubFailErrors();
  $("#UTubDeck").find(".icon-holder").show();
  setAddDeleteUTubEventListeners();
}

// Handles post request and response for adding a new UTub
function addUTub() {
  // Extract data to submit in POST request
  [postURL, data] = addUTubSetup();

  let request = AJAXCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      addUTubSuccess(response);
      showIfHidden($("#listUTubs"));
    }
  });

  request.fail(function (xhr, _, textStatus) {
    addUTubFail(xhr);
  });
}

// Handles preparation for post request to create a new UTub
function addUTubSetup() {
  const postURL = routes.addUTub;
  const newUTubName = $("#utubNameCreate").val();
  const newUTubDescription = $("#utubDescriptionCreate").val();
  data = { utubName: newUTubName, utubDescription: newUTubDescription };

  return [postURL, data];
}

// Handle creation of new UTub
function addUTubSuccess(response) {
  // DP 12/28/23 One problem is that confirmed DB changes aren't yet reflected on the page. Ex. 1. User makes UTub name change UTub1 -> UTub2. 2. User attempts to create new UTub UTub1. 3. Warning modal is thrown because no AJAX call made to update the passed UTubs json.
  let UTubID = response.utubID;

  $("#confirmModal").modal("hide");

  // Remove createDiv; Reattach after addition of new UTub
  addUTubHideInput();

  // Create and append newly created UTub selector
  let index = parseInt($(".UTubSelector").first().attr("position"));
  $("#listUTubs").prepend(
    createUTubSelector(response.utubName, UTubID, index - 1),
  );

  selectUTub(UTubID);
}

// Handle error response display to user
function addUTubFail(xhr) {
  switch (xhr.status) {
    case 400:
      const responseJSON = xhr.responseJSON;
      if (responseJSON.hasOwnProperty("message")) {
        if (responseJSON.hasOwnProperty("errors"))
          addUTubFailShowErrors(responseJSON.errors);
        break;
      }
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}

// Cycle through the valid errors for adding a UTub
function addUTubFailShowErrors(errors) {
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

/* Edit UTub */

// Shows input fields for editing an exiting UTub's name
function editUTubNameShowInput() {
  // Show edit fields
  $("#utubNameUpdate").text(getCurrentUTubName());
  showInput("#utubNameUpdate");

  // Hide current name and edit button
  hideIfShown($("#URLDeckHeader"));
  hideIfShown($("#editUTubNameBtn"));
  hideIfShown($("#addURLBtn"));

  // Handle hiding the button on mobile when hover events stay after touch
  $("#editUTubNameBtn").removeClass("visibleBtn");

  // Setup event listeners on window and escape/enter keys to escape the input box
  setEventListenersToEscapeEditUTubName();

  // Prevent URL keyboard selection while editing name
  unbindURLKeyboardEventListenersWhenEditsOccurring();

  if ($("#URLDeckSubheader").text().length === 0) {
    allowUserToAddDescriptionIfEmptyOnTitleEdit();
  }
}

// Hides input fields for editing an exiting UTub's name
function editUTubNameHideInput() {
  // Hide edit fields
  hideInput("#utubNameUpdate");

  // Show values and edit button
  showIfHidden($("#URLDeckHeader"));
  showIfHidden($("#editUTubNameBtn"));
  showIfHidden($("#addURLBtn"));

  // Remove event listeners on window and escape/enter keys
  removeEventListenersToEscapeEditUTubName();

  // Handle giving mobile devices ability to see button again
  $("#editUTubNameBtn").addClass("visibleBtn");

  // Allow URL selection with keyboard again
  bindURLKeyboardEventListenersWhenEditsNotOccurring();

  if ($("#URLDeckSubheader").text().length === 0) {
    hideIfShown($("p#URLDeckSubheaderAddDescription"));
  }

  // Remove any errors if shown
  resetEditUTubNameFailErrors();
}

// Handles post request and response for editing an existing UTub's name
function editUTubName() {
  // Skip if edit is identical
  if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
    editUTubNameHideInput();
    return;
  }

  // Extract data to submit in POST request
  [postURL, data] = editUTubNameSetup();

  let request = AJAXCall("patch", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      editUTubNameSuccess(response);
    }
  });

  request.fail(function (xhr, _, textStatus) {
    editUTubNameFail(xhr);
  });
}

// Handles preparation for post request to edit an existing UTub
function editUTubNameSetup() {
  const postURL = routes.editUTubName(getActiveUTubID());

  const editedUTubName = $("#utubNameUpdate").val();
  data = { utubName: editedUTubName };

  return [postURL, data];
}

// Handle edition of UTub's name
function editUTubNameSuccess(response) {
  const UTubName = response.utubName;

  $("#confirmModal").modal("hide");

  // UTubDeck display updates
  const editedUTubSelector = $("#listUTubs").find(".active");
  editedUTubSelector.find(".UTubName").text(UTubName);

  // Display updates
  displayState1UTubDeck(getActiveUTubID(), getCurrentUTubOwnerUserID());
  displayState1URLDeck(UTubName);
}

// Handle error response display to user
function editUTubNameFail(xhr) {
  switch (xhr.status) {
    case 400:
      const responseJSON = xhr.responseJSON;
      if (responseJSON.hasOwnProperty("message")) {
        if (responseJSON.hasOwnProperty("errors"))
          editUTubNameFailShowErrors(responseJSON.errors);
        break;
      }
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}

// Cycle through the valid errors for editing a UTub name
function editUTubNameFailShowErrors(errors) {
  for (let key in errors) {
    switch (key) {
      case "utubName":
        let errorMessage = errors[key][0];
        displayEditUTubNameFailErrors(key, errorMessage);
        return;
    }
  }
}

// Show the error message and highlight the input box border red on error of field
function displayEditUTubNameFailErrors(key, errorMessage) {
  $("#" + key + "Update-error")
    .addClass("visible")
    .text(errorMessage);
  $("#" + key + "Update").addClass("invalid-field");
}

function resetEditUTubNameFailErrors() {
  const editUTubNameFields = ["utubName"];
  editUTubNameFields.forEach((fieldName) => {
    $("#" + fieldName + "Update-error").removeClass("visible");
    $("#" + fieldName + "Update").removeClass("invalid-field");
  });
}

/* Edit UTub Description */

// Shows input fields for editing an exiting UTub's description
function editUTubDescriptionShowInput() {
  // Show edit fields
  $(".#utubDescriptionUpdate").val($("#URLDeckSubheader").text());
  showInput("#utubDescriptionUpdate");
  showIfHidden($("#submitEditUTubDescriptionBtn"));

  // Setup event listeners for window click and escape/enter keys
  setEventListenersToEscapeEditUTubDescription();

  // Handle hiding the button on mobile when hover events stay after touch
  $("#editUTubDescriptionBtn").removeClass("visibleBtn");

  // Hide current description and edit button
  hideIfShown($("#UTubDescription"));
  hideIfShown($("#editUTubDescriptionBtn"));
  hideIfShown($("#URLDeckSubheader"));
}

// Hides input fields for editing an exiting UTub's description
function editUTubDescriptionHideInput() {
  // Hide edit fields
  hideInput("#utubDescriptionUpdate");
  hideIfShown($("#submitEditUTubDescriptionBtn"));
  hideIfShown($("#submitEditUTubDescriptionBtn"));

  // Handle giving mobile devices ability to see button again
  $("#editUTubDescriptionBtn").addClass("visibleBtn");

  // Remove event listeners for window click and escape/enter keys
  removeEventListenersToEscapeEditUTubDescription();

  // Show values and edit button
  showIfHidden($("#URLDeckSubheader"));
  showIfHidden($("#editUTubDescriptionBtn"));

  // Reset errors on hiding of inputs
  resetEditUTubDescriptionFailErrors();
}

// Handles post request and response for editing an existing UTub's description
function editUTubDescription() {
  // Skip if identical
  if ($("#URLDeckSubheader").text() === $("#utubDescriptionUpdate").val()) {
    editUTubDescriptionHideInput();
    return;
  }

  // Extract data to submit in POST request
  [postURL, data] = editUTubDescriptionSetup();

  const request = AJAXCall("patch", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    if (xhr.status === 200) {
      editUTubDescriptionSuccess(response);
    }
  });

  request.fail(function (xhr, _, textStatus) {
    editUTubDescriptionFail(xhr);
  });
}

// Handles preparation for post request to edit an existing UTub
function editUTubDescriptionSetup() {
  const postURL = routes.editUTubDescription(getActiveUTubID());

  const editedUTubDescription = $("#utubDescriptionUpdate").val();
  data = { utubDescription: editedUTubDescription };

  return [postURL, data];
}

// Handle edition of UTub's description
function editUTubDescriptionSuccess(response) {
  const utubDescription = response.utubDescription;

  // Change displayed and editable value for utub description
  $("#URLDeckSubheader").text(utubDescription);
  $("#utubDescriptionUpdate").val(utubDescription);

  // Hide all inputs on success
  editUTubDescriptionHideInput();
}

// Handle error response display to user
function editUTubDescriptionFail(xhr) {
  switch (xhr.status) {
    case 400:
      const responseJSON = xhr.responseJSON;
      if (responseJSON.hasOwnProperty("message")) {
        if (responseJSON.hasOwnProperty("errors"))
          editUTubDescriptionFailShowErrors(responseJSON.errors);
        break;
      }
    case 404:
    default:
      window.location.assign(routes.errorPage);
  }
}

// Cycle through the valid errors for editing a UTub name
function editUTubDescriptionFailShowErrors(errors) {
  for (let key in errors) {
    switch (key) {
      case "utubDescription":
        let errorMessage = errors[key][0];
        displayEditUTubDescriptionFailErrors(key, errorMessage);
    }
  }
}

// Show the error message and highlight the input box border red on error of field
function displayEditUTubDescriptionFailErrors(key, errorMessage) {
  $("#" + key + "Update-error")
    .addClass("visible")
    .text(errorMessage);
  $("#" + key + "Update").addClass("invalid-field");
}

function resetEditUTubDescriptionFailErrors() {
  const editUTubNameFields = ["utubDescription"];
  editUTubNameFields.forEach((fieldName) => {
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
