import { $ } from "../../../lib/globals.js";
import { updateCountOfTagFiltersApplied } from "../../tags/deck.js";
import { currentTagDeckIDs, isATagSelected } from "../../tags/utils.js";

export const TagCountOperation = Object.freeze({
  INCREMENT: 1,
  DECREMENT: -1,
});

export function updateURLsAndTagSubheaderWhenTagSelected() {
  const selectedTagIDs = $.map($(".tagFilter.selected"), (tagFilter) =>
    parseInt($(tagFilter).attr("data-utub-tag-id")),
  );
  const urlCards = $(".urlRow");
  const numSelectedTagIDs = selectedTagIDs.length;

  let tagBadgeIDsOnURL, shouldShow;
  urlCards.each((_, urlCard) => {
    tagBadgeIDsOnURL = $.map($(urlCard).find(".tagBadge"), (tagBadge) =>
      parseInt($(tagBadge).attr("data-utub-tag-id")),
    );

    shouldShow = true;
    for (let i = 0; i < selectedTagIDs.length; i++) {
      if (!tagBadgeIDsOnURL.includes(selectedTagIDs[i])) {
        shouldShow = false;
      }
    }

    shouldShow
      ? $(urlCard).attr({ filterable: true })
      : $(urlCard).attr({ filterable: false });
  });
  reapplyAlternatingURLCardBackgroundAfterFilter();
  updateCountOfTagFiltersApplied(numSelectedTagIDs);
  updateVisibleURLsForTagCount();
  sortTagFiltersInPlace();
}

function updateVisibleURLsForTagCount() {
  const currentTagIDs = currentTagDeckIDs();
  const currentTagIDsMap = new Map();
  currentTagIDs.forEach((tagID) => {
    currentTagIDsMap.set(`${tagID}`, 0);
  });

  const visibleURLCards = $(".urlRow[filterable=true]");

  let urlTagIDsRaw, urlTagIDs, visibleURL, urlTag;
  for (let i = 0; i < visibleURLCards.length; i++) {
    visibleURL = $(visibleURLCards[i]);
    urlTagIDsRaw = visibleURL.attr("data-utub-url-tag-ids");
    if (!urlTagIDsRaw) continue;
    urlTagIDs = urlTagIDsRaw.split(",");

    urlTagIDs.forEach((tagID) => {
      currentTagIDsMap.set(tagID, (currentTagIDsMap.get(tagID) || 0) + 1);
    });
  }

  let tagCountElem, tagCountText, tagID;
  for (let j = 0; j < currentTagIDs.length; j++) {
    tagID = currentTagIDs[j];
    tagCountElem = $(
      `.tagFilter[data-utub-tag-id=${tagID}]` + " .tagAppliedToUrlsCount",
    );
    tagCountText = tagCountElem.text().split(" / ");
    if (!tagCountText || tagCountText.length !== 2) continue;

    tagCountElem.text(
      `${currentTagIDsMap.get(`${tagID}`)}` + " / " + `${tagCountText[1]}`,
    );
  }
}

export function updateTagFilterCount(utubTagID, tagCount, tagCountOperation) {
  const tagCountElem = $(
    `.tagFilter[data-utub-tag-id="${utubTagID}"]` + " .tagAppliedToUrlsCount",
  );

  const tagCountText = tagCountElem.text().split(" / ");
  if (!tagCountText || tagCountText.length !== 2) {
    tagCountElem.text(`${tagCount}` + " / " + `${tagCount}`);
    return;
  }

  let delta;
  switch (tagCountOperation) {
    case TagCountOperation.DECREMENT:
      delta = -1;
      break;
    default:
      delta = 1;
  }

  tagCountElem.text(
    `${parseInt(tagCountText[0]) + delta}` + " / " + `${tagCount}`,
  );
}

export function reapplyAlternatingURLCardBackgroundAfterFilter() {
  const visibleURLCards = $(".urlRow[filterable=true]:visible");

  visibleURLCards.each((idx, urlCard) => {
    $(urlCard)
      .removeClass("odd even")
      .addClass(idx % 2 == 0 ? "even" : "odd");
  });
}

function sortTagFiltersInPlace() {
  const container = $("#listTags");
  const tagFilters = container.children(".tagFilter").get();

  tagFilters.sort((a, b) => {
    const textA = $(a).find(".tagAppliedToUrlsCount").text().trim();
    const textB = $(b).find(".tagAppliedToUrlsCount").text().trim();

    const numeratorA = parseInt(textA.split(" / ")[0]) || 0;
    const numeratorB = parseInt(textB.split(" / ")[0]) || 0;

    return numeratorB - numeratorA;
  });

  const detachedElements = tagFilters.map((el) => $(el).detach());

  for (let i = 0; i < detachedElements.length; i++) {
    container.append(detachedElements[i]);
  }
}

export function isURLCurrentlyVisibleInURLDeck(urlString) {
  const visibleURLs = $(".urlString");

  for (let i = 0; i < visibleURLs.length; i++) {
    if ($(visibleURLs[i]).attr("href") === urlString) {
      return true;
    }
  }
  return false;
}

export function updateTagFilteringOnURLOrURLTagDeletion() {
  if (isATagSelected()) {
    updateURLsAndTagSubheaderWhenTagSelected();
  } else {
    reapplyAlternatingURLCardBackgroundAfterFilter();
  }
}
