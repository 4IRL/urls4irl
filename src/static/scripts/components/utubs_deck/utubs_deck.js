"use strict";

// Utility function to show a loading icon when loading UTubs
function showUTubLoadingIconAndSetTimeout() {
  return setTimeout(function () {
    $("#UTubSelectDualLoadingRing").addClass("dual-loading-ring");
  }, SHOW_LOADING_ICON_AFTER_MS);
}

function hideUTubLoadingIconAndClearTimeout(timeoutID) {
  clearTimeout(timeoutID);
  $("#UTubSelectDualLoadingRing").removeClass("dual-loading-ring");
}

// Set event listeners for add and delete UTubs
function setCreateDeleteUTubEventListeners() {
  setCreateUTubEventListeners();
  setDeleteEventListeners();
}

// Remove event listeners for add and delete UTubs
function removeCreateDeleteUTubEventListeners() {
  $(document).off(".createDeleteUTub");
}

// Clear the UTub Deck
function resetUTubDeck() {
  $("#listUTubs").empty();
  hideIfShown($("#utubBtnDelete"));
}

// Assembles components of the UTubDeck (top left panel)
function buildUTubDeck(utubs, timeoutID) {
  resetUTubDeck();
  const parent = $("#listUTubs");
  const numOfUTubs = utubs.length;

  if (numOfUTubs !== 0) {
    // Instantiate deck with list of UTubs accessible to current user
    for (let i = 0; i < numOfUTubs; i++) {
      parent.append(
        createUTubSelector(utubs[i].name, utubs[i].id, utubs[i].memberRole, i),
      );
    }

    hideInputsAndSetUTubDeckSubheader();
  } else {
    resetUTubDeckIfNoUTubs();
  }

  if (timeoutID) hideUTubLoadingIconAndClearTimeout(timeoutID);
}

// Takes a user input into the UTub search field and returns an array of UTub ids that have names that contain the user's input as a substring
function filterUTubs(searchTerm) {
  const UTubSelectors = $(".UTubSelector");

  if (searchTerm === "")
    return Object.values(
      UTubSelectors.map((i) => $(UTubSelectors[i]).attr("utubid")),
    );

  const filteredSelectors = UTubSelectors.filter((i) => {
    const UTubName = $(UTubSelectors[i]).children(".UTubName")[0].innerText;
    if (UTubName === "") {
      // In case UTubName returns empty string for some reason...
      return false;
    }
    return UTubName.toLowerCase().includes(searchTerm);
  });

  return Object.values(
    filteredSelectors.map((i) => $(filteredSelectors[i]).attr("utubid")),
  );
}

// Updates displayed UTub selectors based on the provided array
function updatedUTubSelectorDisplay(filteredUTubIDs) {
  const UTubSelectors = $(".UTubSelector");
  UTubSelectors.each(function (_, UTubSelector) {
    const UTubID = $(UTubSelector).attr("utubid");
    if (!filteredUTubIDs.includes(UTubID)) $(this).hide();
    else $(this).show();
  });
}

function setUTubEventListenersOnInitialPageLoad() {
  const utubs = $(".UTubSelector");
  for (let i = 0; i < utubs.length; i++) {
    setUTubSelectorEventListeners(utubs[i]);
  }
  setUTubSelectorSearchEventListener();
}

function resetUTubDeckIfNoUTubs() {
  // Subheader to prompt user to create a UTub shown
  $("#UTubDeckSubheader").text("Create a UTub");

  // Hide delete UTub button
  hideIfShown($("#utubBtnDelete"));
}

function hideInputsAndSetUTubDeckSubheader() {
  hideInputs();
  const numOfUTubs = getNumOfUTubs();
  const subheaderText =
    numOfUTubs > 1 ? numOfUTubs + " UTubs" : numOfUTubs + " UTub";

  // Subheader to tell user how many UTubs are accessible
  $("#UTubDeckSubheader").text(subheaderText);
}

function setUTubDeckOnUTubSelected(selectedUTubID, isCurrentUserOwner) {
  hideInputsAndSetUTubDeckSubheader();

  if (isCurrentUserOwner) {
    $("#utubBtnDelete").show();
  } else hideIfShown($("#utubBtnDelete"));

  const utubSelector = $(`.UTubSelector[utubid=${selectedUTubID}]`);

  if (!utubSelector.hasClass("active")) {
    // Remove all other active UTub selectors first
    $(".UTubSelector.active").removeClass("active").removeClass("focus");

    $(".UTubSelector:focus").blur();

    utubSelector.addClass("active");
  }
}
