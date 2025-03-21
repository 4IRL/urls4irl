"use strict";

$(document).ready(function () {
  const timeoutID = showUTubLoadingIconAndSetTimeout();
  setUIWhenNoUTubSelected();
  // Instantiate UTubDeck with user's accessible UTubs
  try {
    buildUTubDeck(UTubs, timeoutID);
  } catch (error) {
    console.log("Something is wrong!");
    console.log(error);
  }

  setCreateDeleteUTubEventListeners();
});

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
      parent.append(createUTubSelector(utubs[i].name, utubs[i].id, i));
    }

    hideInputsAndSetUTubDeckSubheader();
    setURLDeckWhenNoUTubSelected();
  } else {
    resetUTubDeckIfNoUTubs();
  }

  if (timeoutID) hideUTubLoadingIconAndClearTimeout(timeoutID);
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

function setUTubDeckOnUTubSelected(selectedUTubID, UTubOwnerUserID) {
  hideInputsAndSetUTubDeckSubheader();

  if (getCurrentUserID() === UTubOwnerUserID) {
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
