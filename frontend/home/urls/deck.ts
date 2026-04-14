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
  setUTubNameAndDescription,
} from "./update-name.js";
import { createURLShowInputEventListeners } from "./create-btns.js";
import {
  createURLBlock,
  updateURLAfterFindingStaleData,
  newURLInputRemoveEventListeners,
} from "./cards/cards.js";
import { resetNewURLForm } from "./cards/create.js";
import type { UtubUrlItem, UtubTag } from "../../types/url.js";

// Clear the URL Deck
export function resetURLDeck(): void {
  // Empty URL Deck
  // Detach NO URLs text and reattach after emptying
  resetNewURLForm();
  newURLInputRemoveEventListeners();
  $(".urlRow").remove();
  $("#urlBtnCreate").hideClass();
  updateUTubDescriptionHideInput();
}

export function resetURLDeckOnDeleteUTub(): void {
  $("#urlBtnCreate").hideClass();
  $("#NoURLsSubheader").hideClass();
  $("#urlBtnDeckCreateWrap").hideClass();
  $("#updateUTubDescriptionBtn")
    .removeClass("visibleBtn")
    .addClass("hiddenBtn");
}

export function showURLDeckBannerError(errorMessage: string): void {
  const SECONDS_TO_SHOW_ERROR = 3.5;
  const errorBanner = $("#URLDeckErrorIndicator");
  const CLASS_TO_SHOW = "URLDeckErrorIndicatorShow";
  errorBanner.text(errorMessage).addClass(CLASS_TO_SHOW).trigger("focus");

  setTimeout(() => {
    errorBanner.removeClass(CLASS_TO_SHOW);
  }, 1000 * SECONDS_TO_SHOW_ERROR);
}

// Update URLs in center panel based on asynchronous updates or stale data
export function updateURLDeck(
  updatedUTubUrls: UtubUrlItem[],
  updatedUTubTags: UtubTag[],
  utubID: number,
): void {
  const oldURLIDs = getState().urls.map((url) => url.utubUrlID);
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
    const urlToAdd = updatedUTubUrls.find((url) => url.utubUrlID === urlID);
    if (!urlToAdd) return;
    urlDeck.append(createURLBlock(urlToAdd, updatedUTubTags, utubID));
  });

  // Update any URLs in both old/new that might have new data from new
  toUpdate.forEach((urlID) => {
    const urlToUpdate = $(".urlRow[utuburlid=" + urlID + "]");
    const newUrl = updatedUTubUrls.find((url) => url.utubUrlID === urlID);
    if (!newUrl) return;
    updateURLAfterFindingStaleData(
      urlToUpdate,
      newUrl,
      updatedUTubTags,
      utubID,
    );
  });
}

// Build center panel URL list for selectedUTub
export function setURLDeckOnUTubSelected(
  utubID: number,
  utubName: string,
  dictURLs: UtubUrlItem[],
  dictTags: UtubTag[],
): void {
  resetURLDeck();
  createURLShowInputEventListeners(utubID);
  setupUpdateUTubDescriptionEventListeners(utubID);
  setupUpdateUTubNameEventListeners(utubID);

  const parent = $("#listURLs");
  const numOfURLs = dictURLs.length ? dictURLs.length : 0;

  if (numOfURLs !== 0) {
    // Instantiate deck with list of URLs stored in current UTub
    for (let urlIndex = 0; urlIndex < dictURLs.length; urlIndex++) {
      parent.append(
        createURLBlock(dictURLs[urlIndex], dictTags, utubID).addClass(
          urlIndex % 2 === 0 ? "even" : "odd",
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

export function setURLDeckWhenNoUTubSelected(): void {
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

export function initURLDeck(): void {
  bindSwitchURLKeyboardEventListeners();
}

on(AppEvents.UTUB_SELECTED, ({ utubID, utubName, urls, tags }) =>
  setURLDeckOnUTubSelected(utubID, utubName, urls, tags),
);
on(AppEvents.STALE_DATA_DETECTED, ({ urls, tags, utubID }) =>
  updateURLDeck(urls, tags, utubID),
);
on(AppEvents.UTUB_DELETED, () => resetURLDeckOnDeleteUTub());
