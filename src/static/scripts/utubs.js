/** UTub-related constants **/

/* Routes */
// Minor DP 09/17/23 terminology of 'create' vs. 'add', and 'delete' vs. 'remove' -ing UTubs vs. URLs
const ROUTE_ADD_UTUB = "/utub/new";
const ROUTE_EDIT_UTUB_NAME = "/utub/edit_name/"; // +<int:utub_id>
const ROUTE_EDIT_UTUB_DESCRIPTION = "/utub/edit_description/"; // +<int:utub_id>
const ROUTE_DELETE_UTUB = "/utub/delete/"; // +<int:utub_id>

/** UTub UI Interactions **/

$(document).ready(function () {
  displayState0();
  // Instantiate UTubDeck with user's accessible UTubs
  try {
    buildUTubDeck(UTubs);
  } catch (error) {
    console.log("Something is wrong!");
    console.log(error);
  }

  /* Bind click functions */

  // Create new UTub
  $("#createUTubBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    hideInputs();
    deselectAllURLs();
    addUTubShowInput();
  });

  // Delete UTub
  $("#deleteUTubBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    deleteUTubShowModal();

    // Bind enter key (keycode 13) to modal submit
    // DP 12/29 bindKeyToFunction() appears to work here. See deleteUTubShowModal();
  });

  // Edit UTub name
  $("#editUTubNameBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    hideInputs();
    deselectAllURLs();
    editUTubNameShowInput();
  });


  $("#submitEditUTubNameBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    checkSameNameUTub(0, $("#editUTubName").val());
  })

  // Edit UTub description
  $("#editUTubDescriptionBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    editUTubDescriptionShowInput();
  });


  $("#submitEditUTubDescriptionBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    editUTubDescription();
  })
});

/** UTub Utility Functions **/

// Function to count number of UTubs current user has access to
function getNumOfUTubs() {
  return $("#listUTubs > .UTub").length
}

// Streamline the jQuery selector extraction of UTub ID. And makes it easier in case the ID is encoded in a new location in the future
function getActiveUTubID() {
  return $(".UTub.active").attr("utubid");
}

// Streamline the jQuery selector for the UTub Selector.
function getUTubSelectorElemFromID(id) {
  return $("div.UTub[utubid='" + id + "']");
}

// Streamline the extraction of a UTub array element from its ID
function getUTubObjFromID(id) {
  UTubs.forEach(function (UTub) {
    if (UTub.id === id) return UTub;
  });
}

// Streamline the jQuery selector extraction of UTub ID. And makes it easier in case the ID is encoded in a new location in the future
function getUTubIDFromName(name) {
  let UTubIDs = [];

  UTubs.forEach(function (UTub) {
    if (UTub.name === name) UTubIDs.push(UTub.id);
  });
  return UTubIDs;
}

// Streamline the jQuery selector extraction of UTub name.
function getCurrentUTubName() {
  return $("div.UTub.active").find(".UTubName").text();
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

// Clear the UTub Deck
function resetUTubDeck() {
  $("#listUTubs").empty();
}

/** UTub Functions **/

// Assembles components of the UTubDeck (top left panel)
function buildUTubDeck(UTubs) {
  resetUTubDeck();
  const parent = $("#listUTubs");
  let numOfUTubs = UTubs.length;

  if (numOfUTubs !== 0) {
    // Instantiate deck with list of UTubs accessible to current user
    for (let i = 0; i < numOfUTubs; i++) {
      parent.append(createUTubSelector(UTubs[i].name, UTubs[i].id, i));
    }

    displayState1UTubDeck(null, null);
    displayState0URLDeck();
  } else displayState0UTubDeck();

  parent.append(createNewUTubInputField());
}

// Handles progagating changes across page related to a UTub selection
function selectUTub(selectedUTubID) {
  getUTubInfo(selectedUTubID).then(function (selectedUTub) {
    // Parse incoming data, pass them into subsequent functions as required
    let UTubName = selectedUTub.name;
    let dictURLs = selectedUTub.urls;
    let dictTags = selectedUTub.tags;
    let dictUsers = selectedUTub.members;
    let UTubOwnerID = selectedUTub.created_by;
    let UTubDescription = selectedUTub.description;

    // LH panels
    // UTub deck
    displayState1UTubDeck(selectedUTubID, UTubOwnerID);

    // Tag deck
    buildTagDeck(dictTags);

    // Center panel
    // URL deck
    buildURLDeck(UTubName, dictURLs, dictTags);

    // RH panels
    // UTub Description deck
    if (UTubDescription) displayState2UTubDescriptionDeck(UTubDescription);
    else displayState1UTubDescriptionDeck();

    // Users deck
    buildUserDeck(dictUsers, UTubOwnerID);
  });
}

// Creates UTub radio button that changes URLDeck display to show contents of the selected UTub
function createUTubSelector(UTubName, UTubID, index) {
  let container = document.createElement("div");
  let name = document.createElement("b");
  let label = document.createElement("label");
  let radio = document.createElement("input");

  $(container)
    .addClass("UTub draw")
    .attr({
      utubid: UTubID,
      position: index,
    })
    // Bind display state change function on click
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      selectUTub(UTubID);
    });

  $(name).addClass("UTubName").text(UTubName);

  $(label).attr({ for: "UTub-" + UTubID });

  $(radio).attr({
    type: "radio",
    id: "UTub-" + UTubID,
    value: UTubName,
  });

  $(container).append(name);
  $(container).append(label);
  $(container).append(radio);

  return container;
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
    .addClass("createDiv row")
    .attr({ style: "display: none" });

  $(wrapperInput)
    .addClass("col-9 col-lg-9 mb-md-0");

  $(input)
    .addClass("userInput")
    .attr({
      type: "text",
      id: "createUTub",
      placeholder: "New UTub name",
    });

  wrapperInput.append(input);

  $(wrapperBtns)
    .addClass("col-3 mb-md-0 text-right d-flex justify-content-center flex-row");

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
  let selectedUTubSelector = getUTubSelectorElemFromID(selectedUTubID);
  selectedUTubSelector.addClass("active");
  // Unbind selection function
  selectedUTubSelector.off("click");
}

function bindUTubSelectionBehavior() {
  // Unselect any already selected UTub
  let departureUTubSelector = getUTubSelectorElemFromID(getActiveUTubID());
  if (departureUTubSelector) {
    // Change UTub
    departureUTubSelector.removeClass("active");
    // Rebind selection function
    $(departureUTubSelector).on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      selectUTub(departureUTubSelector.attr("utubid"));
    });
  }
}

/** UTub Display State Functions **/

// Display state 0: Clean slate, no UTubs
function displayState0UTubDeck() {
  // Subheader to prompt user to create a UTub shown
  $("#UTubDeckSubheader").text("Create a UTub");

  // Hide delete UTub button
  hideIfShown($("#deleteUTubBtn"));
}

// Display state 1: UTubs list, none selected. selectedUTubID, UTubOwnerID == null
// Enter into this state only at page load, or after UTub deletion
// Display state 2: UTubs list, 1x selected
// Enter into this state change only if new UTub is selected
// No actions performed within other decks can affect UTub Deck display
function displayState1UTubDeck(selectedUTubID, UTubOwnerID) {
  hideInputs();

  // Subheader to tell user how many UTubs are accessible
  $("#UTubDeckSubheader").text(getNumOfUTubs() + " Accessible UTubs");

  // UTub selected

  // Bind selection behavior to depature UTub, unbind from selected UTub
  bindUTubSelectionBehavior();
  if (selectedUTubID) {
    unbindUTubSelectionBehavior(selectedUTubID);
    showIfHidden($("#editUTubNameBtn"));
    showIfHidden($("#editUTubDescriptionBtn"));
  }

  if (getCurrentUserID() == UTubOwnerID) {
    showIfHidden($("#deleteUTubBtn"));
  } else hideIfShown($("#deleteUTubBtn"));
}

/** UTub Description Display State Functions **/

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

  // Update description values
  let p = $("#UTubDescription");
  hideIfShown(p);
  p.text("");
  let editUTubDescription = $("#editUTubDescription");
  hideIfShown(editUTubDescription.closest(".createDiv"));
  editUTubDescription.val("");
}

// Display state 2: UTub selected, description exists
function displayState2UTubDescriptionDeck(UTubDescription) {
  if (UTubDescription) {
    // Subheader prompt hidden
    hideIfShown($("#UTubDescriptionDeckSubheader").closest(".row"));

    // Edit UTub Description button shown, submission button hidden
    showIfHidden($("#editUTubBtn"));
    hideIfShown($(".submitEditUTubBtn"));

    // Update description values
    let p = $("#UTubDescription");
    showIfHidden(p);
    p.text(UTubDescription);

    let editUTubDescription = $("#editUTubDescription");
    hideIfShown(editUTubDescription.closest(".createDiv"));
    editUTubDescription.val(UTubDescription);
  } // User edited description to empty string
  else displayState1UTubDescriptionDeck();
}

// Display state 3: UTub selected, edit active
function displayState3UTubDescriptionDeck(UTubDescription) {
  // Subheader prompt hidden
  hideIfShown($("#UTubDescriptionDeckSubheader").closest(".row"));

  // Submission button shown, edit UTub Description button hidden
  hideIfShown($("#editUTubBtn"));
  showIfHidden($(".submitEditUTubBtn"));

  // Update description values
  let editUTubDescription = $("#editUTubDescription");
  hideIfShown(editUTubDescription.closest(".createDiv"));
  editUTubDescription.val(UTubDescription);
}

/** Post data handling **/

// Checks if submitted UTub name exists in db. mode is 0 for editUTub, 1 for addUTub
function checkSameNameUTub(mode, name) {
  // Count UTubs with same name
  let sameNameCounter = 0;
  try {
    sameNameCounter = numSameNameUTub(name);
  } catch (error) {
    sameNameCounter = 0;
  }

  // If editUTub, ignore one instance of names
  if (!mode) sameNameCounter -= 1;

  if (sameNameCounter > 0) sameNameWarningShowModal(mode, getUTubIDFromName(name));
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
      displayState1UTubDeck(UTubID, getCurrentUTubCreatorID());
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

  console.log("About to make post AJAX call")
  let request = AJAXCall("post", postURL, data);

  // Handle response
  request.done(function (response, textStatus, xhr) {
    console.log("success");

    if (xhr.status == 200) {
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
  resetNewUTubForm();

  let UTubID = response.UTub_ID;

  $("#confirmModal").modal("hide");

  // Remove createDiv; Reattach after addition of new UTub
  $("#createUTub").closest(".createDiv").remove();

  // Create and append newly created UTub selector
  let index = Number($(".UTub").last().attr("position"));
  let nextIndex = index + 1;
  let listUTubs = $("#listUTubs");
  listUTubs.append(createUTubSelector(response.UTub_name, UTubID, nextIndex));

  // Create new createDiv after latest created UTub selector
  listUTubs.append(createNewUTubInputField());

  selectUTub(UTubID);
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

// Shows input fields for editing an exiting UTub's name 
function editUTubNameShowInput() {
  // Show edit fields
  showInput("editUTubName");

  // Hide current name and edit button
  hideIfShown($("#URLDeckHeader"));
  hideIfShown($("#editUTubNameBtn"));
  hideIfShown($("#addURLBtn"));
}

// Hides input fields for editing an exiting UTub's name
function editUTubNameHideInput() {
  // Hide edit fields
  hideInput("editUTubName");

  // Show values and edit button
  showIfHidden($("#URLDeckHeader"));
  showIfHidden($("#editUTubNameBtn"));
  showIfHidden($("#addURLBtn"));
}

// Shows input fields for editing an exiting UTub's description
function editUTubDescriptionShowInput() {
  // Show edit fields
  showInput("editUTubDescription");
  showIfHidden($("#submitEditUTubDescriptionBtn"));

  // Hide current description and edit button
  hideIfShown($("#UTubDescription"));
  hideIfShown($("#editUTubDescriptionBtn"));
}

// Hides input fields for editing an exiting UTub's description
function editUTubDescriptionHideInput() {
  // Hide edit fields
  hideInput("editUTubDescription");
  hideIfShown($("#submitEditUTubDescriptionBtn"));

  // Show values and edit button
  showIfHidden($("#UTubDescription"));
  hideIfShown($("#editUTubDescriptionBtn"));
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

  // Display updates
  displayState1UTubDeck(getActiveUTubID(), getCurrentUTubCreatorID());
  displayState1URLDeck();
}

//
function editUTubDescriptionSuccess(response) {
  let UTubDescription = response.UTub_description;

  if (!isHidden($("#confirmModal")[0])) $("#confirmModal").modal("hide");

  displayState2UTubDescriptionDeck(UTubDescription);
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
    .off("click")
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
  let UTubSelector = $("div[utubid=" + currentUTubID + "]");
  UTubSelector.fadeOut();
  UTubSelector.remove();

  // Reset all panels
  displayState0();

  displayState1UTubDeck(null, null)

  if ($("#listUTubs").find("div.UTub").length == 0) displayState0UTubDeck();
}

function deleteUTubFailure(response, textStatus, xhr) {
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
