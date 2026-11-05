import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { debug } from "../../lib/debug.js";
import { $ } from "../../lib/globals.js";
import { emit } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { AppEvents, on } from "../../lib/event-bus.js";
import { getState, setState, subscribe } from "../../store/app-store.js";
import type { TagMatchModeValue } from "../../types/preferences.js";
import { announceSettingsStatus } from "../panel-settings/announce.js";
import { isPanelSettingsOpen } from "../panel-settings/state.js";
import { updateURLsAndTagSubheaderWhenTagSelected } from "../urls/cards/filtering.js";
import { getNumOfVisibleURLs } from "../urls/utils.js";
import { deleteUTubTagShowModal } from "./delete.js";
import { effectiveTagDisplaySettings } from "./display-settings.js";
import { tagFilterResultAnnouncement } from "./utils.js";
import {
  disableUnselectAllButtonAfterTagFilterRemoved,
  enableUnselectAllButtonAfterTagFilterApplied,
} from "./unselect-all.js";

const log = debug("tags");

// Dynamically generates the delete URL-Tag icon when needed
function createTagDeleteIcon(pixelSize: number = 15): JQuery<SVGElement> {
  const WIDTH_HEIGHT_PX = pixelSize + "px";
  const SVG_NS = "http://www.w3.org/2000/svg";
  const deleteURLTagOuterIconSvg = $(
    document.createElementNS(SVG_NS, "svg"),
  ) as JQuery<SVGElement>;
  const deleteURLTagInnerIconPath = $(
    document.createElementNS(SVG_NS, "path"),
  ) as JQuery<SVGElement>;
  const path =
    "M11.46.146A.5.5 0 0 0 11.107 0H4.893a.5.5 0 0 0-.353.146L.146 4.54A.5.5 0 0 0 0 4.893v6.214a.5.5 0 0 0 .146.353l4.394 4.394a.5.5 0 0 0 .353.146h6.214a.5.5 0 0 0 .353-.146l4.394-4.394a.5.5 0 0 0 .146-.353V4.893a.5.5 0 0 0-.146-.353zm-6.106 4.5L8 7.293l2.646-2.647a.5.5 0 0 1 .708.708L8.707 8l2.647 2.646a.5.5 0 0 1-.708.708L8 8.707l-2.646 2.647a.5.5 0 0 1-.708-.708L7.293 8 4.646 5.354a.5.5 0 1 1 .708-.708";

  deleteURLTagInnerIconPath.attr({
    d: path,
  });

  deleteURLTagOuterIconSvg
    .attr({
      xmlns: SVG_NS,
      width: WIDTH_HEIGHT_PX,
      height: WIDTH_HEIGHT_PX,
      fill: "currentColor",
      class: "bi bi-x-octagon-fill",
      viewBox: "0 0 16 16",
    })
    .append(deleteURLTagInnerIconPath);

  return deleteURLTagOuterIconSvg;
}

// Creates tag filter for addition to Tag deck
export function buildTagFilterInDeck(
  utubID: number,
  tagID: number,
  tagString: string,
  urlCount: number = 0,
): JQuery<HTMLDivElement> {
  const container = $(document.createElement("div")) as JQuery<HTMLDivElement>;
  const tagStringSpan = $(document.createElement("span"));
  const tagCountContainer = $(document.createElement("div"));
  const tagMenuContainer = $(document.createElement("div"));
  const urlCountSpan = $(document.createElement("span"));
  const deleteTagButton = $(document.createElement("button"));

  container
    .addClass("tagFilter pointerable unselected col-12")
    .attr({
      "data-utub-tag-id": tagID,
      tabindex: 0,
    })
    .on("click.tagFilterSelected", function () {
      toggleTagFilterSelected(container);
    })
    .on("focus.tagFilterSelected", function () {
      container.offAndOn(
        "keyup.tagFilterSelected",
        function (event: JQuery.TriggeredEvent) {
          if (event.key === KEYS.ENTER && $(event.target).hasClass("tagFilter"))
            toggleTagFilterSelected(container);
        },
      );
    })
    .on("blur.tagFilterSelected", function () {
      container.off("keyup.tagFilterSelected");
    });

  tagStringSpan.text(tagString);

  tagCountContainer.addClass("tagCountWrap");
  tagMenuContainer.addClass("tagMenuWrap hidden");

  // Structured count: CSS shows "in view / total", the total alone, or nothing,
  // and no code parses the rendered text (see readTagCount/writeTagCount).
  urlCountSpan.addClass("tagAppliedToUrlsCount");
  urlCountSpan.append(
    $(document.createElement("span"))
      .addClass("tagCountInView")
      .text(String(urlCount)),
    $(document.createElement("span")).addClass("tagCountSep").text(" / "),
    $(document.createElement("span"))
      .addClass("tagCountTotal")
      .text(String(urlCount)),
  );

  deleteTagButton
    .addClass("utubTagBtnDelete align-center pointerable tabbable")
    .onExact("click.removeUtubTag", function () {
      deleteUTubTagShowModal(utubID, tagID, tagString);
    });

  deleteTagButton.append(createTagDeleteIcon(22));

  container.append(tagStringSpan);

  tagCountContainer.append(urlCountSpan);
  container.append(tagCountContainer);

  tagMenuContainer.append(deleteTagButton);
  container.append(tagMenuContainer);

  return container;
}

// Handle tag filtered selected - tags are filtered based on a URL having one tag AND another tag.. etc
export function toggleTagFilterSelected(activeTagFilter: JQuery): void {
  emit({ event: UI_EVENTS.UI_TAG_FILTER_TOGGLE });
  const tagID = parseInt(activeTagFilter.attr("data-utub-tag-id") as string);
  const currentSelectedTagIDs = getState().selectedTagIDs;
  const isSelected = activeTagFilter.hasClass("selected");

  log("toggleTagFilterSelected", {
    tagID,
    action: isSelected ? "unselect" : "select",
    selectedCountBefore: currentSelectedTagIDs.length,
  });

  // Prevent selecting more than the tag limit, under "all" only
  if (
    !isSelected &&
    effectiveTagDisplaySettings().tagMatchMode === "all" &&
    currentSelectedTagIDs.length >= APP_CONFIG.constants.TAGS_MAX_ON_URLS
  ) {
    log("toggleTagFilterSelected ignored — TAGS_MAX_ON_URLS reached", {
      currentlySelected: currentSelectedTagIDs.length,
    });
    return;
  }

  let selectedTagIDs: number[];
  if (isSelected) {
    // Unselect the tag, keeping everyone else's selection order
    if (currentSelectedTagIDs.length === 1) {
      // Unselecting would leave no tags selected, so disable 'unselectAll' button
      disableUnselectAllButtonAfterTagFilterRemoved();
    }
    activeTagFilter.addClass("unselected").removeClass("selected");
    selectedTagIDs = currentSelectedTagIDs.filter((id) => id !== tagID);
  } else {
    // Select the tag: selectedTagIDs is in click order
    activeTagFilter.removeClass("unselected").addClass("selected");
    if (currentSelectedTagIDs.length === 0) {
      // Selecting would select first tag, so enable 'unselectAll' button
      enableUnselectAllButtonAfterTagFilterApplied();
    }
    selectedTagIDs = [
      ...currentSelectedTagIDs.filter((id) => id !== tagID),
      tagID,
    ];
  }

  setState({ selectedTagIDs });
  syncTagCapState();
  updateURLsAndTagSubheaderWhenTagSelected();
}

/**
 * Derives the disabled/enabled state of the unselected chips from the cap rule:
 * disabled only under "all" with the selection at the limit. Idempotent, so every
 * site that can change the selection, the mode or the chip set just calls it.
 */
export function syncTagCapState(): void {
  const capReached =
    effectiveTagDisplaySettings().tagMatchMode === "all" &&
    getState().selectedTagIDs.length >= APP_CONFIG.constants.TAGS_MAX_ON_URLS;
  if (capReached) {
    disableUnselectedTagsAfterLimitReached();
  } else {
    enableUnselectedTagsAfterDisabledDueToLimit();
  }
}

export function enableUnselectedTagsAfterDisabledDueToLimit(): void {
  // Only chips the cap disabled: re-binding handlers on the others would stack
  // duplicate click handlers each time this runs.
  const unselectedTags = $(".tagFilter.unselected.disabled").removeClass(
    "disabled",
  );
  unselectedTags.each((_index, tag) => {
    $(tag)
      .on("click.tagFilterSelected", function (event: JQuery.TriggeredEvent) {
        if (!$(event.target).closest(".tagFilter").is(this)) return;
        toggleTagFilterSelected($(tag));
      })
      .offAndOn("focus.tagFilterSelected", function () {
        $(tag).on(
          "keyup.tagFilterSelected",
          function (event: JQuery.TriggeredEvent) {
            if (event.key === KEYS.ENTER) toggleTagFilterSelected($(tag));
          },
        );
      })
      .offAndOn("blur.tagFilterSelected", function () {
        $(tag).off("keyup.tagFilterSelected");
      })
      .attr({ tabindex: 0 });
  });
}

export function disableUnselectedTagsAfterLimitReached(): void {
  const unselectedTags = $(".tagFilter.unselected").addClass("disabled");
  unselectedTags.each((_index, tag) => {
    $(tag).off(".tagFilterSelected").attr({ tabindex: -1 });
  });
}

export function updateTagFilteringOnFindingStaleData(): void {
  // Update tag deck itself
  // Handle if new tags are added and the limit was already reached
  syncTagCapState();
  if ($(".tagFilter.selected").length === 0) {
    // Handle if all selected tags were removed
    disableUnselectAllButtonAfterTagFilterRemoved();
  }

  // Apply filters to URLs, either showing or hiding all if necessary
  updateURLsAndTagSubheaderWhenTagSelected();
}

export function updateTagFilteringOnURLOrURLTagDeletion(): void {
  const selectedTagsRemaining = $(".tagFilter.selected").length;

  switch (selectedTagsRemaining) {
    case 0: {
      // No tags left selected
      disableUnselectAllButtonAfterTagFilterRemoved();
      // Intentional fall-through: after removing, re-apply filters
    }
    default:
      // Reapply filters based on tag removed
      updateURLsAndTagSubheaderWhenTagSelected();
  }
}

// Deleting a tag or a stale-data prune shrinks the selection (and can add
// chips), so the cap state is re-derived from the final selection.
on(AppEvents.TAG_DELETED, () => syncTagCapState());
on(AppEvents.STALE_DATA_DETECTED, () => syncTagCapState());

export interface ModeChangeOutcome {
  filterResult: string | null;
  trimNotice: string | null;
}

const NO_OUTCOME: ModeChangeOutcome = Object.freeze({
  filterResult: null,
  trimNotice: null,
});

// The claim lets a caller (personal-settings-section `save()`) take over announcing a match-mode
// change made by one synchronous store write. Written only by
// `applyClaimingModeChange`, read by the handler during `fn`, and cleared by the
// helper's `finally`: the claim never spans an await.
let claimActive = false;
let claimedOutcome: ModeChangeOutcome = NO_OUTCOME;

/**
 * Runs `fn` (a synchronous store write) with the match-mode announcement claimed:
 * the handler records its filter-result and trim sentences instead of
 * announcing them, and they are returned here. A throwing `fn` still clears the
 * claim.
 */
export function applyClaimingModeChange(fn: () => void): ModeChangeOutcome {
  claimedOutcome = NO_OUTCOME;
  claimActive = true;
  const startMode = effectiveTagDisplaySettings().tagMatchMode;
  try {
    fn();
    // A write sequence that ends where it started changed nothing the user needs
    // a result for, but a trim that happened on the way is still reported.
    const returnedToStart =
      effectiveTagDisplaySettings().tagMatchMode === startMode;
    return returnedToStart
      ? { filterResult: null, trimNotice: claimedOutcome.trimNotice }
      : claimedOutcome;
  } finally {
    claimActive = false;
    claimedOutcome = NO_OUTCOME;
  }
}

function announceModeChange({ filterResult, trimNotice }: ModeChangeOutcome) {
  const sentences = [filterResult, trimNotice].filter(
    (sentence): sentence is string => sentence !== null,
  );
  if (sentences.length === 0) return;
  const message = sentences.join(". ");
  if (isPanelSettingsOpen()) {
    announceSettingsStatus({ message });
    return;
  }
  // One clear-then-set write so an identical repeated sentence is re-announced.
  $("#URLTagFilterAnnouncement").text("").text(message);
}

// any -> all with more than the cap selected: keep the first N in selection
// order and unselect the rest. Returns the trim sentence, or null if no trim.
function trimSelectionToCap(): string | null {
  const max = APP_CONFIG.constants.TAGS_MAX_ON_URLS;
  const selected = getState().selectedTagIDs;
  if (selected.length <= max) return null;
  selected.slice(max).forEach((tagID) => {
    $(`.tagFilter[data-utub-tag-id="${tagID}"]`)
      .removeClass("selected")
      .addClass("unselected");
  });
  setState({ selectedTagIDs: selected.slice(0, max) });
  return APP_CONFIG.strings.TAG_FILTER_TRIM_ANNOUNCEMENT;
}

function handleMatchModeChange(mode: TagMatchModeValue): void {
  // Order matters: trim and cap state first, then the filter pipeline runs once
  // over the final selection, then the sentences are built from its result.
  const trimNotice = mode === "all" ? trimSelectionToCap() : null;
  syncTagCapState();
  updateURLsAndTagSubheaderWhenTagSelected();
  const selectedCount = getState().selectedTagIDs.length;
  const filterResult =
    selectedCount >= 2
      ? tagFilterResultAnnouncement({ count: getNumOfVisibleURLs(), mode })
      : null;
  if (claimActive) {
    // Two flips in one claim keep the first trim notice and the latest result.
    claimedOutcome = {
      filterResult,
      trimNotice: claimedOutcome.trimNotice ?? trimNotice,
    };
    return;
  }
  announceModeChange({ filterResult, trimNotice });
}

// Baselines are (re)read from the store by `initTagMatchMode`, so importing this
// module never touches the store.
let lastMatchMode: TagMatchModeValue = "all";
let lastActiveUTubID: number | null = null;

let disposeMatchModeSubscription: (() => void) | null = null;

/**
 * One subscription on the resolved match mode (called once from main.ts). A UTub
 * switch only re-baselines it: the new UTub's override is not a user-driven mode
 * change. Idempotent; re-running re-baselines from the current store.
 */
export function initTagMatchMode(): void {
  disposeMatchModeSubscription?.();
  lastMatchMode = effectiveTagDisplaySettings().tagMatchMode;
  lastActiveUTubID = getState().activeUTubID;
  disposeMatchModeSubscription = subscribe((changedKeys) => {
    const mode = effectiveTagDisplaySettings().tagMatchMode;
    const { activeUTubID } = getState();
    const utubChanged = activeUTubID !== lastActiveUTubID;
    const modeChanged = mode !== lastMatchMode;
    lastActiveUTubID = activeUTubID;
    lastMatchMode = mode;
    if (utubChanged || !modeChanged) return;
    if (
      !changedKeys.includes("preferences") &&
      !changedKeys.includes("memberSettings")
    ) {
      return;
    }
    log("match mode changed", { mode });
    handleMatchModeChange(mode);
  });
}
