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
    console.log("Display state 0");
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

// Set event listeners for add and delete UTubs
function setAddDeleteUTubEventListeners() {
  // Create new UTub
  $("#createUTubBtn")
    .off("click.addDeleteUTub")
    .on("click.addDeleteUTub", function () {
      hideInputs();
      deselectAllURLs();
      addUTubShowInput();
    });

  // Delete UTub
  $("#deleteUTubBtn")
    .off("click.addDeleteUTub")
    .on("click.addDeleteUTub", function () {
      deleteUTubShowModal();
    });
}

// Remove event listeners for add and delete UTubs
function removeAddDeleteUTubEventListeners() {
  $(document).off(".addDeleteUTub");
}

// Clear the UTub Deck
function resetUTubDeck() {
  $("#listUTubs").empty();
}

// Create event listeners to escape from editing UTub name
function setEventListenersToEscapeEditUTubName() {
  // Allow user to still click in the text box
  $(".edit#utubName")
    .off("click.editUTubname")
    .on("click.editUTubname", function (e) {
      e.stopPropagation();
    });

  // Bind clicking outside the window
  $(window)
    .off("click.editUTubname")
    .on("click.editUTubname", function () {
      // Hide UTub name edit fields
      editUTubNameHideInput();
    });

  // Bind escape and enter key
  $(document).bind("keyup.editUTubname", function (e) {
    switch (e.which) {
      case 13:
        // Handle enter key pressed
        // Skip if edit is identical
        if ($("#URLDeckHeader").text() === $(".edit#utubName").val()) {
          editUTubNameHideInput();
          return;
        }
        checkSameNameUTub(false, $(".edit#utubName").val());
        break;
      case 27:
        // Handle escape key pressed
        hideInputs();
        editUTubNameHideInput();
        break;
      default:
      /* no-op */
    }
  });
}

function removeEventListenersToEscapeEditUTubName() {
  $(window).off(".editUTubname");
  $(document).off(".editUTubname");
}

// Create event listeners to escape from editing UTub name
function setEventListenersToEscapeEditUTubDescription() {
  // Allow user to still click in the text box
  $(".edit#utubDescription").on("click.editUTubdescription", function (e) {
    e.stopPropagation();
  });

  // Bind clicking outside the window
  $(window)
    .off("click.editUTubdescription")
    .on("click.editUTubdescription", function (e) {
      // Hide UTub description edit fields
      editUTubDescriptionHideInput();
    });

  // Bind escape key
  $(document).bind("keyup.editUTubdescription", function (e) {
    switch (e.which) {
      case 13:
        // Handle enter key pressed
        editUTubDescription();
        break;
      case 27:
        // Handle escape key pressed
        hideInputs();
        editUTubDescriptionHideInput();
        break;
      default:
      /* no-op */
    }
  });
}

function removeEventListenersToEscapeEditUTubDescription() {
  $(window).off("click.editUTubdescription");
  $(document).off("keyup.editUTubdescription");
  $(".edit#utubDescription").off("click.editUTubdescription");
}

function allowUserToAddDescriptionIfEmptyOnTitleEdit() {
  const clickToAddDesc = $("#URLDeckSubheaderAddDescription");
  showIfHidden(clickToAddDesc);
  clickToAddDesc
    .off("click.addUTubdescription")
    .on("click.addUTubdescription", function (e) {
      e.stopPropagation();
      hideIfShown(clickToAddDesc);
      editUTubNameHideInput();
      editUTubDescriptionShowInput();
      clickToAddDesc.off("click.addUTubdescription");
    });
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
  const utubDescriptionHeader = $("#URLDeckSubheader");
  if (UTubDescription) {
    utubDescriptionHeader.text(UTubDescription);
  } else {
    utubDescriptionHeader.text(null);
  }

  // Members deck
  buildMemberDeck(dictMembers, UTubOwnerID, isCurrentUserOwner);

  // Only allow owner to edit UTub name and description
  if (isCurrentUserOwner) {
    $("#editUTubNameBtn").removeClass("hiddenBtn").addClass("visibleBtn");
    $("#editUTubDescriptionBtn")
      .removeClass("hiddenBtn")
      .addClass("visibleBtn");

    // Setup description edit field to match the current header
    $(".edit#utubDescription").val($("#URLDeckSubheader").text());
  } else {
    $("#editUTubNameBtn").addClass("hiddenBtn").removeClass("visibleBtn");
    $("#editUTubDescriptionBtn")
      .addClass("hiddenBtn")
      .removeClass("visibleBtn");
  }
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
    .on("click.selectUTub", function (e) {
      e.stopPropagation();
      e.preventDefault();
      selectUTub(UTubID);
    })
    .append(UTubSelectorText);

  return UTubSelector;
}

// Attaches appropriate event listeners to the add UTub and cancel add UTub buttons
function createNewUTubEventListeners() {
  $("#submitCreateUTub")
    .off("click.addUTub")
    .on("click.addUTub", function (e) {
      e.stopPropagation();
      e.preventDefault();
      checkSameNameUTub(true, $("#utubNameCreate").val());
    });

  $("#cancelCreateUTub")
    .off("click.addUTub")
    .on("click.addUTub", function (e) {
      e.stopPropagation();
      e.preventDefault();
      addUTubHideInput();
    });

  $(document)
    .off("keyup.addUTub")
    .on("keyup.addUTub", function (e) {
      switch (e.which) {
        case 13:
          // Handle enter key pressed
          checkSameNameUTub(true, $("#utubNameCreate").val());
          break;
        case 27:
          // Handle escape key pressed
          addUTubHideInput();
          break;
        default:
        /* no-op */
      }
    });
}

function removeNewUTubEventListeners() {
  $(document).off(".addUTub");
}

function unbindUTubSelectionBehavior(selectedUTubID) {
  // Select new UTub
  let selectedUTubSelector = getUTubSelectorElemFromID(selectedUTubID);
  selectedUTubSelector.addClass("active");
  // Unbind selection function
  selectedUTubSelector.off("click.selectUTub");
}

function bindUTubSelectionBehavior() {
  // Unselect any already selected UTub
  let departureUTubSelector = getUTubSelectorElemFromID(getActiveUTubID());
  if (departureUTubSelector) {
    // Change UTub
    departureUTubSelector.removeClass("active");
    // Rebind selection function
    $(departureUTubSelector).on("click.selectUTub", function (e) {
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
    //showIfHidden($("#editUTubDescriptionBtn"));
  }

  if (getCurrentUserID() === UTubOwnerUserID) {
    showIfHidden($("#deleteUTubBtn"));
  } else hideIfShown($("#deleteUTubBtn"));
}

/** Post data handling **/

// Checks if submitted UTub name exists in db. mode is 0 for editUTub, 1 for addUTub
function checkSameNameUTub(isAddingUTub, name) {
  if (getAllAccessibleUTubNames().includes(name)) {
    // UTub with same name exists. Confirm action with user
    isAddingUTub
      ? sameUTubNameOnNewUTubWarningShowModal()
      : sameUTubNameOnEditUtubNameWarningShowModal();
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
function sameUTubNameOnNewUTubWarningShowModal() {
  const modalTitle = "Create a new UTub with this name?";
  const modalBody = "You're already in a UTub with an identical name.";
  const buttonTextDismiss = "Go Back to Editing";
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
      highlightInput($("#utubNameCreate"));
    });

  hideIfShown($("#modalRedirect"));
  $("#modalRedirect").hide();

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      addUTub();
      $("#utubNameCreate").val(null);
      $("#utubDescriptionCreate").val(null);
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").on("hidden.bs.modal", function (e) {
    // Refocus on the name's input box
    highlightInput($("#utubNameCreate"));
  });
}

function sameUTubNameOnEditUtubNameWarningShowModal() {
  const modalTitle = "Edit this UTub name?";
  const modalBody = "You're already in a UTub with an identical name.";
  const buttonTextDismiss = "Go Back to Editing";
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
      highlightInput($(".edit#utubName"));
      setEventListenersToEscapeEditUTubName();
    });

  hideIfShown($("#modalRedirect"));
  $("#modalRedirect").hide();

  $("#modalSubmit")
    .removeClass()
    .addClass("btn btn-success")
    .text(buttonTextSubmit)
    .off("click")
    .on("click", function (e) {
      e.preventDefault();
      editUTubName();
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").on("hidden.bs.modal", function (e) {
    e.stopPropagation();
    setEventListenersToEscapeEditUTubName();
  });
}
