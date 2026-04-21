import { $ } from "../../../lib/globals.js";
import { getState, setState } from "../../../store/app-store.js";
import { on, emit, AppEvents } from "../../../lib/event-bus.js";
import { currentTagDeckIDs, isATagSelected } from "../../tags/utils.js";
import {
  computeURLVisibility,
  computeVisibleTagCounts,
  sortTagsByCount,
} from "../../../logic/tag-filtering.js";
import { getNumOfURLs, getNumOfVisibleURLs } from "../utils.js";

export const TAG_FILTER_NO_RESULTS_TEXT = "No URLs match selected tags";

function showTagFilterNoResultsMessage(): void {
  $("#URLTagFilterNoResults")
    .text(TAG_FILTER_NO_RESULTS_TEXT)
    .removeClass("hidden");
  $("#URLTagFilterAnnouncement").text(TAG_FILTER_NO_RESULTS_TEXT);
}

function hideTagFilterNoResultsMessage(): void {
  $("#URLTagFilterNoResults").addClass("hidden").text("");
  $("#URLTagFilterAnnouncement").text("");
}

export const TagCountOperation = Object.freeze({
  INCREMENT: 1,
  DECREMENT: -1,
} as const);

type TagCountOperationValue =
  (typeof TagCountOperation)[keyof typeof TagCountOperation];

type UrlVisibility = {
  urlId: number;
  visible: boolean;
};

function applyURLVisibilityToDOM(visibility: UrlVisibility[]): void {
  visibility.forEach(({ urlId, visible }) => {
    $(`.urlRow[utuburlid=${urlId}]`).attr({ filterable: visible });
  });
}

export function updateURLsAndTagSubheaderWhenTagSelected(): void {
  const selectedTagIDs = getState().selectedTagIDs;
  const urlsWithTagIDs = getState().urls.map((url) => ({
    urlId: url.utubUrlID,
    tagIDs: url.utubUrlTagIDs,
  }));
  const visibility = computeURLVisibility(selectedTagIDs, urlsWithTagIDs);
  applyURLVisibilityToDOM(visibility);
  const totalURLs = getNumOfURLs();
  const visibleURLs = getNumOfVisibleURLs();
  if (totalURLs > 0 && visibleURLs === 0) {
    showTagFilterNoResultsMessage();
  } else {
    hideTagFilterNoResultsMessage();
  }
  emit(AppEvents.URL_TAG_FILTER_APPLIED);
  reapplyAlternatingURLCardBackgroundAfterFilter();
  emit(AppEvents.TAG_FILTER_CHANGED, { selectedTagIDs });
  updateVisibleURLsForTagCount();
  sortTagFiltersInPlace();
}

function updateVisibleURLsForTagCount(): void {
  const currentTagIDs = currentTagDeckIDs();
  const visibleURLCards = $(".urlRow[filterable=true]");

  const visibleURLTagIDsList: string[][] = [];
  visibleURLCards.each((_, urlCard) => {
    const urlTagIDsRaw = $(urlCard).attr("data-utub-url-tag-ids");
    visibleURLTagIDsList.push(urlTagIDsRaw ? urlTagIDsRaw.split(",") : []);
  });

  const tagCounts = computeVisibleTagCounts(
    visibleURLTagIDsList,
    currentTagIDs,
  );

  let tagCountElem: JQuery;
  let tagCountText: string[];
  for (let tagIndex = 0; tagIndex < currentTagIDs.length; tagIndex++) {
    const tagID = currentTagIDs[tagIndex];
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

export function updateTagFilterCount(
  utubTagID: number,
  tagCount: number,
  tagCountOperation: TagCountOperationValue,
): void {
  const tagCountElem = $(
    `.tagFilter[data-utub-tag-id="${utubTagID}"]` + " .tagAppliedToUrlsCount",
  );

  const tagCountText = tagCountElem.text().split(" / ");
  if (!tagCountText || tagCountText.length !== 2) {
    tagCountElem.text(`${tagCount}` + " / " + `${tagCount}`);
    return;
  }

  let delta: number;
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

export function reapplyAlternatingURLCardBackgroundAfterFilter(): void {
  const visibleURLCards = $(
    ".urlRow[filterable=true][searchable!=false]:visible",
  );

  visibleURLCards.each((idx, urlCard) => {
    $(urlCard)
      .removeClass("odd even")
      .addClass(idx % 2 == 0 ? "even" : "odd");
  });
}

function sortTagFiltersInPlace(): void {
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

export function isURLCurrentlyVisibleInURLDeck(urlString: string): boolean {
  const visibleURLs = $(".urlString");

  for (let urlIndex = 0; urlIndex < visibleURLs.length; urlIndex++) {
    if ($(visibleURLs[urlIndex]).attr("href") === urlString) {
      return true;
    }
  }
  return false;
}

export function updateTagFilteringOnURLOrURLTagDeletion(): void {
  if (isATagSelected()) {
    updateURLsAndTagSubheaderWhenTagSelected();
  } else {
    reapplyAlternatingURLCardBackgroundAfterFilter();
  }
}

on(AppEvents.TAG_DELETED, () => updateURLsAndTagSubheaderWhenTagSelected());

on(AppEvents.UTUB_SELECTED, () => hideTagFilterNoResultsMessage());

on(AppEvents.URL_SEARCH_VISIBILITY_CHANGED, () =>
  reapplyAlternatingURLCardBackgroundAfterFilter(),
);

on(AppEvents.STALE_DATA_DETECTED, ({ tags }) => {
  setState({
    selectedTagIDs: getState().selectedTagIDs.filter((id) =>
      tags.some((tag) => tag.id === id),
    ),
  });
  updateTagFilteringOnURLOrURLTagDeletion();
});
