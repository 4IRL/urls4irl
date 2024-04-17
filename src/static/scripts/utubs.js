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
    editUTubNameShowInput();
  });

  $("#submitEditUTubNameBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    checkSameNameUTub(0, $("#editUTubName").val());
  });

  // Edit UTub description
  $("#editUTubDescriptionBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    editUTubDescriptionShowInput();
  });

  $("#submitEditUTubDescriptionBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    editUTubDescriptionShowInput();
  });

  $("#submitEditUTubDescriptionBtn").on("click", function (e) {
    // e.stopPropagation();
    // e.preventDefault();
    editUTubDescription();
  });
});

/** UTub Utility Functions **/

// Function to count number of UTubs current user has access to
function getNumOfUTubs() {
  return $("#listUTubs > .UTub").length;
}

// Function to count number of UTubs current user has access to
function getNumOfUTubs() {
  return $("#listUTubs > .UTub").length;
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

  $(name)
    .addClass("UTubName")
    .text(UTubName);

  $(label)
    .attr({ for: "UTub-" + UTubID });

  $(radio)
    .attr({
      type: "radio",
      id: "UTub-" + UTubID,
      value: UTubName,
    });

  $(container)
  .append(name)
  .append(label)
  .append(radio);

  return container;
}

// Creates a typically hidden input text field. When creation of a new UTub is requested, it is shown to the user. Input field recreated here to ensure at the end of list after creation of new UTubs
function createNewUTubInputField() {
  const wrapper = document.createElement("div");
  const wrapperInput = document.createElement("div");
  const wrapperBtns = document.createElement("div");

  const input = document.createElement("input");
  const submitBtn = makeSubmitButton(30);
  const cancelBtn = makeCancelButton(30);

  $(wrapper).
    addClass("createDiv row")
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

  $(wrapperBtns)
    .addClass("col-3 mb-md-0 text-right d-flex justify-content-center flex-row");

  $(submitBtn)
    .addClass("mx-1 green-clickable submitCreateUTub")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      checkSameNameUTub(1, $("#createUTub").val());
    });

  $(cancelBtn)
    .addClass("mx-1 cancelCreateUTub")
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      hideIfShown(wrapper);
    });

  $(wrapperInput)
    .append(input);

  $(wrapperBtns)
    .append(submitBtn)
    .append(cancelBtn);

  $(wrapper)
    .append(wrapperInput)
    .append(wrapperBtns);

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

  console.log(getCurrentUserID())
  console.log(UTubOwnerID)

  if (getCurrentUserID() === UTubOwnerID) {
    showIfHidden($("#deleteUTubBtn"));
  } else hideIfShown($("#deleteUTubBtn"));
}

/** UTub Description Display State Functions **/

// Display state 0: Clean slate, no UTub selected
function displayState0UTubDescriptionDeck() {
  // Subheader prompt hidden
  hideIfShown($("#UTubDescriptionDeckSubheader").closest(".row"));

  // Edit UTub Description button hidden
  hideIfShown($("#editUTubDescriptionBtn"));

  // Clear description values
  $("#UTubDescription").text("");
  $("#editUTubDescription").val("");
}

// Display state 1: UTub selected, no description
function displayState1UTubDescriptionDeck() {
  // Subheader prompt shown
  showIfHidden($("#UTubDescriptionDeckSubheader").closest(".row"));

  // Edit UTub Description button shown
  showIfHidden($("#editUTubDescriptionBtn"));

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
    editUTubDescriptionHideInput();

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
  hideIfShown($("#editUTubDescriptionBtn"));
  showIfHidden($("#submitEditUTubDescriptionBtn"));

  // Update description values
  let editUTubDescription = $("#editUTubDescription");
  hideIfShown(editUTubDescription.closest(".createDiv"));
  editUTubDescription.val(UTubDescription);
}

/** Post data handling **/

// Checks if submitted UTub name exists in db. mode is 0 for editUTub, 1 for addUTub
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
  // If editUTub, ignore one instance of names
  if (!mode) sameNameCounter -= 1;

  if (sameNameCounter > 0)
    sameNameWarningShowModal(mode, getUTubIDFromName(name));
  else mode ? addUTub() : editUTubName();
  if (sameNameCounter > 0)
    sameNameWarningShowModal(mode, getUTubIDFromName(name));
  else mode ? addUTub() : editUTubName();
}

// Counts number of UTubs with the same name
// DP 10/22 When I add/delete UTubs, I get a response for the single UTub information. But this doesn't give me updated information about the aggregate of the user's UTubs. This check for the same name requires a loop variable. Is it best to recount based on #listUTubs?
// DP 10/22 When I edit UTubs, I get a response for the single UTub information. But this doesn't give me updated information about the aggregate of the user's UTubs. This check does not catch if user changes two UTubs to a third similar name. Ex. UTub1 --> UTub3, UTub2 --> UTub3, should throw error but does not. Is it best to recount based on #listUTubs?
// Need to implement: check UTubID AND name to circumvent inadvertent error thrown when no edit has been made
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
      displayState1UTubDeck(UTubID, getCurrentUTubCreatorID());
    });

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      mode ? addUTub() : editUTubName();
      mode ? addUTub() : editUTubName();
    });
  // bindKeyToFunction(removeURL, 13);
  // 01/03/24 may want to separate sameNameWarningShowModal for add and edit

  $("#confirmModal").modal("show");
}
