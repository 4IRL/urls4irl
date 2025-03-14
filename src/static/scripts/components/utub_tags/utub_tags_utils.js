"use strict";

// Simple function to streamline the jQuery selector extraction of what tag IDs are currently displayed in the Tag Deck
function currentTagDeckIDs() {
  return $.map($(".tagFilter"), (tag) =>
    parseInt($(tag).attr("data-utub-tag-id")),
  );
}

function isTagInUTubTagDeck(utubTagid) {
  return currentTagDeckIDs().includes(utubTagid);
}

// Given a set of tag badges, verify a given tagID exists within those badges
function isTagInUTub(tagBadges, utubTagID) {
  let tagExistsInUTub = false;
  tagBadges.each(function () {
    if (parseInt($(this).attr("data-utub-tag-id")) === utubTagID) {
      tagExistsInUTub = true;
    }
  });
  return tagExistsInUTub;
}
