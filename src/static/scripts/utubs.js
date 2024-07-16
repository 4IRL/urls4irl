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
    getAllUTubs().then((utubData) => {
      buildUTubDeck(utubData);
      setMemberDeckWhenNoUTubSelected();
      setTagDeckSubheaderWhenNoUTubSelected();
    });
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
function setCreateDeleteUTubEventListeners() {
  const utubBtnCreate = $("#utubBtnCreate");
  const utubBtnDelete = $("#utubBtnDelete");

  // Create new UTub
  utubBtnCreate.offAndOn("click.createDeleteUTub", function () {
    createUTubShowInput();
  });

  // Allows user to press enter to bring up form while focusing on the add UTub icon, esp after tabbing
  utubBtnCreate.offAndOn("focus.createDeleteUTub", function () {
    $(document).offAndOn("keyup.createDeleteUTub", function (e) {
      if (e.which === 13) {
        e.stopPropagation();
        createUTubShowInput();
      }
    });
  });

  // Removes the keyup listener from the document once the button is blurred
  utubBtnCreate.offAndOn("blur.createDeleteUTub", function () {
    $(document).off("keyup.createDeleteUTub");
  });

  // Delete UTub
  utubBtnDelete.offAndOn("click.createDeleteUTub", function () {
    deleteUTubShowModal();
  });

  // Allows user to press enter to bring up form while focusing on the delete UTub icon, esp after tabbing
  utubBtnDelete.offAndOn("focus.createDeleteUTub", function () {
    $(document).offAndOn("keyup.createDeleteUTub", function (e) {
      if (e.which === 13) {
        e.stopPropagation();
        deleteUTubShowModal();
      }
    });
  });

  // Removes the keyup listener from the document once the button is blurred
  utubBtnDelete.offAndOn("blur.createDeleteUTub", function () {
    $(document).off("keyup.createDeleteUTub");
  });
}

// Remove event listeners for add and delete UTubs
function removeCreateDeleteUTubEventListeners() {
  $(document).off(".createDeleteUTub");
}

// Clear the UTub Deck
function resetUTubDeck() {
  $("#listUTubs").empty();
}

// Create event listeners to escape from updating UTub name
function setEventListenersToEscapeUpdateUTubName() {
  // Allow user to still click in the text box
  $("#utubNameUpdate").offAndOn("click.updateUTubname", function (e) {
    e.stopPropagation();
  });

  // Bind clicking outside the window
  $(window).offAndOn("click.updateUTubname", function () {
    // Hide UTub name update fields
    updateUTubNameHideInput();
  });

  // Bind escape and enter key
  $(document).on("keyup.updateUTubname", function (e) {
    switch (e.which) {
      case 13:
        // Handle enter key pressed
        // Skip if update is identical
        if ($("#URLDeckHeader").text() === $("#utubNameUpdate").val()) {
          updateUTubNameHideInput();
          return;
        }
        checkSameNameUTub(false, $("#utubNameUpdate").val());
        break;
      case 27:
        // Handle escape key pressed
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

// Create event listeners to escape from updating UTub name
function setEventListenersToEscapeUpdateUTubDescription() {
  // Allow user to still click in the text box
  $("#utubDescriptionUpdate").on("click.updateUTubDescription", function (e) {
    e.stopPropagation();
  });

  // Bind clicking outside the window
  $(window).offAndOn("click.updateUTubDescription", function (e) {
    // Hide UTub description update fields
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

function allowUserToCreateDescriptionIfEmptyOnTitleUpdate() {
  const clickToCreateDesc = $("#URLDeckSubheaderCreateDescription");
  showIfHidden(clickToCreateDesc);
  clickToCreateDesc.offAndOn("click.createUTubdescription", function (e) {
    e.stopPropagation();
    hideIfShown(clickToCreateDesc);
    updateUTubNameHideInput();
    updateUTubDescriptionShowInput();
    clickToCreateDesc.off("click.createUTubdescription");
  });
}

/** UTub Functions **/

// Assembles components of the UTubDeck (top left panel)
function buildUTubDeck(UTubs) {
  resetUTubDeck();
  const parent = $("#listUTubs");
  const numOfUTubs = UTubs.length;

  if (numOfUTubs !== 0) {
    // Instantiate deck with list of UTubs accessible to current user
    for (let i = 0; i < numOfUTubs; i++) {
      parent.append(createUTubSelector(UTubs[i].name, UTubs[i].id, i));
    }

    displayState1UTubDeck(null, null);
    setURLDeckWhenNoUTubSelected();
  } else resetUTubDeckIfNoUTubs();
}

function buildSelectedUTub(selectedUTub) {
  // Parse incoming data, pass them into subsequent functions as required
  const UTubName = selectedUTub.name;
  const dictURLs = selectedUTub.urls;
  const dictTags = selectedUTub.tags;
  const dictMembers = selectedUTub.members;
  const UTubOwnerID = selectedUTub.createdByUserID;
  const UTubDescription = selectedUTub.description;
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

  // Only allow owner to update UTub name and description
  if (isCurrentUserOwner) {
    $("#utubNameBtnUpdate").removeClass("hiddenBtn").addClass("visibleBtn");
    $("#updateUTubDescriptionBtn")
      .removeClass("hiddenBtn")
      .addClass("visibleBtn");

    // Setup description update field to match the current header
    $("#utubDescriptionUpdate").val($("#URLDeckSubheader").text());
  } else {
    $("#utubNameBtnUpdate").addClass("hiddenBtn").removeClass("visibleBtn");
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

// Handles updating a UTub if found to include stale data
// For example, a user decides to update a URL string to a new URL, but it returns
// saying the URL already exists in the UTub -> yet the user does not see the URL in the UTub?
// This means another user has updated a URL or added a URL with the new URL string, in which
// we should reload the user's UTub to show them the latest data
async function updateUTubOnFindingStaleData(selectedUTubID) {
  const utub = await getUTubInfo(selectedUTubID);
  const utubName = utub.name;
  const utubDescription = utub.description;
  updateUTubNameAndDescription(utub.id, utubName, utubDescription);

  // Update Tags
  const utubTags = utub.tags;
  updateTagDeck(utubTags);

  // Update URLs
  const utubURLs = utub.urls;
  updateURLDeck(utubURLs, utubTags);

  // Update members
  const utubMembers = utub.members;
  const utubOwnerID = utub.createdByUserID;
  const isCurrentUserOwner = utub.isCreator;
  updateMemberDeck(utubMembers, utubOwnerID, isCurrentUserOwner);

  // Update filtering
  updateTagFilteringOnFindingStaleData();
}

function updateUTubNameAndDescription(utubID, utubName, utubDescription) {
  const utubNameElem = $("#URLDeckHeader");
  const utubNameInUTubDeckElem = $(
    "UTubSelector[utubid=" + utubID + "] > .UTubName",
  );
  const utubDescriptionElem = $("#URLDeckSubheader");

  if (utubNameElem.text() !== utubName) {
    utubNameElem.text(utubName);
    utubNameInUTubDeckElem.text(utubName);
  }

  utubDescriptionElem.text() !== utubDescription
    ? utubDescriptionElem.text(utubDescription)
    : null;
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
  const utubSubmitBtnCreate = $("#utubSubmitBtnCreate");
  const utubCancelBtnCreate = $("#utubCancelBtnCreate");
  utubSubmitBtnCreate.offAndOn("click.createUTub", function (e) {
    if ($(e.target).closest("#utubSubmitBtnCreate").length > 0)
      checkSameNameUTub(true, $("#utubNameCreate").val());
  });

  utubCancelBtnCreate.offAndOn("click.createUTub", function (e) {
    if ($(e.target).closest("#utubCancelBtnCreate").length > 0)
      createUTubHideInput();
  });

  utubSubmitBtnCreate.offAndOn("focus.createUTub", function () {
    $(document).offAndOn("keyup.createUTubSubmit", function (e) {
      if (e.which === 13) checkSameNameUTub(true, $("#utubNameCreate").val());
    });
  });

  utubSubmitBtnCreate.offAndOn("blur.createUTub", function () {
    $(document).off("keyup.createUTubSubmit");
  });

  utubCancelBtnCreate.offAndOn("focus.createUTub", function () {
    $(document).offAndOn("keyup.createUTubCancel", function (e) {
      if (e.which === 13) createUTubHideInput();
    });
  });

  utubCancelBtnCreate.on("blur.createUTub", function () {
    $(document).off("keyup.createUTubCancel");
  });

  const utubNameInput = $("#utubNameCreate");
  const utubDescriptionInput = $("#utubDescriptionCreate");

  utubNameInput.on("focus.createUTub", function () {
    $(document).on("keyup.createUTubName", function (e) {
      handleOnFocusEventListenersForCreateUTub(e);
    });
  });

  utubNameInput.on("blur.createUTub", function () {
    $(document).off(".createUTubName");
  });

  utubDescriptionInput.on("focus.createUTub", function () {
    $(document).on("keyup.createUTubDescription", function (e) {
      handleOnFocusEventListenersForCreateUTub(e);
    });
  });

  utubDescriptionInput.on("blur.createUTub", function () {
    $(document).off(".createUTubDescription");
  });
}

function removeNewUTubEventListeners() {
  $(document).off("keyup.createUTubName");
  $(document).off("keyup.createUTubDescription");
  $(document).off("keyup.createUTubCancel");
  $(document).off("keyup.createUTubSubmit");
  $("#utubNameCreate").off(".createUTub");
  $("#utubDescriptionCreate").off(".createUTub");
  $("#utubSubmitBtnCreate").off(".createUTub");
  $("#utubCancelBtnCreate").off(".createUTub");
}

function handleOnFocusEventListenersForCreateUTub(e) {
  switch (e.which) {
    case 13:
      // Handle enter key pressed
      checkSameNameUTub(true, $("#utubNameCreate").val());
      break;
    case 27:
      // Handle escape key pressed
      $("#utubNameCreate").trigger("blur");
      $("#utubDescriptionCreate").trigger("blur");
      createUTubHideInput();
      break;
    default:
    /* no-op */
  }
}

function unbindCreateUTubFocusEventListeners() {}

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
function resetUTubDeckIfNoUTubs() {
  // Subheader to prompt user to create a UTub shown
  $("#UTubDeckSubheader").text("Create a UTub");

  // Hide delete UTub button
  hideIfShown($("#utubBtnDelete"));
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
    showIfHidden($("#utubBtnDelete"));
  } else hideIfShown($("#utubBtnDelete"));
}

/** Post data handling **/

// Checks if submitted UTub name exists in db. mode is 0 for updateUTub, 1 for createUTub
function checkSameNameUTub(isCreatingUTub, name) {
  if (getAllAccessibleUTubNames().includes(name)) {
    // UTub with same name exists. Confirm action with user
    isCreatingUTub
      ? sameUTubNameOnNewUTubWarningShowModal()
      : sameUTubNameOnUpdateUTubNameWarningShowModal();
  } else {
    // UTub name is unique. Proceed with requested action
    isCreatingUTub ? createUTub() : updateUTubName();
  }
}

// Hides modal for UTub same name action confirmation
function sameNameWarningHideModal() {
  $("#confirmModal").modal("hide");
}

// Handles a double check if user inputs a new UTub name similar to one already existing. mode true 'add', mode false 'update'
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
    .offAndOn("click", function (e) {
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
    .offAndOn("click", function (e) {
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
    .offAndOn("click", function (e) {
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
    .offAndOn("click", function (e) {
      e.preventDefault();
      updateUTubName();
    });

  $("#confirmModal").modal("show");
  $("#confirmModal").on("hidden.bs.modal", function (e) {
    e.stopPropagation();
    setEventListenersToEscapeUpdateUTubName();
  });
}
