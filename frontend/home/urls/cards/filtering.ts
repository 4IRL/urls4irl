import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { getState, setState } from "../../../store/app-store.js";
import { on, emit, AppEvents } from "../../../lib/event-bus.js";
import { currentTagDeckIDs, isATagSelected } from "../../tags/utils.js";
import {
  computeURLVisibility,
  computeVisibleTagCounts,
  sortTagsByCount,
} from "../../../logic/tag-filtering.js";
import { getNumOfVisibleURLs } from "../utils.js";
import type {
  DensityValue,
  SortOrderValue,
  ViewModeValue,
} from "../../../types/preferences.js";
import type { UtubUrlItem } from "../../../types/url.js";
import { debug } from "../../../lib/debug.js";

const log = debug("urls:cards");

function showTagFilterNoResultsMessage(): void {
  $("#URLTagFilterNoResults")
    .text(APP_CONFIG.strings.TAG_FILTER_NO_RESULTS)
    .removeClass("hidden");
  $("#URLTagFilterAnnouncement").text(APP_CONFIG.strings.TAG_FILTER_NO_RESULTS);
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
  const totalURLs = getState().urls.length;
  const visibleURLs = getNumOfVisibleURLs();
  log("tag filter applied to URL visibility", {
    selectedTagIDs,
    totalURLs,
    visibleURLs,
    showingNoResults: totalURLs > 0 && visibleURLs === 0,
  });
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

export function updateVisibleURLsForTagCount(): void {
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

// Write only the authoritative UTub-wide total (the right-hand/denominator digit
// of the `X / Y` count on a tag-filter chip) directly from server data, leaving
// the visible/numerator half untouched (it is recomputed in a single later pass
// by updateVisibleURLsForTagCount). Guards on the `X / Y` split so a malformed or
// missing chip label is left as-is. Shared by bulk-tag and bulk-delete.
export function writeTagChipDenominator({
  tagId,
  count,
}: {
  tagId: number | string;
  count: number;
}): void {
  const tagCountElem = $(
    `.tagFilter[data-utub-tag-id="${tagId}"] .tagAppliedToUrlsCount`,
  );
  const tagCountText = tagCountElem.text().split(" / ");
  if (tagCountText.length !== 2) return;
  tagCountElem.text(`${tagCountText[0]} / ${count}`);
}

export function updateTagFilterCount(
  utubTagID: number,
  tagCount: number,
  tagCountOperation: TagCountOperationValue,
): void {
  log("tag filter count updated", {
    utubTagID,
    operation:
      tagCountOperation === TagCountOperation.INCREMENT
        ? "increment"
        : "decrement",
    tagCount,
  });

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

// Pure sort of a URL list by the stored default-sort preference. Returns a NEW
// array (no in-place mutation) and has zero DOM/store side effects. DD-36: the
// deck's full-load ordering is server-authoritative — this helper's ONLY
// production caller is the create-time re-sort in createURLSuccess(), where a
// freshly-created card must land in its sorted position before the next
// server-driven load supersedes it.
export function applyDefaultUrlSort(
  urls: UtubUrlItem[],
  sortOrder: SortOrderValue,
): UtubUrlItem[] {
  const sorted = [...urls];
  switch (sortOrder) {
    case "oldest":
      sorted.sort(
        (first, second) =>
          new Date(first.addedAt).getTime() -
          new Date(second.addedAt).getTime(),
      );
      break;
    case "title_az":
      sorted.sort((first, second) =>
        first.urlTitle
          .toLowerCase()
          .localeCompare(second.urlTitle.toLowerCase()),
      );
      break;
    case "newest":
    default:
      sorted.sort(
        (first, second) =>
          new Date(second.addedAt).getTime() -
          new Date(first.addedAt).getTime(),
      );
  }
  return sorted;
}

// Cosmetic-only presentation toggle (border/shadow/layout, never row spacing —
// row spacing stays under applyDefaultDensity's touch-target-guarded control).
// Sets document.body.dataset.view from the stored ViewMode on initial render.
export function applyDefaultViewMode(viewMode: ViewModeValue): void {
  document.body.dataset.view = viewMode;
}

// Sets document.body.dataset.density from the stored Density on initial render.
// The compact reduction of row min-height/padding is scoped in CSS to
// (any-pointer: fine) devices only, so touch devices never drop below the 44px
// WCAG 2.5.5 touch-target floor regardless of this preference.
export function applyDefaultDensity(density: DensityValue): void {
  document.body.dataset.density = density;
}

on(AppEvents.TAG_DELETED, () => updateURLsAndTagSubheaderWhenTagSelected());

on(AppEvents.UTUB_SELECTED, () => hideTagFilterNoResultsMessage());

on(AppEvents.URL_SEARCH_VISIBILITY_CHANGED, () =>
  reapplyAlternatingURLCardBackgroundAfterFilter(),
);

on(AppEvents.STALE_DATA_DETECTED, ({ tags }) => {
  log("stale-data: pruning selectedTagIDs of tags no longer in UTub", {
    previousSelected: getState().selectedTagIDs,
    retained: getState().selectedTagIDs.filter((id) =>
      tags.some((tag) => tag.id === id),
    ),
  });
  setState({
    selectedTagIDs: getState().selectedTagIDs.filter((id) =>
      tags.some((tag) => tag.id === id),
    ),
  });
  updateTagFilteringOnURLOrURLTagDeletion();
});
