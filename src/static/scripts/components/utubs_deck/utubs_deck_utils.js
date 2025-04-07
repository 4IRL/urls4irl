"use strict";

// Verify UTubID is valid
function isValidUTubID(utubIdStr) {
  const utubId = parseInt(utubIdStr);
  const isANumber = !isNaN(utubId);
  const isPositive = utubId > 0;
  const isValidIntegerFormat = String(utubId) === utubIdStr;

  return isANumber && isPositive && isValidIntegerFormat;
}

function isUtubIdValidOnPageLoad(utubId) {
  return isUtubIdValidFromStateAccess(utubId);
}

function isUtubIdValidFromStateAccess(utubId) {
  return $(`.UTubSelector[utubid='${utubId}']`).length === 1;
}

// Function to count number of UTubs current user has access to
function getNumOfUTubs() {
  return $("#listUTubs > .UTubSelector").length;
}

// Streamline extraction of UTub ID
function getActiveUTubID() {
  return parseInt($(".UTubSelector.active").attr("utubid"));
}

// Check if a UTub is selected
function isUTubSelected() {
  return $(".UTubSelector.active").length === 1;
}

// Streamline the jQuery selector extraction of UTub name.
function getCurrentUTubName() {
  return $(".UTubSelector.active .UTubName").text();
}

// Quickly extracts all UTub names from #listUTubs and returns an array.
function getAllAccessibleUTubNames() {
  let utubNames = [];
  const utubSelectorNames = $(".UTubName");
  utubSelectorNames.map((i) => utubNames.push($(utubSelectorNames[i]).text()));
  return utubNames;
}

// Utility route to get all UTub summaries
function getAllUTubs() {
  const timeoutID = showUTubLoadingIconAndSetTimeout();
  return $.getJSON(routes.getUTubs).always(function () {
    hideUTubLoadingIconAndClearTimeout(timeoutID);
  });
}

// TODO: This function appears to be doing too much...
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
