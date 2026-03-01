import { $ } from "../../lib/globals.js";
import { diffIDLists } from "../../logic/deck-diffing.js";
import { getState } from "../../store/app-store.js";
import { APP_CONFIG } from "../../lib/config.js";
import { on, AppEvents } from "../../lib/event-bus.js";
import { bindSwitchURLKeyboardEventListeners } from "./utils.js";
import {
  setupUpdateUTubDescriptionEventListeners,
  updateUTubDescriptionHideInput,
  removeEventListenersForShowCreateUTubDescIfEmptyDesc,
} from "./update-description.js";
import {
  setupUpdateUTubNameEventListeners,
  updateUTubNameHideInput,
  setUTubNameAndDescription,
} from "./update-name.js";
import { createURLShowInputEventListeners } from "./create-btns.js";
import {
  createURLBlock,
  updateURLAfterFindingStaleData,
  newURLInputRemoveEventListeners,
} from "./cards/cards.js";
import { resetNewURLForm } from "./cards/create.js";

// Clear the URL Deck
export function resetURLDeck() {
  // Empty URL Deck
  // Detach NO URLs text and reattach after emptying
  resetNewURLForm();
  newURLInputRemoveEventListeners();
  $(".urlRow").remove();
  $("#urlBtnCreate").hideClass();
  updateUTubDescriptionHideInput();
}

export function resetURLDeckOnDeleteUTub() {
  $("#urlBtnCreate").hideClass();
  $("#NoURLsSubheader").hideClass();
  $("#urlBtnDeckCreateWrap").hideClass();
  $("#updateUTubDescriptionBtn")
    .removeClass("visibleBtn")
    .addClass("hiddenBtn");
}

export function showURLDeckBannerError(errorMessage) {
  const SECONDS_TO_SHOW_ERROR = 3.5;
  const errorBanner = $("#URLDeckErrorIndicator");
  const CLASS_TO_SHOW = "URLDeckErrorIndicatorShow";
  errorBanner.text(errorMessage).addClass(CLASS_TO_SHOW).trigger("focus");

  setTimeout(() => {
    errorBanner.removeClass(CLASS_TO_SHOW);
  }, 1000 * SECONDS_TO_SHOW_ERROR);
}

// Update URLs in center panel based on asynchronous updates or stale data
export function updateURLDeck(updatedUTubUrls, updatedUTubTags, utubID) {
  const oldURLIDs = getState().urls.map((u) => u.utubUrlID);
  const newURLIDs = $.map(updatedUTubUrls, (newURL) => newURL.utubUrlID);

  const { toRemove, toAdd, toUpdate } = diffIDLists(oldURLIDs, newURLIDs);

  // Remove any URLs that are in old that aren't in new
  toRemove.forEach((urlID) => {
    const urlToRemove = $(".urlRow[utuburlid=" + urlID + "]");
    urlToRemove.fadeOut("fast", function () {
      urlToRemove.remove();
    });
  });

  // Add any URLs that are in new that aren't in old
  const urlDeck = $("#listURLs");
  toAdd.forEach((urlID) => {
    urlDeck.append(
      createURLBlock(
        updatedUTubUrls.find((url) => url.utubUrlID === urlID),
        updatedUTubTags,
        utubID,
      ),
    );
  });

  // Update any URLs in both old/new that might have new data from new
  toUpdate.forEach((urlID) => {
    const urlToUpdate = $(".urlRow[utuburlid=" + urlID + "]");
    updateURLAfterFindingStaleData(
      urlToUpdate,
      updatedUTubUrls.find((url) => url.utubUrlID === urlID),
      updatedUTubTags,
      utubID,
    );
  });
}

// Build center panel URL list for selectedUTub
export function setURLDeckOnUTubSelected(utubID, utubName, dictURLs, dictTags) {
  resetURLDeck();
  createURLShowInputEventListeners(utubID);
  setupUpdateUTubDescriptionEventListeners(utubID);
  setupUpdateUTubNameEventListeners(utubID);

  const parent = $("#listURLs");
  const numOfURLs = dictURLs.length ? dictURLs.length : 0;

  if (numOfURLs !== 0) {
    // Instantiate deck with list of URLs stored in current UTub
    for (let i = 0; i < dictURLs.length; i++) {
      parent.append(
        createURLBlock(dictURLs[i], dictTags, utubID).addClass(
          i % 2 === 0 ? "even" : "odd",
        ),
      );
    }

    // Show access all URLs button
    $("#accessAllURLsBtn").showClassNormal();
    $("#NoURLsSubheader").hideClass();
    $("#urlBtnDeckCreateWrap").hideClass();
  } else {
    $("#NoURLsSubheader").showClassNormal();
    $("#urlBtnDeckCreateWrap").showClassFlex();
    $("#accessAllURLsBtn").hideClass();
  }

  $("#urlBtnCreate").showClassNormal();
  setUTubNameAndDescription(utubName);
}

export function setURLDeckWhenNoUTubSelected() {
  $(".urlRow").remove();
  $("#URLDeckHeader").text("URLs");
  $(".updateUTubBtn").hideClass();
  $("#urlBtnCreate").hideClass();
  $("#accessAllURLsBtn").hideClass();
  $("#utubNameBtnUpdate").hideClass();
  $("#updateUTubDescriptionBtn")
    .removeClass("visibleBtn")
    .addClass("hiddenBtn");
  removeEventListenersForShowCreateUTubDescIfEmptyDesc();

  const urlDeckSubheader = $("#URLDeckSubheader");
  urlDeckSubheader.text(`${APP_CONFIG.strings.UTUB_SELECT}`);
  urlDeckSubheader.show();
  $("#UTubDescriptionSubheaderWrap").removeClass("hidden");

  // Prevent on-hover of URL Deck Header to show update UTub name button in case of back button
  $("#utubNameBtnUpdate").removeClass("visibleBtn");
}

export function initURLDeck() {
  bindSwitchURLKeyboardEventListeners();
}

on(AppEvents.UTUB_SELECTED, ({ utubID, utubName, urls, tags }) =>
  setURLDeckOnUTubSelected(utubID, utubName, urls, tags),
);
on(AppEvents.STALE_DATA_DETECTED, ({ urls, tags, utubID }) =>
  updateURLDeck(urls, tags, utubID),
);
on(AppEvents.UTUB_DELETED, () => resetURLDeckOnDeleteUTub());
