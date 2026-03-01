import { $ } from "../../lib/globals.js";
import { getState } from "../../store/app-store.js";

// Returns tag IDs currently in the store
export function currentTagDeckIDs() {
  return getState().tags.map((t) => t.id);
}

export function isTagInUTubTagDeck(utubTagid) {
  return currentTagDeckIDs().includes(utubTagid);
}

// Given a set of tag badges, verify a given tagID exists within those badges
export function isTagInUTub(tagBadges, utubTagID) {
  let tagExistsInUTub = false;
  tagBadges.each(function () {
    if (parseInt($(this).attr("data-utub-tag-id")) === utubTagID) {
      tagExistsInUTub = true;
    }
  });
  return tagExistsInUTub;
}

export function isATagSelected() {
  return getState().selectedTagIDs.length > 0;
}
