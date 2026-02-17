import { $ } from "../lib/globals.js";
import { hideInputs } from "./btns-forms.js";
import {
  setTagDeckSubheaderWhenNoUTubSelected,
  resetTagDeckIfNoUTubSelected,
} from "./tags/deck.js";
import { setURLDeckWhenNoUTubSelected } from "./urls/deck.js";
import {
  setMemberDeckWhenNoUTubSelected,
  resetMemberDeck,
} from "./members/deck.js";
import { getAllUTubs } from "./utubs/utils.js";
import { buildUTubDeck } from "./utubs/deck.js";

/**
 * Sets UI state when no UTub is selected
 */
export function setUIWhenNoUTubSelected() {
  hideInputs();
  setTagDeckSubheaderWhenNoUTubSelected();
  resetTagDeckIfNoUTubSelected();
  setURLDeckWhenNoUTubSelected();
  setMemberDeckWhenNoUTubSelected();
  resetMemberDeck();
  $(".dynamic-subheader").removeClass("height-2p5rem");
  $(".sidePanelTitle").addClass("pad-b-0-25rem");

  // Remove active state from all UTub selectors
  $(".UTubSelector.active").removeClass("active").removeClass("focus");
  $(".UTubSelector:focus").blur();
}

/**
 * Resets the home page to its initial state with no UTub selected
 */
export function resetHomePageToInitialState() {
  setUIWhenNoUTubSelected();
  getAllUTubs().then((utubData) => {
    buildUTubDeck(utubData.utubs);
    setMemberDeckWhenNoUTubSelected();
    setTagDeckSubheaderWhenNoUTubSelected();
  });
}
