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
  buildUTubDeck(UTubs);

  /* Bind click functions */

  // Create new UTub
  $("#createUTubButton").on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    addUTubShowInput();
  });

  // Delete UTub
  $("#deleteUTubButton").on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    deleteUTubShowModal();
  });

  // Edit UTub name and description
  $("#editUTubButton").on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    editUTubShowInput();
  });

  // Complete edit UTub name and description
  $("#submitEditUTubButton").on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    let proposedUTubName = $("#editUTubName").val();
    if (checkSameNameUTub(proposedUTubName))
      sameNameWarningShowModal(0, UTubIDFromName(proposedUTubName));
    else editUTub();
  });
});

/** UTub Utility Functions **/

// Streamline the jQuery selector extraction of UTub ID. And makes it easier in case the ID is encoded in a new location in the future
function currentUTubID() {
  return $(".UTub.active").find("input").attr("utubid");
}

// Streamline the jQuery selector extraction of UTub ID. And makes it easier in case the ID is encoded in a new location in the future
function UTubIDFromName(name) {
  for (let i = 0; i < UTubs.length; i++) {
    if (UTubs[i].name === name) return UTubs[i].id;
  }
}

// Streamline the AJAX call to db for updated info
function getUtubInfo(selectedUTubID) {
  return $.getJSON("/home?UTubID=" + selectedUTubID);
}

// Clear new UTub Form
function resetNewUTUbForm() {
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
  let NumOfUTubs = UTubs.length;

  if (NumOfUTubs !== 0) {
    // Instantiate deck with list of UTubs accessible to current user
    for (let i = 0; i < NumOfUTubs; i++) {
      parent.append(createUTubSelector(UTubs[i].name, UTubs[i].id, i));
    }
  }

  parent.append(createNewUTubInputField());

  // Display changes needed regardless of UTubDeck status
  displayUpdateUTubChange(NumOfUTubs, null);
}

// Creates UTub radio button that changes URLDeck display to show contents of the selected UTub
function createUTubSelector(UTubName, UTubID, index) {
  let label = document.createElement("label");
  let radio = document.createElement("input");

  $(label).attr({
    for: "UTub-" + UTubID,
    class: "UTub draw",
    position: index,
  });
  label.innerHTML = "<b>" + UTubName + "</b>";
  // Bind changeUTub function on click
  $(label).on("click", function (e) {
    e.stopPropagation();
    e.preventDefault();
    changeUTub(UTubID);
  });

  $(radio).attr({
    type: "radio",
    id: "UTub-" + UTubID,
    utubid: UTubID,
    value: UTubName,
  });

  $(label).append(radio);

  return label;
}

// Creates a typically hidden input text field. When creation of a new UTub is requested, it is shown to the user. Input field recreated here to ensure at the end of list after creation of new UTubs
function createNewUTubInputField() {
  let wrapper = $(document.createElement("div"));
  let wrapperInput = $(document.createElement("div"));
  let wrapperBtns = $(document.createElement("div"));
  let input = $(document.createElement("input"));
  let submit = $(document.createElement("i"));
  let cancel = $(document.createElement("i"));

  $(wrapper)
    .attr({
      class: "createDiv",
      style: "display: none",
    })
    .on("blur", function (e) {
      e.stopPropagation();
      e.preventDefault();
      hideIfShown(wrapper);
    });

  $(wrapperInput).attr({ class: "col-9 col-lg-9 mb-md-0" });

  $(input).attr({
    type: "text",
    id: "createUTub",
    class: "UTub userInput",
    placeholder: "New UTub name",
  });

  wrapperInput.append(input);

  $(wrapperBtns).attr({
    class:
      "col-3 col-lg-3 mb-md-0 text-right d-flex justify-content-center flex-row",
  });

  $(submit)
    .attr({ class: "fa fa-check-square fa-2x text-success mx-1" })
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      let proposedUTubName = $(input).val();
      if (checkSameNameUTub(proposedUTubName))
        sameNameWarningShowModal(1, UTubIDFromName(proposedUTubName));
      else addUTub();
    });

  wrapperBtns.append(submit);

  $(cancel)
    .attr({ class: "fa bi-x-square-fill fa-2x text-danger mx-1" })
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      hideIfShown(wrapper);
    });

  wrapperBtns.append(cancel);

  wrapper.append(wrapperInput);
  wrapper.append(wrapperBtns);

  return wrapper;
}

// User selected a UTub, display data
function changeUTub(selectedUTubID) {
  getUtubInfo(selectedUTubID).then(function (selectedUTub) {
    // Parse incoming data, pass them into subsequent functions as required
    let dictURLs = selectedUTub.urls;
    let dictTags = selectedUTub.tags;
    let dictUsers = selectedUTub.members;
    let creator = selectedUTub.created_by;
    let currentUserID = $(".user").attr("id");

    // UTubDeck display updates
    displayUpdateUTubChange(null, selectedUTub); // NumOfUTubs variable set to null. If changeUTub() is called, existence of UTubs is guaranteed

    // Tag deck display updates
    buildTagDeck(dictTags);

    // Center panel
    buildURLDeck(dictURLs, dictTags);

    // RH panels
    // Update UTub description, not yet implemented on backend
    // $('#UTubInfo').text(selectedUTub.description);

    gatherUsers(dictUsers, creator);
  });
}

// Updates page display in response to current UTubDeck status.  If
function displayUpdateUTubChange(NumOfUTubs, selectedUTub) {
  if (!NumOfUTubs === 0) {
    // User has no UTubs
    $("#UTubDeckHeader").text("Create a UTub");

    $("#URLDeckHeader").text("<----------- Oops, no UTubs! Create one!");
  } else {
    // User has access to UTubs
    $("#UTubDeckHeader").text("UTubs");

    if (selectedUTub) {
      // New UTub created or selected UTub is active
      displayUpdateUTubActive(selectedUTub);
    } else {
      // UTub deleted or page refresh. No active UTub
      displayUpdateUTubInactive();
    }
  }
}

// New user, or user has deleted their final UTub, base site displayed
function displayUpdateUTubInactive() {
  // UTubDeck display updates
  hideIfShown($("#deleteUTubButton"));

  // TagDeck display updates
  $("#TagDeckHeader").text("No UTub Selected");

  // URLDeck display updates
  $("#URLDeckHeader").text("Select a UTub");
}

// Handles display changes in response to UTubs change or creation
function displayUpdateUTubActive(selectedUTub) {
  // Extract relevant data
  let UTubName = selectedUTub.name;
  let UTubID = selectedUTub.id;
  let UTubDescription = selectedUTub.description;

  // UTubDeck display updates
  showIfHidden($("#deleteUTubButton"));
  // Unselect any already selected UTub
  let departureUTubLabel = $("#listUTubs").find(".active");
  if (departureUTubLabel) {
    // Change UTub
    departureUTubLabel.removeClass("active");
    // Rebind selection function
    $(departureUTubLabel).on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      changeUTub(departureUTubLabel.find("input[type=radio]").attr("utubid"));
    });
  }
  // Select new UTub
  let selectedUTubRadio = $("input[utubid=" + UTubID + "]");
  let selectedUTubLabel = selectedUTubRadio.parent();
  selectedUTubLabel.addClass("active");
  // Unbind selection function
  $(selectedUTubLabel).off("click");

  // URLDeck display updates
  $("#URLDeckHeader").text(UTubName);
  $("#UTubDescription").text(UTubDescription);
  $("#editUTubName").val(UTubName);
  $("#editUTubDescription").val(UTubDescription);
  showIfHidden($("#editUTubButton"));
  showIfHidden($("#addURLBtn"));
  showIfHidden($("#UTubDescription"));
}

/** Post data handling **/

// Checks if submitted UTub name exists in db
function checkSameNameUTub(name) {
  // Extract existing UTub names for comparison
  let UTubNames = UTubs.map((x) => x.name);

  return UTubNames.includes(name);
}

// Handles a double check if user inputs a new UTub name similar to one already existing. mode 1 'add', mode 0 'edit'
function sameNameWarningShowModal(mode, UTubID) {
  let modalTitle = "Are you sure you want to create a new UTub with this name?";
  let modalBody = "A UTub in your repository has a similar name.";
  let buttonTextDismiss = "Go back and change name";
  let buttonTextRedirect = "Go to UTub";
  let buttonTextSubmit = "Create";

  $(".modal-title").text(modalTitle);
  $("#modal-body").text(modalBody);
  $("#modalDismiss").attr({ class: "btn btn-default" }).text(buttonTextDismiss);
  $("#modalDismiss").off("click");
  $("#modalDismiss").on("click", function (e) {
    e.preventDefault();
    $("#confirmModal").modal("hide");
    highlightInput(mode ? $("#createUTub") : $("#editUTubName"));
  });

  showIfHidden($("#modalRedirect"));
  $("#modalRedirect")
    .attr({ class: "btn btn-primary" })
    .text(buttonTextRedirect);
  $("#modalRedirect").off("click");
  $("#modalRedirect").on("click", function (e) {
    e.preventDefault();
    $("#confirmModal").modal("hide");
    mode ? addUTubHideInput() : editUTubHideInput();
    changeUTub(UTubID);
  });

  $("#modalSubmit").attr({ class: "btn btn-success" }).text(buttonTextSubmit);
  $("#modalSubmit").off("click");
  $("#modalSubmit").on("click", function (e) {
    e.preventDefault();
    $("#confirmModal").modal("hide");
    mode ? addUTub() : editUTub();
  });

  $("#confirmModal").modal("show");
}

/* Delete UTub */

// Show confirmation modal for deletion of the current UTub
function deleteUTubShowModal() {
  let modalTitle = "Are you sure you want to delete this UTub?";
  $(".modal-title").text(modalTitle);

  let modalBody =
    "This action will remove all URLs in UTub and is irreverisible!";
  $(".modal-body").text(modalBody);

  $("#modalDismiss").on("click", function (e) {
    e.preventDefault();
    $("#confirmModal").modal("hide");
  });

  $("#modalSubmit").on("click", function (e) {
    e.preventDefault();
    deleteUTub();
  });

  $("#confirmModal").modal("show");
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
}

// Prepares post request inputs to delete the current UTub
function deleteUTubSetup() {
  let postURL = ROUTE_DELETE_UTUB + currentUTubID();

  return postURL;
}

function deleteUTubSuccess() {
  // Close modal
  $("#confirmModal").modal("hide");

  // Update UTub Deck
  let UTubSelector = $("input[utubid=" + currentUTubID() + "]").parent();
  UTubSelector.fadeOut();
  UTubSelector.remove();

  // Update UTub center panel
  $("#URLDeckHeader")[0].innerHTML = "Select a UTub";

  hideIfShown($("#editUTubButton"));
  hideIfShown($("#addURLBtn"));
  hideIfShown($("#UTubDescription"));
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
    "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
  );
  console.log("Error: " + error.Error_code);
}

/* Add UTub */

// Shows new UTub input fields
function addUTubShowInput() {
  showInput("createUTub");
  highlightInput($("#createUTub"));
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
      addUTubSuccess(response);
    }
  });

  request.fail(function (response, textStatus, xhr) {
    console.log("failed");

    addUTubFail(response, textStatus, xhr);
  });
}

// Handles preparation for post request to create a new UTub
function addUTubSetup() {
  let newUTubName = $("#createUTub").val();
  data = { name: newUTubName };

  return [ROUTE_ADD_UTUB, data];
}

// DP 09/17/23 should work, can't figure its failure
// Handle creation of new UTub
function addUTubSuccess(response) {
  resetNewUTUbForm();

  if (!isHidden($("#confirmModal")[0])) $("#confirmModal").modal("hide");

  let createUTub = $("#createUTub").closest(".createDiv").detach();
  let index = Number($(".UTub").last().attr("position"))
    ? Number($(".UTub").last().attr("position"))
    : 0;
  let nextIndex = index + 1;

  $("#listUTubs").append(
    createUTubSelector(response.UTub_name, response.UTub_ID, nextIndex),
  );
  // Reorder createDiv after latest created UTub selector
  $("#listUTubs").append(createUTub);
}

function addUTubFail(response, textStatus, xhr) {
  console.log("Error: Could not create UTub");
  console.log(response);
  console.log(response.responseJSON.Error_code);

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
    "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
  );
}

/* Edit UTub */

// Shows input fields for editing an exiting UTub's name and description
function editUTubShowInput() {
  // Hide exisitng values and edit button
  hideIfShown($("#URLDeckHeader"));
  hideIfShown($("#UTubDescription"));
  hideIfShown($("#editUTubButton"));
  hideIfShown($("#addURLBtn"));

  // Show temporary div element containing UTub description
  showInput("editUTubDescription");

  // Show temporary div element containing UTub name
  showInput("editUTubName");
}

// Shows input fields for editing an exiting UTub's name and description
function editUTubHideInput() {
  // Hide exisitng values and edit button
  showIfHidden($("#URLDeckHeader"));
  showIfHidden($("#UTubDescription"));
  showIfHidden($("#editUTubButton"));
  showIfHidden($("#addURLBtn"));

  // Show temporary div element containing UTub description
  hideInput("editUTubDescription");

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
  let postURL = ROUTE_EDIT_UTUB_NAME + currentUTubID();

  let editedUTubName = $("#editUTubName").val();
  data = { name: editedUTubName };

  return [postURL, data];
}

// Handles preparation for post request to edit an existing UTub
function editUTubDescriptionSetup() {
  let postURL = ROUTE_EDIT_UTUB_DESCRIPTION + currentUTubID();

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
    "Failure. Status code: " + xhr.status + ". Status: " + textStatus,
  );
}
