import type { UtubTag } from "../../types/url.js";

import { debug } from "../../lib/debug.js";
import { on, AppEvents } from "../../lib/event-bus.js";
import { $ } from "../../lib/globals.js";
import { hideTooltip } from "../../lib/tooltips.js";
import { applyDeckDiff } from "../../logic/apply-deck-diff.js";
import { getState } from "../../store/app-store.js";
import {
  createUTubTagHideInput,
  removeCreateUTubTagEventListeners,
  resetCreateUTubTagFailErrors,
  resetNewUTubTagForm,
  setupOpenCreateUTubTagEventListeners,
} from "./create.js";
import {
  applyAlternatingTagBackground,
  hideTagFilterBar,
  reapplyTagFilter,
  resetTagFilter,
  setTagNameFilterToggleListeners,
  setTagSelectorSearchEventListener,
  showTagFilterBar,
} from "./search.js";
import { hideTagDeckEmptyState, showTagDeckEmptyState } from "./empty-state.js";
import { buildTagFilterInDeck } from "./tags.js";
import {
  closeUTubTagBtnMenuOnUTubTags,
  setTagDeckBtnsOnUpdateAllUTubTagsClosed,
  setUnselectUpdateUTubTagEventListeners,
} from "./update-all.js";
import { disableUnselectAllButtonAfterTagFilterRemoved } from "./unselect-all.js";

const log = debug("tags");

export function setTagDeckOnUTubSelected(
  dictTags: UtubTag[],
  utubID: number,
): void {
  log("setTagDeckOnUTubSelected — rebuilding tag deck", {
    utubID,
    tagCount: dictTags.length,
  });
  resetTagDeck();
  setupOpenCreateUTubTagEventListeners(utubID);
  setUnselectUpdateUTubTagEventListeners();
  const parent = $("#listTags");

  // Select all checkbox if tags in UTub
  if (dictTags.length > 0) {
    const unselectAllBtn = $("#unselectAllTagFilters");
    unselectAllBtn.showClassNormal();
    unselectAllBtn.addClass("red-icon-disabled");
    $("#utubTagBtnUpdateAllOpen").showClassNormal();
    hideTagDeckEmptyState();
  } else {
    showTagDeckEmptyState();
  }

  // Loop through all tags and provide checkbox input for filtering
  for (let i in dictTags) {
    parent.append(
      buildTagFilterInDeck(
        utubID,
        dictTags[i].id,
        dictTags[i].tagString,
        dictTags[i].tagApplied,
      ),
    );
  }

  refreshTagDeckTagCount();

  // Stripe the freshly-built rows (mirrors the member deck build).
  applyAlternatingTagBackground();

  setTagSelectorSearchEventListener();
  setTagNameFilterToggleListeners();
  showTagFilterBar();

  $("#utubTagBtnCreate").showClassNormal();
}

export function resetTagDeck(): void {
  $("#listTags").empty();
  refreshTagDeckTagCount();
  disableUnselectAllButtonAfterTagFilterRemoved();
  $("#utubTagBtnCreate").hideClass();
  // This button is hidden by callers rather than by its own click, so hide any
  // open hover tooltip here or the bubble lingers detached over the deck.
  hideTooltip($("#unselectAllTagFilters")[0]);
  $("#unselectAllTagFilters").hideClass();
  $("#utubTagBtnUpdateAllOpen").hideClass();
  createUTubTagHideInput();
  closeUTubTagBtnMenuOnUTubTags();
  setTagDeckBtnsOnUpdateAllUTubTagsClosed();
  hideTagDeckEmptyState();
  resetTagFilter();
  hideTagFilterBar();
}

export function resetTagDeckIfNoUTubSelected(): void {
  $("#listTags").empty();
  $("#createUTubTagWrap").hideClass();
  $("#utubTagBtnCreate").hideClass();
  // Same detached-bubble guard as resetTagDeck() above.
  hideTooltip($("#unselectAllTagFilters")[0]);
  $("#unselectAllTagFilters").hideClass();
  setTagDeckBtnsOnUpdateAllUTubTagsClosed();
  $("#utubTagBtnUpdateAllOpen").hideClass();
  removeCreateUTubTagEventListeners();
  resetCreateUTubTagFailErrors();
  resetNewUTubTagForm();
  hideTagDeckEmptyState();
  resetTagFilter();
  hideTagFilterBar();
}

// Update tags in LH panel based on asynchronous updates or stale data
export function updateTagDeck(updatedTags: UtubTag[], utubID: number): void {
  log("updateTagDeck — applying tag deck diff", {
    utubID,
    oldCount: getState().tags.length,
    newCount: updatedTags.length,
  });
  applyDeckDiff<UtubTag>({
    oldItems: getState().tags,
    newItems: updatedTags,
    getID: (tag) => tag.id,
    removeElement: (tagID) =>
      $(".tagFilter[data-utub-tag-id=" + tagID + "]").remove(),
    addElement: (tag) => {
      $("#listTags").append(
        buildTagFilterInDeck(utubID, tag.id, tag.tagString),
      );
    },
  });

  // Covers both halves of the diff — rows added and rows removed.
  refreshTagDeckTagCount();

  reapplyTagFilter();
  if (updatedTags.length === 0) {
    showTagDeckEmptyState();
  } else {
    hideTagDeckEmptyState();
  }
}

export function setTagDeckSubheaderWhenNoUTubSelected(): void {
  $("#TagDeckCount").text("");
}

// Inline "(n)" total of the UTub's tags, next to the deck title. Derived from
// the rendered rows rather than from the store so it can never drift from what
// the user is actually looking at — and so a collapsed Tag deck, whose "no tags
// yet" empty state lives inside the hidden .content, still reads as empty.
export function refreshTagDeckTagCount(): void {
  $("#TagDeckCount").text("(" + $("#listTags > .tagFilter").length + ")");
}

export function removeTagFromTagDeckGivenTagID(tagID: number): void {
  $(".tagFilter[data-utub-tag-id=" + tagID + "]").remove();
  refreshTagDeckTagCount();
}

on(AppEvents.UTUB_SELECTED, ({ tags, utubID }) =>
  setTagDeckOnUTubSelected(tags, utubID),
);
on(AppEvents.STALE_DATA_DETECTED, ({ tags, utubID }) =>
  updateTagDeck(tags, utubID),
);
