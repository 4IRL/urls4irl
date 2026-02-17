import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import {
  showUTubLoadingIconAndSetTimeout,
  hideUTubLoadingIconAndClearTimeout,
} from "./deck.js";

// Verify UTubID is valid
export function isValidUTubID(utubIdStr) {
  const utubId = parseInt(utubIdStr);
  const isANumber = !isNaN(utubId);
  const isPositive = utubId > 0;
  const isValidIntegerFormat = String(utubId) === utubIdStr;

  return isANumber && isPositive && isValidIntegerFormat;
}

export function isUtubIdValidOnPageLoad(utubId) {
  return isUtubIdValidFromStateAccess(utubId);
}

export function isUtubIdValidFromStateAccess(utubId) {
  return $(`.UTubSelector[utubid='${utubId}']`).length === 1;
}

// Function to count number of UTubs current user has access to
export function getNumOfUTubs() {
  return $("#listUTubs > .UTubSelector").length;
}

// Streamline extraction of UTub ID
export function getActiveUTubID() {
  return parseInt($(".UTubSelector.active").attr("utubid"));
}

// Check if a UTub is selected
export function isUTubSelected() {
  return $(".UTubSelector.active").length === 1;
}

// Streamline the jQuery selector extraction of UTub name.
export function getCurrentUTubName() {
  return $(".UTubSelector.active .UTubName").text();
}

// Quickly extracts all UTub names from #listUTubs and returns an array.
export function getAllAccessibleUTubNames() {
  let utubNames = [];
  const utubSelectorNames = $(".UTubName");
  utubSelectorNames.map((i) => utubNames.push($(utubSelectorNames[i]).text()));
  return utubNames;
}

// Utility route to get all UTub summaries
export function getAllUTubs() {
  const timeoutID = showUTubLoadingIconAndSetTimeout();
  return $.getJSON(APP_CONFIG.routes.getUTubs).always(function () {
    hideUTubLoadingIconAndClearTimeout(timeoutID);
  });
}

// Hides modal for UTub same name action confirmation
export function sameNameWarningHideModal() {
  $("#confirmModal").modal("hide");
}
