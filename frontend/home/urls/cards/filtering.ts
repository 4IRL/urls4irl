import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { getState, setState } from "../../../store/app-store.js";
import { on, emit, AppEvents } from "../../../lib/event-bus.js";
import {
  currentTagDeckIDs,
  isATagSelected,
  readTagCount,
  writeTagCount,
} from "../../tags/utils.js";
import { effectiveTagDisplaySettings } from "../../tags/display-settings.js";
import { applyAlternatingTagBackground } from "../../tags/search.js";
import {
  compareTags,
  computeURLVisibility,
  computeVisibleTagCounts,
  sortTagsByCount,
} from "../../../logic/tag-filtering.js";
import { getNumOfVisibleURLs } from "../utils.js";
import { normalizeViewMode } from "../view-mode.js";
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

export function updateURLsAndTagSubheaderWhenTagSelected({
  urls = getState().urls,
}: { urls?: UtubUrlItem[] } = {}): void {
  const selectedTagIDs = getState().selectedTagIDs;
  const urlsWithTagIDs = urls.map((url) => ({
    urlId: url.utubUrlID,
    tagIDs: url.utubUrlTagIDs,
  }));
  const visibility = computeURLVisibility({
    selectedTagIDs,
    urlsWithTagIDs,
    mode: effectiveTagDisplaySettings().tagMatchMode,
  });
  applyURLVisibilityToDOM(visibility);
  // A card still mid-fadeOut after a removal is in the DOM but not in `urls`:
  // never count it as visible.
  const knownURLIDs = new Set(urls.map((url) => url.utubUrlID));
  $(".urlRow").each((_, urlCard) => {
    if (!knownURLIDs.has(Number($(urlCard).attr("utuburlid")))) {
      $(urlCard).attr({ filterable: false });
    }
  });
  const totalURLs = urls.length;
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
  applyTagSort();
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

  for (let tagIndex = 0; tagIndex < currentTagIDs.length; tagIndex++) {
    const tagID = currentTagIDs[tagIndex];
    const chip = $(`.tagFilter[data-utub-tag-id=${tagID}]`);
    const current = readTagCount(chip);
    if (!current) continue;
    writeTagCount({
      chip,
      inView: tagCounts.get(`${tagID}`) ?? 0,
      total: current.total,
    });
  }
}

// Write only the authoritative UTub-wide total (the `.tagCountTotal` span of a
// tag-filter chip) directly from server data, leaving the in-view half untouched
// (it is recomputed in a single later pass by updateVisibleURLsForTagCount).
// A chip with a missing or malformed count is left as-is. Shared by bulk-tag
// and bulk-delete.
export function writeTagChipDenominator({
  tagId,
  count,
}: {
  tagId: number | string;
  count: number;
}): void {
  const chip = $(`.tagFilter[data-utub-tag-id="${tagId}"]`);
  const current = readTagCount(chip);
  if (!current) return;
  writeTagCount({ chip, inView: current.inView, total: count });
  reapplyTagSortForNonDefault();
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

  const chip = $(`.tagFilter[data-utub-tag-id="${utubTagID}"]`);

  const current = readTagCount(chip);
  if (!current) {
    writeTagCount({ chip, inView: tagCount, total: tagCount });
    reapplyTagSortForNonDefault();
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

  writeTagCount({ chip, inView: current.inView + delta, total: tagCount });
  reapplyTagSortForNonDefault();
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

const TAG_DRAGGING_SELECTOR = "#listTags .tagDragging";

function isTagDragActive(): boolean {
  return $(TAG_DRAGGING_SELECTOR).length > 0;
}

let sortDeferredUntilDragEnds = false;

function runSortAfterDragEnds(): void {
  document.removeEventListener("dragend", runSortAfterDragEnds);
  document.removeEventListener("drop", runSortAfterDragEnds);
  if (!sortDeferredUntilDragEnds) return;
  sortDeferredUntilDragEnds = false;
  applyTagSort();
}

/**
 * Reorders `#listTags` by the resolved sort, re-stripes, and keeps keyboard
 * focus on the same chip (by `data-utub-tag-id`). While a tag drag is active the
 * reorder is deferred until it ends. "Most in view" keeps the stable count-only
 * sort (no tie-break), exactly as before; every other order uses `compareTags`.
 */
export function applyTagSort(): void {
  if (isTagDragActive()) {
    if (!sortDeferredUntilDragEnds) {
      sortDeferredUntilDragEnds = true;
      document.addEventListener("dragend", runSortAfterDragEnds);
      document.addEventListener("drop", runSortAfterDragEnds);
    }
    return;
  }

  const { tagSort } = effectiveTagDisplaySettings();
  const container = $("#listTags");
  const tagFilterElems = container.children(".tagFilter").get();
  // Detaching a node drops its focus, so remember the focused element and the
  // chip it sits in (by `data-utub-tag-id`) and restore focus afterwards.
  const focusedElement = document.activeElement as HTMLElement | null;
  const focusedChipID =
    focusedElement && container[0]?.contains(focusedElement)
      ? $(focusedElement).closest(".tagFilter").attr("data-utub-tag-id")
      : undefined;

  const tags = tagFilterElems.map((el) => {
    const count = readTagCount($(el));
    return {
      el,
      visibleCount: count?.inView ?? 0,
      sortable: {
        id: Number($(el).attr("data-utub-tag-id")),
        name: $(el).find("span").first().text(),
        total: count?.total ?? 0,
        inView: count?.inView ?? 0,
      },
    };
  });

  const sorted =
    tagSort === "most_in_view"
      ? sortTagsByCount(tags)
      : [...tags].sort((left, right) =>
          compareTags({
            left: left.sortable,
            right: right.sortable,
            sort: tagSort,
          }),
        );
  const detachedElements = sorted.map(({ el }) => $(el).detach());
  detachedElements.forEach((el) => container.append(el));

  applyAlternatingTagBackground();
  if (
    focusedChipID !== undefined &&
    document.activeElement !== focusedElement
  ) {
    const chip = container.children(
      `.tagFilter[data-utub-tag-id="${focusedChipID}"]`,
    )[0];
    const target = focusedElement?.isConnected ? focusedElement : chip;
    target?.focus();
  }
}

/**
 * The extra re-sort triggers (tag create, delete, stale-data refresh, count
 * change) that apply only to the non-default orders. Under "Most in view" the
 * deck keeps re-sorting only after a filter change, as before.
 */
export function reapplyTagSortForNonDefault(): void {
  if (effectiveTagDisplaySettings().tagSort === "most_in_view") return;
  applyTagSort();
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

export function updateTagFilteringOnURLOrURLTagDeletion({
  urls = getState().urls,
}: { urls?: UtubUrlItem[] } = {}): void {
  if (isATagSelected()) {
    updateURLsAndTagSubheaderWhenTagSelected({ urls });
    return;
  }
  reapplyAlternatingURLCardBackgroundAfterFilter();
  // Non-default sorts follow stale-data refreshes (tags added, counts changed).
  reapplyTagSortForNonDefault();
  // The no-tag-selected branch is reachable *from* a filtered state: the
  // STALE_DATA_DETECTED handler below prunes selectedTagIDs of tags another
  // session deleted, and pruning the last one lands here. Only
  // updateURLsAndTagSubheaderWhenTagSelected() emits TAG_FILTER_CHANGED, so
  // without this every filter-state indicator — the collapsed Tag deck's pill
  // and its SR announcement, the mobile sheet handle's count badge — would keep
  // showing the pre-prune count until the user touched a filter again. Emitting
  // the (now empty) set here is idempotent for every subscriber.
  emit(AppEvents.TAG_FILTER_CHANGED, {
    selectedTagIDs: getState().selectedTagIDs,
  });
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
  document.body.dataset.view = normalizeViewMode(viewMode);
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

on(AppEvents.STALE_DATA_DETECTED, ({ tags, urls }) => {
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
  updateTagFilteringOnURLOrURLTagDeletion({ urls });
});
