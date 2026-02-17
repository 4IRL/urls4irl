import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { buildTagFilterInDeck } from "./tags.js";
import {
  createUTubTagHideInput,
  setupOpenCreateUTubTagEventListeners,
  removeCreateUTubTagEventListeners,
  resetCreateUTubTagFailErrors,
  resetNewUTubTagForm,
} from "./create.js";
import {
  closeUTubTagBtnMenuOnUTubTags,
  setTagDeckBtnsOnUpdateAllUTubTagsClosed,
  setUnselectUpdateUTubTagEventListeners,
} from "./update-all.js";
import {
  disableUnselectAllButtonAfterTagFilterRemoved,
  resetCountOfTagFiltersApplied,
} from "./unselect-all.js";

export function setTagDeckOnUTubSelected(dictTags, utubID) {
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

  $("#utubTagBtnCreate").showClassNormal();

  $("#TagDeck > .dynamic-subheader").addClass("height-2p5rem");
}

export function resetTagDeck() {
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

export function resetTagDeckIfNoUTubSelected() {
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
export function updateTagDeck(updatedTags, utubID) {
  const oldTags = $(".tagFilter");
  const oldTagIDs = $.map(oldTags, (tag) =>
    parseInt($(tag).attr("data-utub-tag-id")),
  );
  const newTagIDs = $.map(updatedTags, (tag) => tag.id);

  // Find any tags in old that aren't in new and remove them
  let oldTagID;
  for (let i = 0; i < oldTags.length; i++) {
    oldTagID = parseInt($(oldTags[i]).attr("data-utub-tag-id"));
    if (!newTagIDs.includes(oldTagID)) {
      $(".tagFilter[data-utub-tag-id=" + oldTagID + "]").remove();
    }
  }

  // Find any tags in new that aren't in old and add them
  const tagDeck = $("#listTags");
  for (let i = 0; i < updatedTags.length; i++) {
    if (!oldTagIDs.includes(updatedTags[i].id)) {
      tagDeck.append(
        buildTagFilterInDeck(
          utubID,
          updatedTags[i].id,
          updatedTags[i].tagString,
        ),
      );
    }
  }
}

export function setTagDeckSubheaderWhenNoUTubSelected() {
  $("#TagDeckSubheader").text(null);
}

export function updateCountOfTagFiltersApplied(selectedTagCount) {
  $("#TagDeckSubheader").text(
    selectedTagCount +
      " of " +
      APP_CONFIG.constants.TAGS_MAX_ON_URLS +
      " tag filters applied",
  );
}

export function removeTagFromTagDeckGivenTagID(tagID) {
  $(".tagFilter[data-utub-tag-id=" + tagID + "]").remove();
}
