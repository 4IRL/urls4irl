import type { UtubTag } from "../../types/url.js";

import { debug } from "../../lib/debug.js";
import { on, AppEvents } from "../../lib/event-bus.js";
import { $ } from "../../lib/globals.js";
import { hideTooltip } from "../../lib/tooltips.js";
import { applyDeckDiff } from "../../logic/apply-deck-diff.js";
import { getState } from "../../store/app-store.js";
import {
  createUTubTagHideInput,
  removeCreateUTubTagEventListeners,
  resetCreateUTubTagFailErrors,
  resetNewUTubTagForm,
  setupOpenCreateUTubTagEventListeners,
} from "./create.js";
import {
  applyAlternatingTagBackground,
  hideTagFilterBar,
  reapplyTagFilter,
  resetTagFilter,
  setTagNameFilterToggleListeners,
  setTagSelectorSearchEventListener,
  showTagFilterBar,
} from "./search.js";
import { hideTagDeckEmptyState, showTagDeckEmptyState } from "./empty-state.js";
import { buildTagFilterInDeck } from "./tags.js";
import {
  closeUTubTagBtnMenuOnUTubTags,
  setTagDeckBtnsOnUpdateAllUTubTagsClosed,
  setUnselectUpdateUTubTagEventListeners,
} from "./update-all.js";
import { disableUnselectAllButtonAfterTagFilterRemoved } from "./unselect-all.js";
import { collapsedTagFilterAnnouncement, tagFilterPillLabel } from "./utils.js";

const log = debug("tags");

const TAG_DECK_SELECTOR = "#TagDeck";
const TAG_FILTER_PILL_SELECTOR = "#TagDeckFilterPill";
const TAG_FILTER_PILL_LABEL_SELECTOR = "#TagDeckFilterPillLabel";
const COLLAPSED_FILTER_ANNOUNCEMENT_SELECTOR =
  "#TagDeckCollapsedFilterAnnouncement";
const FILTERING_CLASS = "filtering";

// A collapsed Tag deck hides the chips that carry "a filter is applied", so the
// header-band pill carries it instead. Cleared wholesale rather than toggled:
// TAG_FILTER_CHANGED is never emitted on a UTub switch (its only emit site is
// `urls/cards/filtering.ts`), so without an explicit reset a stale count — and a
// stale announcement — would survive into the next UTub's collapsed state.
function resetTagFilterPill(): void {
  $(TAG_FILTER_PILL_SELECTOR).removeClass(FILTERING_CLASS);
  $(TAG_FILTER_PILL_LABEL_SELECTOR).text("");
  $(COLLAPSED_FILTER_ANNOUNCEMENT_SELECTOR).text("");
}

export function setTagDeckOnUTubSelected(
  dictTags: UtubTag[],
  utubID: number,
): void {
  log("setTagDeckOnUTubSelected — rebuilding tag deck", {
    utubID,
    tagCount: dictTags.length,
  });
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
    hideTagDeckEmptyState();
  } else {
    showTagDeckEmptyState();
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

  refreshTagDeckTagCount();

  // Stripe the freshly-built rows (mirrors the member deck build).
  applyAlternatingTagBackground();

  setTagSelectorSearchEventListener();
  setTagNameFilterToggleListeners();
  showTagFilterBar();

  $("#utubTagBtnCreate").showClassNormal();
}

export function resetTagDeck(): void {
  $("#listTags").empty();
  refreshTagDeckTagCount();
  disableUnselectAllButtonAfterTagFilterRemoved();
  $("#utubTagBtnCreate").hideClass();
  // This button is hidden by callers rather than by its own click, so hide any
  // open hover tooltip here or the bubble lingers detached over the deck.
  hideTooltip($("#unselectAllTagFilters")[0]);
  $("#unselectAllTagFilters").hideClass();
  $("#utubTagBtnUpdateAllOpen").hideClass();
  createUTubTagHideInput();
  closeUTubTagBtnMenuOnUTubTags();
  setTagDeckBtnsOnUpdateAllUTubTagsClosed();
  hideTagDeckEmptyState();
  resetTagFilter();
  resetTagFilterPill();
  hideTagFilterBar();
}

export function resetTagDeckIfNoUTubSelected(): void {
  $("#listTags").empty();
  $("#createUTubTagWrap").hideClass();
  $("#utubTagBtnCreate").hideClass();
  // Same detached-bubble guard as resetTagDeck() above.
  hideTooltip($("#unselectAllTagFilters")[0]);
  $("#unselectAllTagFilters").hideClass();
  setTagDeckBtnsOnUpdateAllUTubTagsClosed();
  $("#utubTagBtnUpdateAllOpen").hideClass();
  removeCreateUTubTagEventListeners();
  resetCreateUTubTagFailErrors();
  resetNewUTubTagForm();
  hideTagDeckEmptyState();
  resetTagFilter();
  // Reached from setUIWhenNoUTubSelected(), which is how a user leaves a
  // filtered UTub (deleting it, or backing out). The Tag deck is locked
  // minimized in that state, so a stale pill would be the only thing visible.
  resetTagFilterPill();
  hideTagFilterBar();
}

// Update tags in LH panel based on asynchronous updates or stale data
export function updateTagDeck(updatedTags: UtubTag[], utubID: number): void {
  log("updateTagDeck — applying tag deck diff", {
    utubID,
    oldCount: getState().tags.length,
    newCount: updatedTags.length,
  });
  applyDeckDiff<UtubTag>({
    oldItems: getState().tags,
    newItems: updatedTags,
    getID: (tag) => tag.id,
    removeElement: (tagID) =>
      $(".tagFilter[data-utub-tag-id=" + tagID + "]").remove(),
    addElement: (tag) => {
      $("#listTags").append(
        buildTagFilterInDeck(utubID, tag.id, tag.tagString),
      );
    },
  });

  // Covers both halves of the diff — rows added and rows removed.
  refreshTagDeckTagCount();

  reapplyTagFilter();
  if (updatedTags.length === 0) {
    showTagDeckEmptyState();
  } else {
    hideTagDeckEmptyState();
  }
}

export function setTagDeckSubheaderWhenNoUTubSelected(): void {
  $("#TagDeckCount").text("");
}

// Inline "(n)" total of the UTub's tags, next to the deck title. Derived from
// the rendered rows rather than from the store so it can never drift from what
// the user is actually looking at — and so a collapsed Tag deck, whose "no tags
// yet" empty state lives inside the hidden .content, still reads as empty.
export function refreshTagDeckTagCount(): void {
  $("#TagDeckCount").text("(" + $("#listTags > .tagFilter").length + ")");
}

export function removeTagFromTagDeckGivenTagID(tagID: number): void {
  $(".tagFilter[data-utub-tag-id=" + tagID + "]").remove();
  refreshTagDeckTagCount();
}

on(AppEvents.UTUB_SELECTED, ({ tags, utubID }) =>
  setTagDeckOnUTubSelected(tags, utubID),
);
on(AppEvents.STALE_DATA_DETECTED, ({ tags, utubID }) =>
  updateTagDeck(tags, utubID),
);

// Collapsed-state tag-filter indicator. Registered once here at module scope —
// never inside a per-UTub builder — so it can never accumulate duplicate
// handlers across UTub switches (same reasoning as `tags/sheet.ts`'s
// handle-count badge subscriber).
on(AppEvents.TAG_FILTER_CHANGED, ({ selectedTagIDs }) => {
  const count = selectedTagIDs.length;
  $(TAG_FILTER_PILL_SELECTOR).toggleClass(FILTERING_CLASS, count > 0);
  $(TAG_FILTER_PILL_LABEL_SELECTOR).text(tagFilterPillLabel(count));
  // The pill only exists to be seen while collapsed (Design Decision 4), so the
  // announcement fires on the same condition: an expanded deck already exposes
  // filter state through the chips themselves, and re-announcing it there on
  // every filter change would be redundant screen-reader chatter.
  const isCollapsed = $(TAG_DECK_SELECTOR).hasClass("collapsed");
  $(COLLAPSED_FILTER_ANNOUNCEMENT_SELECTOR).text(
    isCollapsed ? collapsedTagFilterAnnouncement(count) : "",
  );
});
