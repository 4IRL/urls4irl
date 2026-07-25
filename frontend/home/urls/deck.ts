import { $ } from "../../lib/globals.js";
import { applyDeckDiff } from "../../logic/apply-deck-diff.js";
import { getState } from "../../store/app-store.js";
import { APP_CONFIG } from "../../lib/config.js";
import { showURLsEmptyState, hideURLsEmptyState } from "./empty-state.js";
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
import {
  setupUTubEditPanelToggle,
  setUTubEditPanelToggleVisibility,
  resetUTubEditPanelState,
} from "./update-utub-panel.js";
import { createURLShowInputEventListeners } from "./create-btns.js";
import {
  createURLBlock,
  updateURLAfterFindingStaleData,
  newURLInputRemoveEventListeners,
} from "./cards/cards.js";
import { resetNewURLForm } from "./cards/create.js";
import { triggerURLSwipeNudgeIfEligible } from "./cards/swipe.js";
import {
  showURLSearchIcon,
  hideURLSearchIcon,
  disableURLSearch,
  setURLSearchEventListener,
  reapplyURLSearchFilter,
} from "./search.js";
import { fitUTubHeaderAndSubheader } from "../utubs/header-fit.js";
import { debug } from "../../lib/debug.js";
import type { UtubUrlItem, UtubTag } from "../../types/url.js";

const log = debug("urls");

// Clear the URL Deck
export function resetURLDeck(): void {
  // Empty URL Deck
  // Detach NO URLs text and reattach after emptying
  resetNewURLForm();
  newURLInputRemoveEventListeners();
  $(".urlRow").remove();
  updateUTubDescriptionHideInput();
  // resetUTubEditPanelState() closes the name form via updateUTubNameHideInput(),
  // which re-shows #urlBtnCreate as a side effect — so hide the create button
  // AFTER the reset (no UTub is selected here), otherwise it would surface again.
  resetUTubEditPanelState();
  $("#urlBtnCreate").hideClass();
  disableURLSearch();
}

export function resetURLDeckOnDeleteUTub(): void {
  $("#lhsToggleHeader").hideClass();
  hideURLsEmptyState();
  // See resetURLDeck(): resetUTubEditPanelState() re-shows #urlBtnCreate via
  // updateUTubNameHideInput(), so hide the create button after it runs.
  resetUTubEditPanelState();
  $("#urlBtnCreate").hideClass();
  disableURLSearch();
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
  log("updateURLDeck — applying deck diff for stale URLs", {
    utubID,
    oldCount: getState().urls.length,
    newCount: updatedUTubUrls.length,
  });
  applyDeckDiff<UtubUrlItem>({
    oldItems: getState().urls,
    newItems: updatedUTubUrls,
    getID: (url) => url.utubUrlID,
    removeElement: (urlID) => {
      const urlToRemove = $(".urlRow[utuburlid=" + urlID + "]");
      urlToRemove.fadeOut("fast", function () {
        urlToRemove.remove();
      });
    },
    addElement: (url) => {
      const urlBlock = createURLBlock(url, updatedUTubTags, utubID);
      $("#listURLs").append(urlBlock);
      triggerURLSwipeNudgeIfEligible({ urlRow: urlBlock });
    },
    updateElement: (urlID, url) => {
      const urlCard = $(".urlRow[utuburlid=" + urlID + "]");
      if (urlCard.length) {
        updateURLAfterFindingStaleData(urlCard, url, updatedUTubTags, utubID);
      }
    },
  });

  if ($("#SearchURLWrap").hasClass("visible-flex")) {
    reapplyURLSearchFilter();
  }
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
  setupUTubEditPanelToggle(utubID);
  setUTubEditPanelToggleVisibility();

  const parent = $("#listURLs");
  const numOfURLs = dictURLs.length ? dictURLs.length : 0;

  log("setURLDeckOnUTubSelected — rendering URL deck", {
    utubID,
    numOfURLs,
    showingEmptyState: numOfURLs === 0,
  });

  if (numOfURLs !== 0) {
    // Instantiate deck with list of URLs stored in current UTub
    for (let urlIndex = 0; urlIndex < dictURLs.length; urlIndex++) {
      const urlBlock = createURLBlock(
        dictURLs[urlIndex],
        dictTags,
        utubID,
      ).addClass(urlIndex % 2 === 0 ? "even" : "odd");
      parent.append(urlBlock);
      triggerURLSwipeNudgeIfEligible({ urlRow: urlBlock });
    }

    hideURLsEmptyState();
  } else {
    showURLsEmptyState();
  }

  $("#urlBtnCreate").showClassNormal();
  // The LHS minify toggle is only meaningful with a UTub open. Remove the hidden
  // class (don't add visible-flex) so the mobile rule that hides .lhs-toggle is
  // not overridden by an !important display.
  $("#lhsToggleHeader").removeHideClass();
  setUTubNameAndDescription(utubName);

  setURLSearchEventListener();
  if (numOfURLs > 0) {
    showURLSearchIcon();
  } else {
    hideURLSearchIcon();
  }
  reapplyURLSearchFilter();
}

export function setURLDeckWhenNoUTubSelected(): void {
  $(".urlRow").remove();
  $("#URLDeckHeader").text("URLs");
  $(".updateUTubBtn").hideClass();
  $("#urlBtnCreate").hideClass();
  // No UTub open -> hide the LHS minify toggle (initial load, leave, delete).
  $("#lhsToggleHeader").hideClass();
  removeEventListenersForShowCreateUTubDescIfEmptyDesc();

  const urlDeckSubheader = $("#URLDeckSubheader");
  urlDeckSubheader.text(`${APP_CONFIG.strings.UTUB_SELECT}`);
  urlDeckSubheader.removeClass("editable");
  urlDeckSubheader.off("click.updateUTubDesc");
  urlDeckSubheader.show();
  $("#URLDeckHeader").removeClass("editable");
  $("#URLDeckHeader").off("click.updateUTubname");
  $("#UTubDescriptionSubheaderWrap").removeClass("hidden");
  disableURLSearch();
  fitUTubHeaderAndSubheader();
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
