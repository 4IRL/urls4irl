import type { UtubSummaryItem } from "../../types/utub.js";

import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { SHOW_LOADING_ICON_AFTER_MS } from "../../lib/constants.js";
import { setState } from "../../store/app-store.js";
import { hideInputs } from "../btns-forms.js";
import {
  createUTubSelector,
  setUTubSelectorEventListeners,
} from "./selectors.js";
import { getNumOfUTubs } from "./utils.js";
import { setUTubSelectorSearchEventListener } from "./search.js";
import { setDeleteEventListeners } from "./delete.js";

// Utility function to show a loading icon when loading UTubs
export function showUTubLoadingIconAndSetTimeout(): number {
  return setTimeout(function () {
    $("#UTubSelectDualLoadingRing").addClass("dual-loading-ring");
  }, SHOW_LOADING_ICON_AFTER_MS);
}

export function hideUTubLoadingIconAndClearTimeout(timeoutID: number): void {
  clearTimeout(timeoutID);
  $("#UTubSelectDualLoadingRing").removeClass("dual-loading-ring");
}

// Remove event listeners for add and delete UTubs
export function removeCreateUTubEventListeners(): void {
  $(document).off(".createUTub");
}

// Clear the UTub Deck
export function resetUTubDeck(): void {
  $("#listUTubs").empty();
  $("#utubBtnDelete").hideClass();
}

// Assembles components of the UTubDeck (top left panel)
export function buildUTubDeck(
  utubs: UtubSummaryItem[],
  timeoutID?: number,
): void {
  setState({ utubs });
  resetUTubDeck();
  const parent = $("#listUTubs");
  const numOfUTubs = utubs.length;

  if (numOfUTubs !== 0) {
    // Instantiate deck with list of UTubs accessible to current user
    for (let index = 0; index < numOfUTubs; index++) {
      parent.append(
        createUTubSelector(
          utubs[index].name,
          utubs[index].id,
          utubs[index].memberRole,
          index,
        ),
      );
    }

    hideInputsAndSetUTubDeckSubheader();
  } else {
    resetUTubDeckIfNoUTubs();
  }

  if (timeoutID) hideUTubLoadingIconAndClearTimeout(timeoutID);
}

export function setUTubEventListenersOnInitialPageLoad(): void {
  const utubs = $(".UTubSelector");
  for (let index = 0; index < utubs.length; index++) {
    setUTubSelectorEventListeners(utubs[index]);
  }
  setUTubSelectorSearchEventListener();
}

export function resetUTubDeckIfNoUTubs(): void {
  // Subheader to prompt user to create a UTub shown
  $("#UTubDeckSubheader").text(`${APP_CONFIG.strings.UTUB_CREATE_MSG}`);

  // Hide delete UTub button
  $("#utubBtnDelete").hideClass();
}

export function hideInputsAndSetUTubDeckSubheader(): void {
  hideInputs();
  const numOfUTubs = getNumOfUTubs();
  const subheaderText =
    numOfUTubs > 1 ? numOfUTubs + " UTubs" : numOfUTubs + " UTub";

  // Subheader to tell user how many UTubs are accessible
  $("#UTubDeckSubheader").text(subheaderText);
}

export function setUTubDeckOnUTubSelected(
  selectedUTubID: number,
  isCurrentUserOwner: boolean,
): void {
  hideInputsAndSetUTubDeckSubheader();

  if (isCurrentUserOwner) {
    $("#utubBtnDelete").showClassNormal();
    setDeleteEventListeners(selectedUTubID);
  } else $("#utubBtnDelete").hideClass();

  const utubSelector = $(`.UTubSelector[utubid="${selectedUTubID}"]`);

  if (!utubSelector.hasClass("active")) {
    // Remove all other active UTub selectors first
    $(".UTubSelector.active").removeClass("active").removeClass("focus");

    $(".UTubSelector:focus").blur();

    utubSelector.addClass("active");
  }
}
