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
      createUTubShowInput();
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
function setEventListenersToEscapeUpdateUTubName() {
  // Allow user to still click in the text box
  $("#utubNameUpdate")
    .off("click.updateUTubname")
    .on("click.updateUTubname", function (e) {
      e.stopPropagation();
    });

  // Bind clicking outside the window
  $(window)
    .off("click.updateUTubname")
    .on("click.updateUTubname", function () {
      // Hide UTub name edit fields
      updateUTubNameHideInput();
    });

  // Bind escape and enter key
  $(document).bind("keyup.updateUTubname", function (e) {
    switch (e.which) {
      case 13:
        // Handle enter key pressed
        // Skip if edit is identical
        if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
          updateUTubNameHideInput();
          return;
        }
        checkSameNameUTub(false, $("#utubNameUpdate").val());
        break;
      case 27:
        // Handle escape key pressed
        hideInputs();
        updateUTubNameHideInput();
        break;
      default:
      /* no-op */
    }
  });
}

function removeEventListenersToEscapeUpdateUTubName() {
  $(window).off(".updateUTubname");
  $(document).off(".updateUTubname");
}

// Create event listeners to escape from editing UTub name
function setEventListenersToEscapeUpdateUTubDescription() {
  // Allow user to still click in the text box
  $("#utubDescriptionUpdate").on("click.updateUTubDescription", function (e) {
    e.stopPropagation();
  });

  // Bind clicking outside the window
  $(window)
    .off("click.updateUTubDescription")
    .on("click.updateUTubDescription", function (e) {
      // Hide UTub description edit fields
      updateUTubDescriptionHideInput();
    });

  // Bind escape key
  $(document).bind("keyup.updateUTubDescription", function (e) {
    switch (e.which) {
      case 13:
        // Handle enter key pressed
        updateUTubDescription();
        break;
      case 27:
        // Handle escape key pressed
        hideInputs();
        updateUTubDescriptionHideInput();
        break;
      default:
      /* no-op */
    }
  });
}

function removeEventListenersToEscapeUpdateUTubDescription() {
  $(window).off(".updateUTubDescription");
  $(document).off(".updateUTubDescription");
}

function allowUserToAddDescriptionIfEmptyOnTitleUpdate() {
  const clickToAddDesc = $("#URLDeckSubheaderAddDescription");
  showIfHidden(clickToAddDesc);
  clickToAddDesc
    .off("click.createUTubdescription")
    .on("click.createUTubdescription", function (e) {
      e.stopPropagation();
      hideIfShown(clickToAddDesc);
      updateUTubNameHideInput();
      updateUTubDescriptionShowInput();
      clickToAddDesc.off("click.createUTubdescription");
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
    $("#UpdateUTubNameBtn").removeClass("hiddenBtn").addClass("visibleBtn");
    $("#updateUTubDescriptionBtn")
      .removeClass("hiddenBtn")
      .addClass("visibleBtn");

    // Setup description edit field to match the current header
    $("#utubDescriptionUpdate").val($("#URLDeckSubheader").text());
  } else {
    $("#UpdateUTubNameBtn").addClass("hiddenBtn").removeClass("visibleBtn");
    $("#updateUTubDescriptionBtn")
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
    .off("click.createUTub")
    .on("click.createUTub", function (e) {
      e.stopPropagation();
      e.preventDefault();
      checkSameNameUTub(true, $("#utubNameCreate").val());
    });

  $("#cancelCreateUTub")
    .off("click.createUTub")
    .on("click.createUTub", function (e) {
      e.stopPropagation();
      e.preventDefault();
      createUTubHideInput();
    });

  $(document)
    .off("keyup.createUTub")
    .on("keyup.createUTub", function (e) {
      switch (e.which) {
        case 13:
          // Handle enter key pressed
          checkSameNameUTub(true, $("#utubNameCreate").val());
          break;
        case 27:
          // Handle escape key pressed
          createUTubHideInput();
          break;
        default:
        /* no-op */
      }
    });
}

function removeNewUTubEventListeners() {
  $(document).off(".createUTub");
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
    //showIfHidden($("#updateUTubDescriptionBtn"));
  }

  if (getCurrentUserID() === UTubOwnerUserID) {
    showIfHidden($("#deleteUTubBtn"));
  } else hideIfShown($("#deleteUTubBtn"));
}

/** Post data handling **/

// Checks if submitted UTub name exists in db. mode is 0 for editUTub, 1 for createUTub
function checkSameNameUTub(isAddingUTub, name) {
  if (getAllAccessibleUTubNames().includes(name)) {
    // UTub with same name exists. Confirm action with user
    isAddingUTub
      ? sameUTubNameOnNewUTubWarningShowModal()
      : sameUTubNameOnUpdateUTubNameWarningShowModal();
  } else {
    // UTub name is unique. Proceed with requested action
    isAddingUTub ? createUTub() : updateUTubName();
  }
}

// Hides modal for UTub same name action confirmation
function sameNameWarningHideModal() {
  $("#confirmModal").modal("hide");
}

// Handles a double check if user inputs a new UTub name similar to one already existing. mode true 'add', mode false 'edit'
function sameUTubNameOnNewUTubWarningShowModal() {
  const modalTitle = "Create a new UTub with this name?";
  const modalBody = "You already have a UTub with a similar name.";
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
      createUTub();
      $("#utubNameCreate").val(null);
      $("#utubDescriptionCreate").val(null);
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").on("hidden.bs.modal", function (e) {
    // Refocus on the name's input box
    highlightInput($("#utubNameCreate"));
  });
}

function sameUTubNameOnUpdateUTubNameWarningShowModal() {
  const modalTitle = "Edit this UTub name?";
  const modalBody = "You're already in a UTub with an identical name.";
  const buttonTextDismiss = "Go Back to Editing";
  const buttonTextSubmit = "Edit Name";

  removeEventListenersToEscapeUpdateUTubName();

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
      highlightInput($("#utubNameUpdate"));
      setEventListenersToEscapeUpdateUTubName();
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
      updateUTubName();
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").on("hidden.bs.modal", function (e) {
    e.stopPropagation();
    setEventListenersToEscapeUpdateUTubName();
  });
}
