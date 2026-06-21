import type { UtubSummaryItem } from "../../types/utub.js";

import { $ } from "../../lib/globals.js";
import { SHOW_LOADING_ICON_AFTER_MS } from "../../lib/constants.js";
import { setState } from "../../store/app-store.js";
import { hideInputs } from "../btns-forms.js";
import {
  createUTubSelector,
  setUTubSelectorEventListeners,
} from "./selectors.js";
import {
  applyAlternatingUTubSelectorBackground,
  hideUTubSearchBar,
  setUTubNameFilterToggleListeners,
  setUTubSelectorSearchEventListener,
  showUTubSearchBar,
} from "./search.js";
import { setDeleteEventListeners } from "./delete.js";
import { updateUTubDeckCount } from "./utils.js";

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
  $("#memberSelfBtnDelete").hideClass();
}

// Hide both role-dependent UTub actions (delete for owner, leave for member)
// when no UTub is selected. The UTub deck owns these buttons regardless of which
// deck triggered the reset.
export function setUTubDeckWhenNoUTubSelected(): void {
  $("#utubBtnDelete").hideClass();
  $("#memberSelfBtnDelete").hideClass();
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

    hideInputsAndUpdateUTubDeck();
    // Zebra-stripe the freshly-built rows. utubs.css keys striping off the
    // JS-assigned `.even`/`.odd` classes (not `:nth-child`), so every path that
    // materializes the row set must (re)apply them.
    applyAlternatingUTubSelectorBackground();
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
  setUTubNameFilterToggleListeners();
  updateUTubDeckCount();
  // The initial deck is server-rendered (Jinja), so this listener-setup path —
  // not buildUTubDeck — is what runs on a fresh page load. Stripe those rows
  // here, since utubs.css now relies on the JS-assigned `.even`/`.odd` classes.
  applyAlternatingUTubSelectorBackground();
}

export function resetUTubDeckIfNoUTubs(): void {
  // Hide the role-dependent UTub actions (delete for owner, leave for member)
  $("#utubBtnDelete").hideClass();
  $("#memberSelfBtnDelete").hideClass();

  // Hide the search bar and reveal the "Create a UTub" subheader
  hideUTubSearchBar();
}

export function hideInputsAndUpdateUTubDeck(): void {
  hideInputs();
  showUTubSearchBar();
}

export function setUTubDeckOnUTubSelected(
  selectedUTubID: number,
  isCurrentUserOwner: boolean,
): void {
  hideInputsAndUpdateUTubDeck();

  // Owner sees Delete, member sees Leave — mutually exclusive, both in the
  // UTub deck header. The member-leave click binding lives in the members
  // domain (createLeaveUTubAsMemberIcon, fired on UTUB_SELECTED).
  if (isCurrentUserOwner) {
    $("#utubBtnDelete").showClassNormal();
    $("#memberSelfBtnDelete").hideClass();
    setDeleteEventListeners(selectedUTubID);
  } else {
    $("#utubBtnDelete").hideClass();
    $("#memberSelfBtnDelete").showClassNormal();
  }

  const utubSelector = $(`.UTubSelector[utubid="${selectedUTubID}"]`);

  if (!utubSelector.hasClass("active")) {
    // Remove all other active UTub selectors first
    $(".UTubSelector.active").removeClass("active").removeClass("focus");

    $(".UTubSelector:focus").blur();

    utubSelector.addClass("active");
  }
}
