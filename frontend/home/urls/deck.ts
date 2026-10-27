import { $ } from "../../lib/globals.js";
import { applyDeckDiff } from "../../logic/apply-deck-diff.js";
import { getState, setState } from "../../store/app-store.js";
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
import { updateURLsAndTagSubheaderWhenTagSelected } from "./cards/filtering.js";
import { isATagSelected } from "../tags/utils.js";
import { isBackgroundRefreshActive } from "../utubs/background-refresh-flag.js";
import {
  pruneRemovedFromSelection,
  reapplyMultiSelectMark,
} from "./bulk-actions/bulk-selection.js";
import { exitMultiSelectMode } from "./bulk-actions/bulk-mode.js";
import {
  showURLSearchIcon,
  hideURLSearchIcon,
  disableURLSearch,
  setURLSearchEventListener,
  reapplyURLSearchFilter,
} from "./search.js";
import { fitUTubHeaderAndSubheader } from "../utubs/header-fit.js";
import { disposeTooltipsWithin } from "../../lib/tooltips.js";
import { debug } from "../../lib/debug.js";
import type { UtubUrlItem, UtubTag } from "../../types/url.js";
import type { MemberItem } from "../../types/member.js";

const log = debug("urls");

// Clear the URL Deck
export function resetURLDeck(): void {
  // Empty URL Deck
  // Detach NO URLs text and reattach after emptying
  resetNewURLForm();
  newURLInputRemoveEventListeners();
  // The per-card/per-tag tooltips are created at render time, so removing the
  // rows alone would leave their Bootstrap instances (and listeners) orphaned
  // on detached nodes.
  const urlRows = $(".urlRow");
  disposeTooltipsWithin(urlRows);
  urlRows.remove();
  updateUTubDescriptionHideInput();
  // resetUTubEditPanelState() closes the name form via updateUTubNameHideInput(),
  // which re-shows #urlBtnCreate as a side effect — so hide the create button
  // AFTER the reset (no UTub is selected here), otherwise it would surface again.
  resetUTubEditPanelState();
  $("#urlBtnCreate").hideClass();
  $("#urlBtnMultiSelect").hideClass();
  disableURLSearch();
}

export function resetURLDeckOnDeleteUTub(): void {
  $("#lhsToggleHeader").hideClass();
  hideURLsEmptyState();
  // See resetURLDeck(): resetUTubEditPanelState() re-shows #urlBtnCreate via
  // updateUTubNameHideInput(), so hide the create button after it runs.
  resetUTubEditPanelState();
  $("#urlBtnCreate").hideClass();
  $("#urlBtnMultiSelect").hideClass();
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
export function updateURLDeck({
  updatedUTubUrls,
  updatedUTubTags,
  utubID,
  updatedMembers,
}: {
  updatedUTubUrls: UtubUrlItem[];
  updatedUTubTags: UtubTag[];
  utubID: number;
  updatedMembers?: MemberItem[];
}): void {
  const oldCount = getState().urls.length;
  log("updateURLDeck — applying deck diff for stale URLs", {
    utubID,
    oldCount,
    newCount: updatedUTubUrls.length,
  });
  applyDeckDiff<UtubUrlItem>({
    oldItems: getState().urls,
    newItems: updatedUTubUrls,
    getID: (url) => url.utubUrlID,
    removeElement: (urlID) => {
      // Reconcile the multi-select store synchronously — before the fade —
      // so the bulk-bar count/store update immediately rather than waiting on
      // the fade animation. Gate on multiSelectMode so a single-URL removal in
      // normal mode never emits setState/URL_MULTISELECT_CHANGED app-wide.
      if (getState().multiSelectMode) pruneRemovedFromSelection([urlID]);
      const urlToRemove = $(".urlRow[utuburlid=" + urlID + "]");
      urlToRemove.fadeOut("fast", function () {
        disposeTooltipsWithin(urlToRemove);
        urlToRemove.remove();
        // A remote/collaborative stale-data diff can empty the UTub while the
        // user has multi-select mode active — fall back to the empty state,
        // hide the (now pointless) toggle, and exit mode.
        if ($(".urlRow").length === 0) {
          showURLsEmptyState();
          $("#urlBtnMultiSelect").hideClass();
          if (getState().multiSelectMode) exitMultiSelectMode();
        }
      });
    },
    addElement: (url) => {
      // The store still holds the pre-refresh members (STALE_DATA_DETECTED is
      // emitted before setState), so resolve the adder from the payload's.
      const urlBlock = createURLBlock({
        url,
        dictTags: updatedUTubTags,
        utubID,
        members: updatedMembers,
      });
      $("#listURLs").append(urlBlock);
      // Deck-diff reconcile lives in the URL adapter (never the generic engine):
      // re-mark a re-added card from the store so a live multi-selection
      // survives the diff, symmetric with removeElement's prune above.
      // createURLBlock also re-marks internally, so this is an idempotent
      // belt-and-suspenders re-mark that keeps the reconcile contract explicit
      // at the adapter boundary.
      reapplyMultiSelectMark(urlBlock);
      // A card another member added while the user was away is not a new
      // affordance the user just earned: skip the swipe nudge for it.
      if (!isBackgroundRefreshActive()) {
        triggerURLSwipeNudgeIfEligible({ urlRow: urlBlock });
      }
    },
    updateElement: (urlID, url) => {
      const urlCard = $(".urlRow[utuburlid=" + urlID + "]");
      if (urlCard.length) {
        updateURLAfterFindingStaleData(urlCard, url, updatedUTubTags, utubID);
      }
    },
  });

  // 0 -> n: leave the empty state and reveal the controls that need URLs
  // (mirrors setURLDeckOnUTubSelected).
  if (oldCount === 0 && updatedUTubUrls.length > 0) {
    hideURLsEmptyState();
    $("#urlBtnMultiSelect").showClassNormal();
    showURLSearchIcon();
  }

  reorderURLCardsToPayloadOrder(updatedUTubUrls);

  if ($("#SearchURLWrap").hasClass("visible-flex")) {
    reapplyURLSearchFilter();
  }

  // The filtering.ts STALE_DATA_DETECTED listener runs before cards are added
  // (new cards default to filterable=true), so re-apply the active tag filter
  // now that the new cards exist.
  if (isATagSelected()) {
    updateURLsAndTagSubheaderWhenTagSelected({ urls: updatedUTubUrls });
  }

  restripeURLCardsInDOMOrder();
}

/**
 * Order-only live-apply of a server payload: moves the existing cards (never
 * recreates, adds or removes one) to the payload order, permutes the store's
 * `urls` the same way without adopting the payload's items or values (so a later
 * `updateURLDeck` diff still sees a new URL as new), then restripes, reapplies
 * the search/tag filters and keeps the selected card in view.
 */
export function applyServerUrlOrder(payloadUrls: UtubUrlItem[]): void {
  const payloadRank = new Map<number, number>();
  payloadUrls.forEach((url, index) => payloadRank.set(url.utubUrlID, index));

  const storeUrls = getState().urls;
  const inBoth = storeUrls
    .filter((url) => payloadRank.has(url.utubUrlID))
    .sort(
      (first, second) =>
        payloadRank.get(first.utubUrlID)! - payloadRank.get(second.utubUrlID)!,
    );
  const storeOnly = storeUrls.filter((url) => !payloadRank.has(url.utubUrlID));
  setState({ urls: [...inBoth, ...storeOnly] });

  reorderURLCardsToPayloadOrder(payloadUrls);

  if ($("#SearchURLWrap").hasClass("visible-flex")) {
    reapplyURLSearchFilter();
  }
  if (isATagSelected()) {
    updateURLsAndTagSubheaderWhenTagSelected({ urls: getState().urls });
  }
  restripeURLCardsInDOMOrder();

  const selectedCard = document.querySelector<HTMLElement>(
    "#listURLs .urlRow[urlSelected='true']",
  );
  selectedCard?.scrollIntoView?.({ block: "nearest" });
}

// Reorders the existing `.urlRow` cards to the payload (server, i.e. viewer's
// sort) order. Skipped when the order already matches, so a refresh that only
// edits a title never moves the DOM or blurs a focused element.
function reorderURLCardsToPayloadOrder(updatedUTubUrls: UtubUrlItem[]): void {
  const cardsByID = new Map<number, HTMLElement>();
  const domIDs: number[] = [];
  const knownIDs = new Set(updatedUTubUrls.map((url) => url.utubUrlID));
  $("#listURLs .urlRow").each((_, urlCard) => {
    const urlID = Number($(urlCard).attr("utuburlid"));
    if (!knownIDs.has(urlID)) return;
    cardsByID.set(urlID, urlCard);
    domIDs.push(urlID);
  });

  const orderedIDs = updatedUTubUrls
    .map((url) => url.utubUrlID)
    .filter((urlID) => cardsByID.has(urlID));
  if (domIDs.every((urlID, index) => urlID === orderedIDs[index])) return;

  const previouslyFocused = document.activeElement;
  const listURLs = $("#listURLs");
  orderedIDs.forEach((urlID) => {
    listURLs.append($(cardsByID.get(urlID)!).detach());
  });
  if (
    previouslyFocused instanceof HTMLElement &&
    previouslyFocused.isConnected &&
    document.activeElement !== previouslyFocused
  ) {
    previouslyFocused.focus({ preventScroll: true });
  }
}

// Visibility-independent alternating stripes in DOM order. Unlike
// reapplyAlternatingURLCardBackgroundAfterFilter this has no `:visible`, which
// matches nothing while the centre panel is hidden on mobile.
function restripeURLCardsInDOMOrder(): void {
  $("#listURLs .urlRow[filterable=true][searchable!=false]").each(
    (idx, urlCard) => {
      $(urlCard)
        .removeClass("odd even")
        .addClass(idx % 2 == 0 ? "even" : "odd");
    },
  );
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
      const urlBlock = createURLBlock({
        url: dictURLs[urlIndex],
        dictTags,
        utubID,
      }).addClass(urlIndex % 2 === 0 ? "even" : "odd");
      parent.append(urlBlock);
      triggerURLSwipeNudgeIfEligible({ urlRow: urlBlock });
    }

    hideURLsEmptyState();
    // A UTub with URLs can be multi-selected — reveal the mode toggle.
    $("#urlBtnMultiSelect").showClassNormal();
  } else {
    showURLsEmptyState();
    // Nothing to select in an empty UTub — keep the toggle hidden.
    $("#urlBtnMultiSelect").hideClass();
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
  const urlRows = $(".urlRow");
  disposeTooltipsWithin(urlRows);
  urlRows.remove();
  $("#URLDeckHeader").text("URLs");
  $(".updateUTubBtn").hideClass();
  $("#urlBtnCreate").hideClass();
  // Covers both the initial page load (before any UTub is selected) and the
  // post-delete/leave paths, which all route through here.
  $("#urlBtnMultiSelect").hideClass();
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
on(AppEvents.STALE_DATA_DETECTED, ({ urls, tags, utubID, members }) =>
  updateURLDeck({
    updatedUTubUrls: urls,
    updatedUTubTags: tags,
    utubID,
    updatedMembers: members,
  }),
);
on(AppEvents.UTUB_DELETED, () => resetURLDeckOnDeleteUTub());
