/** UTub-related constants **/

/* Routes */
// Minor DP 09/17/23 terminology of 'create' vs. 'add', and 'delete' vs. 'remove' -ing UTubs vs. URLs
const ROUTE_ADD_UTUB = "/utub/new";
const ROUTE_EDIT_UTUB_NAME = "/utub/edit_name/"; // +<int:utub_id>
const ROUTE_EDIT_UTUB_DESCRIPTION = "/utub/edit_description/"; // +<int:utub_id>
const ROUTE_DELETE_UTUB = "/utub/delete/"; // +<int:utub_id>

/** UTub UI Interactions **/

$(document).ready(function () {
  // Instantiate UTubDeck with user's accessible UTubs
  try {
    buildUTubDeck(UTubs);
  } catch (error) {
    console.log("Something is wrong!");
    console.log(error);

    $("#listUTubs").append(createNewUTubInputField());
  }

  /* Bind click functions */

  // Create new UTub
  $("#createUTubBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    hideInputs();
    deselectAllURLs();
    addUTubShowInput();

    // Bind enter key (keycode 13) to submit user input
    // DP 12/29 It'd be nice to have a single utils.js function with inputs of function and keyTarget (see semi-successful attempt under bindKeyToFunction() in utils.js)
    unbindEnter();
    $(document).bind("keypress", function (e) {
      if (e.which == 13) {
        checkSameNameUTub(1, $("#createUTub").val());
      }
    });
  });

  // Delete UTub
  $("#deleteUTubBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    deleteUTubShowModal();

    // Bind enter key (keycode 13) to modal submit
    // DP 12/29 bindKeyToFunction() appears to work here. See deleteUTubShowModal();
  });

  // Edit UTub name and description
  $(".editUTubBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    hideInputs();
    deselectAllURLs();
    editUTubShowInput();

    // Bind enter key (keycode 13) to submit user input
    // DP 12/29 It'd be nice to have a single utils.js function with inputs of function and keyTarget (see semi-successful attempt under bindKeyToFunction() in utils.js)
    unbindEnter();
    $(document).bind("keypress", function (e) {
      if (e.which == 13) {
        checkSameNameUTub(0, $("#editUTubName").val());
      }
    });
  });

  // Complete edit UTub name and description
  $(".submitEditUTubBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    checkSameNameUTub(0, $("#editUTubName").val());
  });
});

/** UTub Utility Functions **/

// Streamline the jQuery selector extraction of UTub ID. And makes it easier in case the ID is encoded in a new location in the future
function getActiveUTubID() {
  return $(".UTub.active").attr("utubid");
}

// Streamline the jQuery selector for the UTub Selector.
function UTubSelectorElemFromID(id) {
  return $("label.UTub[utubid='" + id + "']")
}

// Streamline the extraction of a UTub array element from its ID
function UTubElemFromID(id) {
  UTubs.forEach(function (UTub) {
    if (UTub.id === id) return UTub;
  });
}

// Streamline the jQuery selector extraction of UTub ID. And makes it easier in case the ID is encoded in a new location in the future
function UTubIDsFromName(name) {
  let UTubIDs = [];

  UTubs.forEach(function (UTub) {
    if (UTub.name === name) UTubIDs.push(UTub.id);
  });
  return UTubIDs;
}

// Streamline the AJAX call to db for updated info
function getUTubInfo(selectedUTubID) {
  return $.getJSON("/home?UTubID=" + selectedUTubID);
}

// Clear new UTub Form
function resetNewUTubForm() {
  $("#createUTub").val("");
  hideIfShown($("#createUTub").closest(".createDiv"));
}

/** UTub Functions **/

// Assembles components of the UTubDeck (top left panel)
function buildUTubDeck(UTubs) {
  const parent = $("#listUTubs");
  let NumOfUTubs = UTubs.length ? UTubs.length : 0;

  if (NumOfUTubs !== 0) {
    displayState1UTubDeck();

    // Instantiate deck with list of UTubs accessible to current user
    for (let i = 0; i < NumOfUTubs; i++) {
      parent.append(createUTubSelector(UTubs[i].name, UTubs[i].id, i));
    }
  } else {
    displayState0UTubDeck();
  }

  parent.append(createNewUTubInputField());
}

// Creates UTub radio button that changes URLDeck display to show contents of the selected UTub
function createUTubSelector(UTubName, UTubID, index) {
  let label = document.createElement("label");
  let radio = document.createElement("input");

  $(label).attr({
    utubid: UTubID,
    for: "UTub-" + UTubID,
    class: "UTub draw",
    position: index,
  });
  label.innerHTML = "<b>" + UTubName + "</b>";
  // Bind display state change function on click
  $(label).on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    displayState2UTubDeck(UTubID);
  });

  $(radio).attr({
    type: "radio",
    id: "UTub-" + UTubID,
    value: UTubName,
  });

  $(label).append(radio);

  return label;
}

// Creates a typically hidden input text field. When creation of a new UTub is requested, it is shown to the user. Input field recreated here to ensure at the end of list after creation of new UTubs
function createNewUTubInputField() {
  const wrapper = $(document.createElement("div"));
  const wrapperInput = $(document.createElement("div"));
  const wrapperBtns = $(document.createElement("div"));

  const input = $(document.createElement("input"));
  const submit = $(document.createElement("i"));
  const cancel = $(document.createElement("i"));

  $(wrapper)
    .attr({
      style: "display: none",
    })
    .addClass("createDiv row");

  $(wrapperInput).addClass("col-9 col-lg-9 mb-md-0");

  $(input)
    .attr({
      type: "text",
      id: "createUTub",
      placeholder: "New UTub name",
    })
    .addClass("UTub userInput");

  wrapperInput.append(input);

  $(wrapperBtns).addClass(
    "col-3 mb-md-0 text-right d-flex justify-content-center flex-row",
  );

  // Submit addUTub checkbox
  let htmlString =
    '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="b=i bi-check-square-fill" viewBox="0 0 16 16" width="' +
    ICON_WIDTH +
    '" height="' +
    ICON_HEIGHT +
    '">' +
    '<path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm10.03 4.97a.75.75 0 0 1 .011 1.05l-3.992 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.75.75 0 0 1 1.08-.022z"/></svg>';

  $(submit)
    .addClass("mx-1 green-clickable")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      checkSameNameUTub(1, $(input).val());
    })
    .html(htmlString);

  wrapperBtns.append(submit);

  // Cancel add UTub x-box
  htmlString =
    '<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" class="bi bi-x-square-fill text-danger" viewBox="0 0 16 16" width="' +
    ICON_WIDTH +
    '" height="' +
    ICON_HEIGHT +
    '">' +
    '<path d="M2 0a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V2a2 2 0 0 0-2-2zm3.354 4.646L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708"/></svg>';

  $(cancel)
    .addClass("mx-1")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      hideIfShown(wrapper);
    })
    .html(htmlString);

  wrapperBtns.append(cancel);

  wrapper.append(wrapperInput);
  wrapper.append(wrapperBtns);

  return wrapper;
}

function unbindUTubSelectionBehavior(selectedUTubID) {
  // Select new UTub
  let selectedUTubSelector = UTubSelectorElemFromID(selectedUTubID);
  selectedUTubSelector.addClass("active");
  // Unbind selection function
  selectedUTubSelector.off("click");
}

function bindUTubSelectionBehavior() {
  // Unselect any already selected UTub
  let departureUTubSelector = UTubSelectorElemFromID(getActiveUTubID());
  if (departureUTubSelector) {
    // Change UTub
    departureUTubSelector.removeClass("active");
    // Rebind selection function
    $(departureUTubSelector).on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      displayState2UTubDeck(departureUTubLabel.attr("utubid"));
    });
  }
}

// Display state 0: Clean slate
function displayState0UTubDeck() {
  // Subheader prompt user to create a UTub
  showIfHidden($("#UTubDeckSubheader").closest(".row"));
  $("#UTubDeckSubheader").text("Create a UTub");

  // Hide delete UTub button
  hideIfShown($("#deleteUTubBtn"));
}

// Display state 1: UTubs list, none selected
function displayState1UTubDeck() {
  // Subheader prompt hidden
  showIfHidden($("#UTubDeckSubheader").closest(".row"));
  $("#UTubDeckSubheader").text("Select a UTub");

  // Hide delete UTub button
  hideIfShown($("#deleteUTubBtn"));
}

// Display state 2: UTubs list, 1x selected
function displayState2UTubDeck(selectedUTubID) {
  hideInputs();

  // UTubDeck display updates
  // Subheader prompt hidden
  hideIfShown($("#UTubDeckSubheader").closest(".row"));

  bindUTubSelectionBehavior();
  unbindUTubSelectionBehavior(selectedUTubID);

  // Show delete UTub button
  showIfHidden($("#deleteUTubBtn"));

  getUTubInfo(selectedUTubID).then(function (selectedUTub) {
    // Parse incoming data, pass them into subsequent functions as required
    let dictURLs = selectedUTub.urls;
    let dictTags = selectedUTub.tags;
    let dictUsers = selectedUTub.members;
    let UTubOwnerID = selectedUTub.created_by;
    let UTubDescription = selectedUTub.description;

    // // Tag deck display updates
    // if(dictTags) displayState2TagDeck(dictTags);
    // else displayState1TagDeck();

    // // Center panel
    // if(dictURLs) displayState1URLDeck(dictURLs, dictTags);
    // else displayState0URLDeck();

    // // RH panels
    // if(dictUsers) displayState1UserDeck(dictUsers, UTubOwnerID);
    // else displayState0UserDeck();
    

    if(UTubDescription) displayState2UTubDescriptionDeck(UTubDescription);
    else displayState1UTubDescriptionDeck();
  });
}

// Display state 0: Clean slate, no UTub selected
function displayState0UTubDescriptionDeck() {
  // Subheader prompt hidden
  hideIfShown($("#UTubDescriptionDeckSubheader").closest(".row"));

  // Edit UTub Description button hidden
  hideIfShown($("#editUTubBtn"));

  // Clear description values
  $("#UTubDescription").text("");
  $("#editUTubDescription").val("");
}

// Display state 1: UTub selected, no description
function displayState1UTubDescriptionDeck() {
  // Subheader prompt shown
  showIfHidden($("#UTubDescriptionDeckSubheader").closest(".row"));

  // Edit UTub Description button shown
  showIfHidden($("#editUTubBtn"));
}

// Display state 2: UTub selected, description exists
function displayState2UTubDescriptionDeck(UTubDescription) {
  // Subheader prompt hidden
  hideIfShown($("#UTubDescriptionDeckSubheader").closest(".row"));

  // Edit UTub Description button shown, submission button hidden
  showIfHidden($("#editUTubBtn"));
  hideIfShown($("#submitEditUTubBtn"));

  // Update description values
  let p = $("#UTubDescription");
  showIfHidden(p);
  p.text(UTubDescription);
  let editUTubDescription = $("#editUTubDescription");
  hideIfShown(editUTubDescription.closest(".createDiv"));
  editUTubDescription.val(UTubDescription);
}

// Display state 3: UTub selected, edit active
function displayState3UTubDescriptionDeck(UTubDescription) {
  // Subheader prompt hidden
  hideIfShown($("#UTubDescriptionDeckSubheader").closest(".row"));

  // Submission button shown, edit UTub Description button hidden
  hideIfShown($("#editUTubBtn"));
  showIfHidden($("#submitEditUTubBtn"));

  // Update description values
  let editUTubDescription = $("#editUTubDescription");
  hideIfShown(editUTubDescription.closest(".createDiv"));
  editUTubDescription.val(UTubDescription);
}

// Handles display changes in response to UTubs change or creation
function displayUpdateUTubActive(selectedUTub) {
  let UTubName = selectedUTub.name;
  let UTubID = selectedUTub.id;
  let UTubDescription = selectedUTub.description;
  let UTubOwnerID = selectedUTub.created_by;
  let UTubUsers = selectedUTub.members; // 12/17 DP change JSON to match route and frontend naming convention, users vs members

  if (selectedUTub.urls.length > 0) showIfHidden($("#accessAllURLsBtn"));
  else hideIfShown($("#accessAllURLsBtn"));
  showIfHidden($("#UTubDescription"));

  // UserDeck display updates
  // Extract owner username
  let UTubOwnerUsername = "";
  UTubUsers.forEach(function (user) {
    if (user.id === UTubOwnerID) UTubOwnerUsername = user.username;
  });
  $("#UserDeckHeader").text("Users");
  $("#UTubOwner").text(UTubOwnerUsername);
  if (getCurrentUserID() == UTubOwnerID) {
    showIfHidden($("#addUserBtn"));
  } else {
    hideIfShown($("#addUserBtn"));
  }
}

/** Post data handling **/

// Checks if submitted UTub name exists in db
function checkSameNameUTub(mode, name) {
  // Count UTubs with same name
  let sameNameCounter = 0;
  try {
    sameNameCounter = numSameNameUTub(name);
  } catch (error) {
    sameNameCounter = 0;
  }

  let sameNameBool = false;
  // Toggle boolean to determine whether to display warning modal
  if (sameNameCounter > 0) sameNameBool = true;

  if (sameNameBool) sameNameWarningShowModal(mode, UTubIDsFromName(name));
  else mode ? addUTub() : editUTub();
}

// Counts number of UTubs with the same name
// DP 10/22 When I add/delete UTubs, I get a response for the single UTub information. But this doesn't give me updated information about the aggregate of the user's UTubs. This check for the same name requires a loop variable. Is it best to recount based on #listUTubs?
// DP 10/22 When I edit UTubs, I get a response for the single UTub information. But this doesn't give me updated information about the aggregate of the user's UTubs. This check does not catch if user changes two UTubs to a third similar name. Ex. UTub1 --> UTub3, UTub2 --> UTub3, should throw error but does not. Is it best to recount based on #listUTubs?
function numSameNameUTub(name) {
  let counter = 0;

  for (i = 0; i < UTubs.length; i++) {
    if (UTubs[i].name === name) counter++;
  }

  return counter;
}

// Hides modal for UTub same name action confirmation
function sameNameWarningHideModal() {
  $("#confirmModal").modal("hide");
  unbindEnter();
}

// Handles a double check if user inputs a new UTub name similar to one already existing. mode 1 'add', mode 0 'edit'
function sameNameWarningShowModal(mode, UTubID) {
  let modalTitle = "Are you sure you want to create a new UTub with this name?";
  let modalBody = "A UTub in your repository has a similar name.";
  let buttonTextDismiss = "Go back and change name";
  let buttonTextRedirect = "Go to UTub";
  let buttonTextSubmit = "Create";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-default")
    .text(buttonTextDismiss)
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      sameNameWarningHideModal();
      highlightInput(mode ? $("#createUTub") : $("#editUTubName"));
    });
  bindKeyToFunction(sameNameWarningHideModal, 27);

  showIfHidden($("#modalRedirect"));
  $("#modalRedirect")
    .addClass("btn btn-primary")
    .text(buttonTextRedirect)
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      $("#confirmModal").modal("hide");
      mode ? addUTubHideInput() : editUTubHideInput();
      displayState2UTubDeck(UTubID);
    });

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      mode ? addUTub() : editUTub();
    });
  // bindKeyToFunction(removeURL, 13);
  // 01/03/24 may want to separate sameNameWarningShowModal for add and edit

  $("#confirmModal").modal("show");
}

/* Add UTub */

// Shows new UTub input fields
function addUTubShowInput() {
  showInput("createUTub");
  highlightInput($("#createUTub"));
}

// Hides new UTub input fields
function addUTubHideInput() {
  hideInput("createUTub");
  unbindEnter(); // unbinding doesn't seem to work...
}

// Handles post request and response for adding a new UTub
function addUTub() {
  // Extract data to submit in POST request
  [postURL, data] = addUTubSetup();

  let request = AJAXCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status == 200) {
      console.log(response);
      addUTubSuccess(response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    addUTubFail(response, textStatus, xhr);
  });

  unbindEnter();
}

// Handles preparation for post request to create a new UTub
function addUTubSetup() {
  let newUTubName = $("#createUTub").val();
  data = { name: newUTubName };

  return [ROUTE_ADD_UTUB, data];
}

// Handle creation of new UTub
function addUTubSuccess(response) {
  // DP 12/28/23 One problem is that confirmed DB changes aren't yet reflected on the page. Ex. 1. User makes UTub name change UTub1 -> UTub2. 2. User attempts to create new UTub UTub1. 3. Warning modal is thrown because no AJAX call made to update the passed UTubs json.

  let UTubID = response.UTub_ID;

  resetNewUTubForm();

  if (!isHidden($("#confirmModal")[0])) $("#confirmModal").modal("hide");

  let createUTub = $("#createUTub").closest(".createDiv").detach();
  let index = Number($(".UTub").last().attr("position"))
    ? Number($(".UTub").last().attr("position"))
    : 0;
  let nextIndex = index + 1;

  // Create and append newly created UTub selector
  $("#listUTubs").append(
    createUTubSelector(response.UTub_name, UTubID, nextIndex),
  );
  // Reorder createDiv after latest created UTub selector
  $("#listUTubs").append(createUTub);

  displayState2UTubDeck(UTubID)
}

function addUTubFail(response, textStatus, xhr) {
  if (xhr.status == 409) {
    console.log(
      "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
    );
  } else if (xhr.status == 404) {
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
    response.error.Error_code +
    ". Status: " +
    response.error.Message,
  );
}

/* Edit UTub */

// Shows input fields for editing an exiting UTub's name and description
function editUTubShowInput() {
  // Hide exisitng values and edit button
  hideIfShown($("#URLDeckHeader"));
  hideIfShown($("#UTubDescription"));
  hideIfShown($(".editUTubBtn"));
  hideIfShown($("#addURLBtn"));

  // Show temporary div element containing UTub description
  showInput("editUTubDescription");
  showIfHidden($(".submitEditUTubBtn"));

  // Show temporary div element containing UTub name
  showInput("editUTubName");
}

// Hides input fields for editing an exiting UTub's name and description
function editUTubHideInput() {
  // Hide exisitng values and edit button
  showIfHidden($("#URLDeckHeader"));
  showIfHidden($("#UTubDescription"));
  showIfHidden($(".editUTubBtn"));
  showIfHidden($("#addURLBtn"));

  // Show temporary div element containing UTub description
  hideInput("editUTubDescription");
  hideIfShown($(".submitEditUTubBtn"));

  // Show temporary div element containing UTub name
  hideInput("editUTubName");
}

// Handles post request and response for adding a new UTub
function editUTub() {
  // Extract data to submit in POST request
  [postURL, data] = editUTubNameSetup();

  let request = AJAXCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status == 200) {
      editUTubNameSuccess(response);
      editUTubDescription();
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    editUTubFail(response, textStatus, xhr);
  });
}

//
function editUTubDescription() {
  // Extract data to submit in POST request
  [postURL, data] = editUTubDescriptionSetup();

  let request = AJAXCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status == 200) {
      editUTubDescriptionSuccess(response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    editUTubFail(response, textStatus, xhr);
  });
}

// Handles preparation for post request to edit an existing UTub
function editUTubNameSetup() {
  let postURL = ROUTE_EDIT_UTUB_NAME + getActiveUTubID();

  let editedUTubName = $("#editUTubName").val();
  data = { name: editedUTubName };

  return [postURL, data];
}

// Handles preparation for post request to edit an existing UTub
function editUTubDescriptionSetup() {
  let postURL = ROUTE_EDIT_UTUB_DESCRIPTION + getActiveUTubID();

  let editedUTubDescription = $("#editUTubDescription").val();
  data = { utub_description: editedUTubDescription };

  return [postURL, data];
}

//
function editUTubNameSuccess(response) {
  let UTubName = response.UTub_name;

  if (!isHidden($("#confirmModal")[0])) $("#confirmModal").modal("hide");

  // UTubDeck display updates
  let editedUTubLabel = $("#listUTubs").find(".active");
  editedUTubLabel.find("b").text(UTubName);

  // URLDeck display updates
  $("#URLDeckHeader").text(UTubName);
  $("#editUTubName").val(UTubName);
}

//
function editUTubDescriptionSuccess(response) {
  let UTubDescription = response.UTub_description;

  if (!isHidden($("#confirmModal")[0])) $("#confirmModal").modal("hide");

  // URLDeck display updates
  $("#UTubDescription").text(UTubDescription);
  $("#editUTubDescription").val(UTubDescription);

  editUTubHideInput();
}

//
function editUTubFail(response, textStatus, xhr) {
  console.log("Error: Could not create UTub");
  console.log(response);

  if (xhr.status == 409) {
    console.log(
      "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
    );
  } else if (xhr.status == 404) {
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
    response.responseJSON.Error_code +
    ". Status: " +
    response.responseJSON.Message,
  );
}

/* Delete UTub */

// Hide confirmation modal for deletion of the current UTub
function deleteUTubHideModal() {
  $("#confirmModal").modal("hide");
  unbindEnter();
}

// Show confirmation modal for deletion of the current UTub
function deleteUTubShowModal() {
  let modalTitle = "Are you sure you want to delete this UTub?";
  let modalBody =
    "This action will remove all URLs in UTub and is irreverisible!";
  let buttonTextDismiss = "Nevermind...";
  let buttonTextSubmit = "Delete this sucka!";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-default")
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      deleteUTubHideModal();
    })
    .text(buttonTextDismiss);
  bindKeyToFunction(deleteUTubHideModal, 27);

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-danger")
    .text(buttonTextSubmit)
    .on("click", function (e) {
      e.preventDefault();
      deleteUTub();
    });
  bindKeyToFunction(deleteUTub, 13);

  $("#confirmModal").modal("show");

  hideIfShown($("#modalRedirect"));
}

// Handles deletion of a current UTub
function deleteUTub() {
  // Extract data to submit in POST request
  postURL = deleteUTubSetup();

  let request = AJAXCall("post", postURL, []);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status == 200) {
      deleteUTubSuccess();
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    deleteUTubFailure(response, textStatus, xhr);
  });

  unbindEnter();
}

// Prepares post request inputs to delete the current UTub
function deleteUTubSetup() {
  let postURL = ROUTE_DELETE_UTUB + getActiveUTubID();

  return postURL;
}

function deleteUTubSuccess() {
  hideInputs();

  // Close modal
  $("#confirmModal").modal("hide");

  // Update UTub Deck
  let currentUTubID = getActiveUTubID();
  let UTubSelector = $("label[utubid=" + currentUTubID + "]");
  UTubSelector.fadeOut();
  UTubSelector.remove();

  hideIfShown($(".editUTubBtn"));
  hideIfShown($("#addURLBtn"));
  hideIfShown($("#UTubDescription"));

  UTubs.splice($.inArray(UTubElemFromID(currentUTubID), UTubs), 1);

  buildUTubDeck(UTubs);
}

function deleteUTubFailure(xhr, textStatus, error) {
  console.log("Error: Could not delete UTub");

  if (xhr.status == 409) {
    console.log(
      "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
    );
    // const flashMessage = xhr.responseJSON.error;
    // const flashCategory = xhr.responseJSON.category;

    // let flashElem = flashMessageBanner(flashMessage, flashCategory);
    // flashElem.insertBefore('#modal-body').show();
  } else if (xhr.status == 404) {
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
    response.error.Error_code +
    ". Status: " +
    response.error.Message,
  );
}
