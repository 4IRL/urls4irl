import type { UtubTag } from "../../types/url.js";

import { APP_CONFIG } from "../../lib/config.js";
import { debug } from "../../lib/debug.js";
import { on, AppEvents } from "../../lib/event-bus.js";
import { $ } from "../../lib/globals.js";
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
import {
  disableUnselectAllButtonAfterTagFilterRemoved,
  resetCountOfTagFiltersApplied,
} from "./unselect-all.js";

// Tracks the off-function for the per-UTub TAG_FILTER_CHANGED listener
let _tagFilterChangedOff: (() => void) | null = null;

const log = debug("tags");

export function setTagDeckOnUTubSelected(
  dictTags: UtubTag[],
  utubID: number,
): void {
  log("setTagDeckOnUTubSelected — rebuilding tag deck", {
    utubID,
    tagCount: dictTags.length,
    hadPriorListener: _tagFilterChangedOff !== null,
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

  // Stripe the freshly-built rows (mirrors the member deck build).
  applyAlternatingTagBackground();

  setTagSelectorSearchEventListener();
  setTagNameFilterToggleListeners();
  showTagFilterBar();

  _tagFilterChangedOff = on(
    AppEvents.TAG_FILTER_CHANGED,
    ({ selectedTagIDs }) => {
      updateCountOfTagFiltersApplied(selectedTagIDs.length);
    },
  );

  $("#utubTagBtnCreate").showClassNormal();
}

export function resetTagDeck(): void {
  if (_tagFilterChangedOff) {
    _tagFilterChangedOff();
    _tagFilterChangedOff = null;
  }

  $("#listTags").empty();
  resetCountOfTagFiltersApplied();
  disableUnselectAllButtonAfterTagFilterRemoved();
  $("#utubTagBtnCreate").hideClass();
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

export function updateCountOfTagFiltersApplied(selectedTagCount: number): void {
  // Inline "(applied/max-applicable)" total next to the deck title.
  $("#TagDeckCount").text(
    "(" + selectedTagCount + "/" + APP_CONFIG.constants.TAGS_MAX_ON_URLS + ")",
  );
}

export function removeTagFromTagDeckGivenTagID(tagID: number): void {
  $(".tagFilter[data-utub-tag-id=" + tagID + "]").remove();
}

on(AppEvents.UTUB_SELECTED, ({ tags, utubID }) =>
  setTagDeckOnUTubSelected(tags, utubID),
);
on(AppEvents.STALE_DATA_DETECTED, ({ tags, utubID }) =>
  updateTagDeck(tags, utubID),
);
