import type { UtubTag, UtubUrlItem } from "../../../types/url.js";

import { $ } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { AppEvents, emit as emitAppEvent } from "../../../lib/event-bus.js";
import { disposeTooltipsWithin } from "../../../lib/tooltips.js";
import { getState, setState } from "../../../store/app-store.js";
import { isATagSelected } from "../../tags/utils.js";
import { getNumOfVisibleURLs } from "../utils.js";
import { createURLBlock } from "./cards.js";
import { selectURLCard } from "./selection.js";
import { triggerURLSwipeNudgeIfEligible } from "./swipe.js";
import { updateColorOfFollowingURLCardsAfterURLCreated } from "./utils.js";
import {
  applyDefaultUrlSort,
  reapplyAlternatingURLCardBackgroundAfterFilter,
  updateTagFilteringOnURLOrURLTagDeletion,
  updateURLsAndTagSubheaderWhenTagSelected,
} from "./filtering.js";
import { renderAppliedTagsForUrl } from "../tags/tag-render.js";
import {
  closeURLSearchAndEraseInput,
  hideURLSearchIcon,
  showURLSearchIcon,
} from "../search.js";
import { showURLsEmptyState } from "../empty-state.js";
import { effectiveSort } from "../view-settings.js";

// Shared URL-deck mutations: inserting a freshly-materialised card (a create, or
// a revive that brings a trashed URL back) and removing a card (a delete, or the
// edited card a revive-on-edit replaces). Kept in one place so both flows sync
// the store, the tag deck counts, striping and sort identically.

/**
 * Inserts a URL's card at the top of the deck and syncs the store, tag deck,
 * visibility, selection, sort position and search.
 *
 * Returns the new card so the caller can anchor a banner to it. A tag filter that
 * hides the card leaves selection untouched.
 */
export function insertURLCardIntoDeck({
  newUrl,
  utubID,
  appliedTags,
  announce,
  select = true,
}: {
  newUrl: UtubUrlItem;
  utubID: number;
  appliedTags: UtubTag[];
  announce: boolean;
  select?: boolean;
}): JQuery {
  // A background refresh may already have rendered this URL before the create
  // response landed: never duplicate the card, and skip every other side effect.
  const existingCard = $(".urlRow[utuburlid=" + newUrl.utubUrlID + "]");
  if (existingCard.length > 0) return existingCard;

  // Capture visible-URL count BEFORE DOM insertion (drives alternating stripes).
  const currentNumOfURLs = getNumOfVisibleURLs();

  // Single combined store append with the complete entry (incl. tag IDs).
  setState({
    urls: [...getState().urls, newUrl],
  });
  // Notify the onboarding nudge system (and any future url-deck consumer) that
  // the deck's URL set changed, so it can re-arm/re-show the Add-URL tip.
  emitAppEvent(AppEvents.URL_DECK_CHANGED);

  const newUrlCard = createURLBlock({
    url: newUrl,
    dictTags: [], // Mimics an empty array of tags to match against
    utubID,
  }).addClass("even");

  newUrlCard.insertAfter($("#createURLWrap"));

  if (currentNumOfURLs !== 0) {
    updateColorOfFollowingURLCardsAfterURLCreated();
  }

  // Render any tags applied onto the now-attached card and sync the tag deck
  // (badges, deck filters, #unselectAllTagFilters, #utubTagBtnUpdateAllOpen).
  renderAppliedTagsForUrl({
    appliedTags,
    utubUrlTagIDs: newUrl.utubUrlTagIDs,
    urlCard: newUrlCard,
    utubID,
  });

  // Re-evaluate visibility for all URLs (incl. the new one): a URL with tags
  // matching the active filter stays visible; non-matching ones are hidden.
  updateURLsAndTagSubheaderWhenTagSelected();

  // Auto-select the new card only when no filter would suppress it and the
  // caller wants it (a bulk re-insert must not select, or it would clear banners).
  if (select && !isATagSelected()) {
    selectURLCard(newUrlCard);
  }

  reorderURLCardBySortPreference({ newUrl, newUrlCard, announce });

  closeURLSearchAndEraseInput();
  showURLSearchIcon();

  return newUrlCard;
}

// DD-36's sanctioned client-side visual exception: the ONLY place the client
// re-sorts URLs. The deck is server-ordered on every full load; here we merely
// keep the newly inserted or revived card from visually contradicting the
// effective sort (the member's per-UTub override, else the Display default) for
// the brief pre-refetch window. A sort change itself is applied from the server's
// order (`syncDeckOrderToServer`), never by a client re-sort. Detaches/re-appends the URL cards into #listURLs in
// the stored sort order (the detach/re-append idiom sortTagFiltersInPlace uses),
// then — only when the reorder actually relocated the new card away from its
// top-of-list insertion point — scrolls it into view and announces the add.
function reorderURLCardBySortPreference({
  newUrl,
  newUrlCard,
  announce,
}: {
  newUrl: UtubUrlItem;
  newUrlCard: JQuery;
  announce: boolean;
}): void {
  const HIGHLIGHT_CLASS = "url-card-created-highlight";
  const HIGHLIGHT_DURATION_MS = 700;

  const storedSortOrder = effectiveSort();
  const sortedURLIDs = applyDefaultUrlSort(
    getState().urls,
    storedSortOrder,
  ).map((sortedURL) => sortedURL.utubUrlID);
  const listURLs = $("#listURLs");
  sortedURLIDs.forEach((sortedURLID) => {
    listURLs.append($(`.urlRow[utuburlid=${sortedURLID}]`).detach());
  });
  // The detach/re-append changes DOM order, so the alternating even/odd stripe
  // classes (assigned by the pre-reorder order) are now stale — recompute them
  // against the new order so striping stays consistent in the pre-refetch window.
  reapplyAlternatingURLCardBackgroundAfterFilter();

  // Transient background flash on the newly inserted or revived card (distinct from the
  // persistent urlSelected styling), removed after ~0.7s — mirrors
  // showURLDeckBannerError()'s setTimeout-driven class removal.
  newUrlCard.addClass(HIGHLIGHT_CLASS);
  setTimeout(() => {
    newUrlCard.removeClass(HIGHLIGHT_CLASS);
  }, HIGHLIGHT_DURATION_MS);

  // The reorder relocated the new card iff it is no longer the first sorted URL.
  // A no-op top insert (e.g. the default newest sort) needs neither a scroll nor
  // an announcement — the card lands visibly at the top of the deck and is
  // auto-selected; the polite announcement is reserved for the relocate case,
  // where the card can move off-screen and most needs the SR cue.
  const reorderMovedNewCard = sortedURLIDs[0] !== newUrl.utubUrlID;
  if (reorderMovedNewCard) {
    newUrlCard[0].scrollIntoView({
      behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "auto"
        : "smooth",
      block: "center",
    });
    if (announce) {
      $("#fieldSavedAnnouncement").text(
        APP_CONFIG.strings.URL_ADDED_ANNOUNCEMENT,
      );
    }
  }

  // Swipe-nudge fires LAST so its viewport-visibility check reads the card's
  // final sorted/scrolled position rather than its transient top-of-list insert.
  triggerURLSwipeNudgeIfEligible({ urlRow: newUrlCard });
}

/**
 * Where focus should land after `urlCard` leaves the deck: the next visible row,
 * else the previous visible row, else the empty state (the card is the only row)
 * or the deck itself (every remaining row is hidden). Compute it BEFORE removal.
 */
export function focusTargetAfterURLRowRemoval({
  urlCard,
}: {
  urlCard: JQuery;
}): JQuery {
  // Rows still fading out from an earlier delete are about to detach.
  const visibleRows = $("#listURLs .urlRow")
    .not('[filterable="false"],[searchable="false"]')
    .not(":animated");
  const index = visibleRows.index(urlCard);
  const nextRow = visibleRows.eq(index + 1);
  if (index >= 0 && nextRow.length > 0) return nextRow;
  if (index > 0) return visibleRows.eq(index - 1);
  if ($("#listURLs .urlRow").length === 1) return $("#noURLsEmptyState");
  return $("#URLDeck");
}

/**
 * Removes a URL's card from the deck: drops it from the store, decrements the
 * visible/total count of every tag it carried, then detaches the card and
 * re-syncs the empty state / filtering.
 *
 * `animate` fades the card out (a user delete); without it the card is removed
 * in the same tick (a revive-on-edit, where the replacing card lands at once).
 */
export function removeURLCardFromDeck({
  urlCard,
  utubUrlID,
  animate,
  onRemoved,
}: {
  urlCard: JQuery;
  utubUrlID: number;
  animate: boolean;
  onRemoved?: () => void;
}): void {
  setState({
    urls: getState().urls.filter(
      (url: UtubUrlItem) => url.utubUrlID !== utubUrlID,
    ),
  });
  // Notify the onboarding nudge system (and any future url-deck consumer) that
  // the deck's URL set changed, so it can re-arm/re-show the Add-URL tip.
  emitAppEvent(AppEvents.URL_DECK_CHANGED);
  const currentURLTagIDs = urlCard.attr("data-utub-url-tag-ids") || "";
  if (currentURLTagIDs.trim()) {
    const tagIDs = currentURLTagIDs.split(",").map((part) => part.trim());
    let tagCountElem: JQuery;
    let tagID: string;
    let tagCountText: string[];
    for (let tagIdIndex = 0; tagIdIndex < tagIDs.length; tagIdIndex++) {
      tagID = tagIDs[tagIdIndex];
      tagCountElem = $(
        `.tagFilter[data-utub-tag-id=${tagID}]` + " .tagAppliedToUrlsCount",
      );
      tagCountText = tagCountElem.text().split(" / ");
      if (!tagCountText || tagCountText.length !== 2) continue;
      tagCountElem.text(
        `${parseInt(tagCountText[0]) - 1}` +
          " / " +
          `${parseInt(tagCountText[1]) - 1}`,
      );
    }
  }

  const detachCard = (): void => {
    // Tear down the card's own tooltips (and its tag badges') before detaching —
    // Bootstrap's instance map would otherwise pin the whole subtree.
    disposeTooltipsWithin(urlCard);
    urlCard.remove();
    if ($("#listURLs .urlRow").length === 0) {
      showURLsEmptyState();
      hideURLSearchIcon();
    } else {
      updateTagFilteringOnURLOrURLTagDeletion();
    }
    onRemoved?.();
  };

  if (animate) {
    urlCard.fadeOut("slow", detachCard);
  } else {
    detachCard();
  }
}
