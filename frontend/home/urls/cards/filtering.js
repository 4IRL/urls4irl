import { $ } from "../../../lib/globals.js";
import { getState, setState } from "../../../store/app-store.js";
import { on, emit, AppEvents } from "../../../lib/event-bus.js";
import { currentTagDeckIDs, isATagSelected } from "../../tags/utils.js";
import {
  computeURLVisibility,
  computeVisibleTagCounts,
  sortTagsByCount,
} from "../../../logic/tag-filtering.js";

export const TagCountOperation = Object.freeze({
  INCREMENT: 1,
  DECREMENT: -1,
});

function applyURLVisibilityToDOM(visibility) {
  visibility.forEach(({ urlId, visible }) => {
    $(`.urlRow[utuburlid=${urlId}]`).attr({ filterable: visible });
  });
}

export function updateURLsAndTagSubheaderWhenTagSelected() {
  const selectedTagIDs = getState().selectedTagIDs;
  const urlsWithTagIDs = getState().urls.map((u) => ({
    urlId: u.utubUrlID,
    tagIDs: u.utubUrlTagIDs,
  }));
  const visibility = computeURLVisibility(selectedTagIDs, urlsWithTagIDs);
  applyURLVisibilityToDOM(visibility);
  reapplyAlternatingURLCardBackgroundAfterFilter();
  emit(AppEvents.TAG_FILTER_CHANGED, { selectedTagIDs });
  updateVisibleURLsForTagCount();
  sortTagFiltersInPlace();
}

function updateVisibleURLsForTagCount() {
  const currentTagIDs = currentTagDeckIDs();
  const visibleURLCards = $(".urlRow[filterable=true]");

  const visibleURLTagIDsList = [];
  visibleURLCards.each((_, urlCard) => {
    const urlTagIDsRaw = $(urlCard).attr("data-utub-url-tag-ids");
    visibleURLTagIDsList.push(urlTagIDsRaw ? urlTagIDsRaw.split(",") : []);
  });

  const tagCounts = computeVisibleTagCounts(
    visibleURLTagIDsList,
    currentTagIDs,
  );

  let tagCountElem, tagCountText;
  for (let j = 0; j < currentTagIDs.length; j++) {
    const tagID = currentTagIDs[j];
    tagCountElem = $(
      `.tagFilter[data-utub-tag-id=${tagID}]` + " .tagAppliedToUrlsCount",
    );
    tagCountText = tagCountElem.text().split(" / ");
    if (!tagCountText || tagCountText.length !== 2) continue;
    tagCountElem.text(
      `${tagCounts.get(`${tagID}`)}` + " / " + `${tagCountText[1]}`,
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
  const tagFilterElems = container.children(".tagFilter").get();

  const tags = tagFilterElems.map((el) => {
    const textParts = $(el)
      .find(".tagAppliedToUrlsCount")
      .text()
      .trim()
      .split(" / ");
    return { el, visibleCount: parseInt(textParts[0]) || 0 };
  });

  const sorted = sortTagsByCount(tags);
  const detachedElements = sorted.map(({ el }) => $(el).detach());
  detachedElements.forEach((el) => container.append(el));
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

on(AppEvents.TAG_DELETED, () => updateURLsAndTagSubheaderWhenTagSelected());

on(AppEvents.STALE_DATA_DETECTED, ({ tags }) => {
  setState({
    selectedTagIDs: getState().selectedTagIDs.filter((id) =>
      tags.some((t) => t.id === id),
    ),
  });
  updateTagFilteringOnURLOrURLTagDeletion();
});
