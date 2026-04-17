import type { UtubTag } from "../../types/url.js";

import { APP_CONFIG } from "../../lib/config.js";
import { on, AppEvents } from "../../lib/event-bus.js";
import { $ } from "../../lib/globals.js";
import { diffIDLists } from "../../logic/deck-diffing.js";
import { getState } from "../../store/app-store.js";
import {
  createUTubTagHideInput,
  removeCreateUTubTagEventListeners,
  resetCreateUTubTagFailErrors,
  resetNewUTubTagForm,
  setupOpenCreateUTubTagEventListeners,
} from "./create.js";
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

export function setTagDeckOnUTubSelected(
  dictTags: UtubTag[],
  utubID: number,
): void {
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

  _tagFilterChangedOff = on(
    AppEvents.TAG_FILTER_CHANGED,
    ({ selectedTagIDs }) => {
      updateCountOfTagFiltersApplied(selectedTagIDs.length);
    },
  );

  $("#utubTagBtnCreate").showClassNormal();

  $("#TagDeck > .dynamic-subheader").addClass("height-2p5rem");
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
}

// Update tags in LH panel based on asynchronous updates or stale data
export function updateTagDeck(updatedTags: UtubTag[], utubID: number): void {
  const oldTagIDs = getState().tags.map((tag) => tag.id);
  const newTagIDs = $.map(updatedTags, (tag) => tag.id);

  const { toRemove, toAdd } = diffIDLists(oldTagIDs, newTagIDs);

  // Find any tags in old that aren't in new and remove them
  toRemove.forEach((tagID) => {
    $(".tagFilter[data-utub-tag-id=" + tagID + "]").remove();
  });

  // Find any tags in new that aren't in old and add them
  const tagDeck = $("#listTags");
  toAdd.forEach((tagID) => {
    const tagData = updatedTags.find((tag) => tag.id === tagID);
    if (!tagData) return;
    tagDeck.append(buildTagFilterInDeck(utubID, tagData.id, tagData.tagString));
  });
}

export function setTagDeckSubheaderWhenNoUTubSelected(): void {
  $("#TagDeckSubheader").text(null);
}

export function updateCountOfTagFiltersApplied(selectedTagCount: number): void {
  $("#TagDeckSubheader").text(
    selectedTagCount +
      " of " +
      APP_CONFIG.constants.TAGS_MAX_ON_URLS +
      " tag filters applied",
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
