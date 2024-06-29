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
});

window.addEventListener("popstate", function (e) {
  if (e.state && e.state.hasOwnProperty("UTub")) {
    // State will contain property UTub if URL contains query parameter UTubID
    buildSelectedUTub(e.state.UTub);
  } else {
    // If does not contain query parameter, user is at /home - then update UTub titles/IDs
    displayState0();
    getAllUTubs().then((utubData) => buildUTubDeck(utubData));
  }
});

/** UTub Utility Functions **/

// Function to count number of UTubs current user has access to
function getNumOfUTubs() {
  return $("#listUTubs > .UTubSelector").length;
}

// Streamline the jQuery selector extraction of UTub ID. And makes it easier in case the ID is encoded in a new location in the future
function getActiveUTubID() {
  return parseInt($(".UTubSelector.active").attr("utubid"));
}

// Streamline the jQuery selector for the UTub Selector.
function getUTubSelectorElemFromID(id) {
  return $(".UTubSelector[utubid='" + id + "']");
}

// Streamline the extraction of a UTub array element from its ID
function getUTubObjFromID(id) {
  $(".UTubSelector").forEach(function (UTub) {
    if (UTub.attr("utubid") === id) return UTub;
  });

  return -1;
}

// Streamline the jQuery selector extraction of UTub ID. And makes it easier in case the ID is encoded in a new location in the future
function getUTubIDFromName(name) {
  const UTubNames = $(".UTubName");
  let UTub;

  console.log(UTubNames.length);
  for (i = 0; i < UTubNames.length; i++) {
    UTub = $(UTubNames[i]);

    if (UTub.text() === name) {
      return parseInt(UTub.closest(".UTubSelector").attr("utubid"));
    }
  }

  return -1;
}

// Streamline the jQuery selector extraction of UTub name.
function getCurrentUTubName() {
  return $(".UTubSelector.active").text();
}

// Quickly extracts all UTub names from #listUTubs and returns an array.
function getAllAccessibleUTubNames() {
  let UTubNames = [];
  let UTubSelectorNames = $(".UTubName");
  UTubSelectorNames.map((i) => UTubNames.push($(UTubSelectorNames[i]).text()));
  return UTubNames;
}

// Streamline the AJAX call to db for updated info
function getUTubInfo(selectedUTubID) {
  return $.getJSON("/home?UTubID=" + selectedUTubID);
}

// Utility route to get all UTub summaries
function getAllUTubs() {
  return $.getJSON("/utubs");
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

// Create event listeners to escape from editing UTub name
function setEventListenersToEscapeEditUTubName() {
  console.log("Setting up event listeners for edit UTub name!");

  // Allow user to still click in the text box
  $("#editUTubName").on("click", function (e) {
    e.stopPropagation();
  });

  // Bind clicking outside the window
  $(window)
    .off("click")
    .on("click", function () {
      // Hide UTub name edit fields
      console.log("Hiding the inputs");
      editUTubNameHideInput();
    });

  // Bind escape key
  $(document).bind("keyup.27", function (e) {
    if (e.which === 27) {
      hideInputs();
      console.log("Hiding the inputs");
      editUTubNameHideInput();
    }
  });
}

function removeEventListenersToEscapeEditUTubName() {
  console.log("Removing event listeners for edit UTub name!");
  $(window).off("click");
  $(document).unbind("keyup.27");
  $("#editUTubName").off("click");
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

function buildSelectedUTub(selectedUTub) {
  // Parse incoming data, pass them into subsequent functions as required
  let UTubName = selectedUTub.name;
  let dictURLs = selectedUTub.urls;
  let dictTags = selectedUTub.tags;
  let dictMembers = selectedUTub.members;
  let UTubOwnerID = selectedUTub.createdByUserID;
  let UTubDescription = selectedUTub.description;
  const isCurrentUserOwner = selectedUTub.isCreator;

  const isUTubHistoryNull = window.history.state === null;

  // Allow user to back and forth in browser based on given UTub selection
  if (
    isUTubHistoryNull ||
    JSON.stringify(window.history.state.UTub) !== JSON.stringify(selectedUTub)
  ) {
    // Push UTub state to browser history if no history, or if previous UTub history is different
    window.history.pushState(
      { UTub: selectedUTub },
      "UTub History",
      "/home?UTubID=" + selectedUTub.id,
    );
  }

  // LH panels
  // UTub deck
  displayState1UTubDeck(selectedUTub.id, UTubOwnerID);

  // Tag deck
  buildTagDeck(dictTags);

  // Center panel
  // URL deck
  buildURLDeck(UTubName, dictURLs, dictTags);

  // UTub Description
  if (UTubDescription) displayState2UTubDescriptionDeck(UTubDescription);
  else displayState1UTubDescriptionDeck();

  // Members deck
  buildMemberDeck(dictMembers, UTubOwnerID, isCurrentUserOwner);

  // Only allow owner to edit UTub name
  isCurrentUserOwner
    ? showIfHidden($("#editUTubNameBtn"))
    : hideIfShown($("#editUTubNameBtn"));
}

// Handles progagating changes across page related to a UTub selection
function selectUTub(selectedUTubID) {
  getUTubInfo(selectedUTubID).then((selectedUTub) =>
    buildSelectedUTub(selectedUTub),
  );
}

// Creates UTub radio button that changes URLDeck display to show contents of the selected UTub
function createUTubSelector(UTubName, UTubID, index) {
  let UTubSelector = document.createElement("div");
  let UTubSelectorText = document.createElement("b");

  $(UTubSelectorText).addClass("UTubName").text(UTubName);

  $(UTubSelector)
    .addClass("UTubSelector")
    .attr({
      utubid: UTubID,
      position: index,
    })
    // Bind display state change function on click
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      selectUTub(UTubID);
    })
    .append(UTubSelectorText);

  return UTubSelector;
}

// Creates a typically hidden input text field. When creation of a new UTub is requested, it is shown to the user. Input field recreated here to ensure at the end of list after creation of new UTubs
function createNewUTubInputField() {
  const wrapper = document.createElement("div");
  const wrapperInput = document.createElement("div");
  const wrapperBtns = document.createElement("div");

  const input = document.createElement("input");
  const submitBtn = makeSubmitButton(30);
  const cancelBtn = makeCancelButton(30);

  $(wrapper).addClass("createDiv flex-row").attr({ style: "display: none" });

  $(wrapperInput).addClass("col-9 col-lg-9 mb-md-0");

  $(input).addClass("userInput").attr({
    type: "text",
    id: "createUTub",
    placeholder: "New UTub name",
  });

  $(wrapperBtns).addClass("col-3 mb-md-0 flex-row-reverse");

  $(submitBtn)
    .addClass("mx-1 green-clickable")
    .attr({
      id: "submitCreateUTub",
    })
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      checkSameNameUTub(true, $("#createUTub").val());
    });

  $(cancelBtn)
    .addClass("mx-1")
    .attr({
      id: "cancelCreateUTub",
    })
    .on("click", function (e) {
      e.stopPropagation();
      e.preventDefault();
      hideIfShown($(wrapper));
    });

  $(wrapperInput).append(input);

  $(wrapperBtns).append(cancelBtn).append(submitBtn);

  $(wrapper).append(wrapperInput).append(wrapperBtns);

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
function displayState1UTubDeck(selectedUTubID, UTubOwnerUserID) {
  hideInputs();
  const numOfUTubs = getNumOfUTubs();
  const subheaderText =
    numOfUTubs > 1 ? numOfUTubs + " UTubs" : numOfUTubs + " UTub";

  // Subheader to tell user how many UTubs are accessible
  $("#UTubDeckSubheader").text(subheaderText);

  // UTub selected

  // Bind selection behavior to depature UTub, unbind from selected UTub
  bindUTubSelectionBehavior();
  if (selectedUTubID) {
    unbindUTubSelectionBehavior(selectedUTubID);
    showIfHidden($("#editUTubDescriptionBtn"));
  }

  if (getCurrentUserID() === UTubOwnerUserID) {
    showIfHidden($("#deleteUTubBtn"));
  } else hideIfShown($("#deleteUTubBtn"));
}

/** UTub Description Display State Functions **/

// Display state 0: Clean slate, no UTub selected
function displayState0UTubDescriptionDeck() {
  // Subheader prompt hidden
  hideIfShown($("#UTubDescriptionDeckSubheader").closest(".titleElement"));

  // Edit UTub Description button hidden
  hideIfShown($("#editUTubDescriptionBtn"));

  // Clear description values
  $("#UTubDescription").text("");
  $("#editUTubDescription").val("");
}

// Display state 1: UTub selected, no description
function displayState1UTubDescriptionDeck() {
  // Subheader prompt shown
  showIfHidden($("#UTubDescriptionDeckSubheader").closest(".titleElement"));

  // Edit UTub Description button shown, submission button hidden
  showIfHidden($("#editUTubDescriptionBtn"));
  hideIfShown($("#submitEditUTubDescriptionBtn"));

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
  const UTubDescriptionHolder = $("#URLDeckSubheader");
  if (UTubDescription) {
    showIfHidden(UTubDescriptionHolder);
    UTubDescriptionHolder.text(UTubDescription);
  } // User edited description to empty string
  else hideIfShown(UTubDescriptionHolder);
}

// Display state 3: UTub selected, edit active
function displayState3UTubDescriptionDeck(UTubDescription) {
  // Subheader prompt hidden
  hideIfShown($("#UTubDescriptionDeckSubheader").closest(".titleElement"));

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
function checkSameNameUTub(isAddingUTub, name) {
  if (getAllAccessibleUTubNames().includes(name)) {
    // UTub with same name exists. Confirm action with user
    const duplicateUTubIDFromName = getUTubIDFromName(name);
    isAddingUTub
      ? sameUTubNameOnNewUTubWarningShowModal(duplicateUTubIDFromName)
      : sameUTubNameOnEditUtubNameWarningShowModal(duplicateUTubIDFromName);
  } else {
    // UTub name is unique. Proceed with requested action
    isAddingUTub ? addUTub() : editUTubName();
  }
}

// Hides modal for UTub same name action confirmation
function sameNameWarningHideModal() {
  $("#confirmModal").modal("hide");
}

// Handles a double check if user inputs a new UTub name similar to one already existing. mode true 'add', mode false 'edit'
function sameUTubNameOnNewUTubWarningShowModal(UTubID) {
  const modalTitle = "Create a new UTub with this name?";
  const modalBody = "A UTub in your repository has an identical name.";
  const buttonTextDismiss = "Go Back to Editing";
  const buttonTextRedirect = "Go to UTub";
  const buttonTextSubmit = "Create";

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-secondary")
    .text(buttonTextDismiss)
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      sameNameWarningHideModal();
      highlightInput($("#createUTub"));
    });

  showIfHidden($("#modalRedirect"));
  $("#modalRedirect")
    .addClass("btn btn-primary")
    .text(buttonTextRedirect)
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      $("#confirmModal").modal("hide");
      addUTubHideInput();
      selectUTub(UTubID);
    });

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      addUTub();
      hideIfShown($("#modalRedirect"));
      $("#modalRedirect").hide();
    });

  $("#confirmModal").modal("show");
}

function sameUTubNameOnEditUtubNameWarningShowModal(UTubID) {
  const modalTitle = "Edit this UTub name?";
  const modalBody = "A UTub in your repository has an identical name.";
  const buttonTextDismiss = "Go Back to Editing";
  const buttonTextRedirect = "Go to UTub";
  const buttonTextSubmit = "Edit Name";

  removeEventListenersToEscapeEditUTubName();

  $("#confirmModalTitle").text(modalTitle);

  $("#confirmModalBody").text(modalBody);

  $("#modalDismiss")
    .addClass("btn btn-secondary")
    .text(buttonTextDismiss)
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      e.stopPropagation();
      sameNameWarningHideModal();
      highlightInput($("#editUTubName"));
      setEventListenersToEscapeEditUTubName();
    });

  showIfHidden($("#modalRedirect"));
  $("#modalRedirect")
    .addClass("btn btn-primary")
    .text(buttonTextRedirect)
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      $("#confirmModal").modal("hide");
      editUTubNameHideInput();
      selectUTub(UTubID);
    });

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      editUTubName();
      hideIfShown($("#modalRedirect"));
      $("#modalRedirect").hide();
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").on("hidden.bs.modal", function (e) {
    e.stopPropagation();
    setEventListenersToEscapeEditUTubName();
  });
}
