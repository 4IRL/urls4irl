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

// Remove event listeners for add and delete UTubs
function removeCreateUTubEventListeners() {
  $(document).off(".createUTub");
}

// Clear the UTub Deck
function resetUTubDeck() {
  $("#listUTubs").empty();
  $("#utubBtnDelete").hideClass();
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

function setUTubEventListenersOnInitialPageLoad() {
  const utubs = $(".UTubSelector");
  for (let i = 0; i < utubs.length; i++) {
    setUTubSelectorEventListeners(utubs[i]);
  }
  setUTubSelectorSearchEventListener();
}

function resetUTubDeckIfNoUTubs() {
  // Subheader to prompt user to create a UTub shown
  $("#UTubDeckSubheader").text(`${STRINGS.UTUB_CREATE_MSG}`);

  // Hide delete UTub button
  $("#utubBtnDelete").hideClass();
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
    $("#utubBtnDelete").showClassNormal();
    setDeleteEventListeners(selectedUTubID);
  } else $("#utubBtnDelete").hideClass();

  const utubSelector = $(`.UTubSelector[utubid=${selectedUTubID}]`);

  if (!utubSelector.hasClass("active")) {
    // Remove all other active UTub selectors first
    $(".UTubSelector.active").removeClass("active").removeClass("focus");

    $(".UTubSelector:focus").blur();

    utubSelector.addClass("active");
  }
}
