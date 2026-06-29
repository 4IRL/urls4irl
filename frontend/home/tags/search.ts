import { $, getInputValue } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { emit } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { filterTagsByName } from "../../logic/tag-search.js";
import {
  TAG_SEARCH_CLOSE_TARGET,
  TAG_SEARCH_OPEN_TARGET,
} from "../../types/metrics-dim-values.js";

type TagSelectorEntry = { id: number; name: string };

let _tagSearchOpen: boolean = false;

// Takes the already-lowercased term as an argument (simpler than the DOM-read
// UTub pattern; both the input handler and reapplyTagFilter have `term` in
// scope when they call this).
export function isTagFilterActive(term: string): boolean {
  return term.length >= APP_CONFIG.constants.TAGS_MIN_LENGTH;
}

export function readTagsFromDOM(): TagSelectorEntry[] {
  return $.map($(".tagFilter").toArray(), (el: HTMLElement) => ({
    id: Number($(el).attr("data-utub-tag-id")),
    name: $(el).find("span").first().text(),
  }));
}

// Re-stripe the VISIBLE tag rows with the `.tag-stripe` class. The filter hides
// non-matching rows via `.hidden`; a CSS `:nth-child` rule would still count those
// hidden rows and misalign the stripes among the visible subset, so the visible
// rows are re-indexed here. The `.tag-stripe` class only paints under `.unselected`
// rows (selected/disabled keep their state background) — mirroring the prior
// nth-child rule, which alternated by row position regardless of state.
export function applyAlternatingTagBackground(): void {
  $("#listTags > .tagFilter")
    .not(".hidden")
    .each((visibleIndex, tagElem) => {
      $(tagElem).toggleClass("tag-stripe", visibleIndex % 2 === 1);
    });
}

// Toggle `.hidden` on tag rows by id. This is purely a text-visibility filter —
// it must NOT touch `.selected`/`.unselected`/`.disabled` or emit
// TAG_FILTER_CHANGED; a hidden row keeps its URL-filter contribution.
export function updatedTagFilterDisplay(filteredTagIDsToHide: number[]): void {
  if (filteredTagIDsToHide.length === 0) {
    $(".tagFilter").removeClass("hidden");
    applyAlternatingTagBackground();
    return;
  }
  const hideSet = new Set(filteredTagIDsToHide);
  const tagFilters = $(".tagFilter");

  tagFilters.each(function () {
    const tagID = Number($(this).attr("data-utub-tag-id"));
    if (hideSet.has(tagID)) {
      $(this).addClass("hidden");
    } else {
      $(this).removeClass("hidden");
    }
  });
  applyAlternatingTagBackground();
}

export function showTagSearchNoResults(): void {
  $("#TagSearchNoResults")
    .text(APP_CONFIG.strings.TAG_SEARCH_NO_RESULTS)
    .removeClass("hidden");
  $("#TagSearchAnnouncement").text(APP_CONFIG.strings.TAG_SEARCH_NO_RESULTS);
}

export function hideTagSearchNoResults(): void {
  $("#TagSearchNoResults").addClass("hidden").text("");
  $("#TagSearchAnnouncement").text("");
}

function applyTagFilterForTerm(searchTerm: string): void {
  if (!isTagFilterActive(searchTerm)) {
    updatedTagFilterDisplay([]);
    hideTagSearchNoResults();
    return;
  }
  const filteredTagIDsToHide = filterTagsByName(readTagsFromDOM(), searchTerm);
  updatedTagFilterDisplay(filteredTagIDsToHide);
  const visibleCount = $(".tagFilter").not(".hidden").length;
  if (visibleCount === 0) {
    showTagSearchNoResults();
  } else {
    hideTagSearchNoResults();
    const totalCount = $(".tagFilter").length;
    const announcement = APP_CONFIG.strings.TAG_SEARCH_COUNT_TEMPLATE.replace(
      "{{ visible }}",
      String(visibleCount),
    ).replace("{{ total }}", String(totalCount));
    $("#TagSearchAnnouncement").text(announcement);
  }
}

export function setTagSelectorSearchEventListener(): void {
  const searchInput = $("#TagNameSearch");

  searchInput
    .offAndOn("focus.searchInputEsc", function () {
      // A user directly focusing #TagNameSearch without clicking the funnel will
      // also emit — acceptable, since the input is only revealed after the
      // funnel is activated.
      if (!_tagSearchOpen) {
        _tagSearchOpen = true;
        emit({
          event: UI_EVENTS.UI_TAG_SEARCH_OPEN,
          target: TAG_SEARCH_OPEN_TARGET.TAGS,
        });
      }
      searchInput.offAndOn(
        "keydown.searchInputEsc",
        function (event: JQuery.TriggeredEvent) {
          if (event.key === KEYS.ESCAPE) {
            closeTagNameFilter();
            searchInput.blur();
            // Return focus to the funnel toggle, but only if it is visible.
            // openUTubTagBtnMenuOnUTubTags() calls closeTagNameFilter() while
            // #TagNameSearch has focus in edit-all-tags mode, where the funnel
            // button is hidden; focusing a display:none element is a browser
            // no-op that silently loses keyboard focus, so skip it.
            const filterBtn = $("#tagNameFilterBtn");
            if (!filterBtn.hasClass("hidden")) {
              filterBtn.trigger("focus");
            }
          }
        },
      );
    })
    .offAndOn("blur.searchInputEsc", function () {
      _tagSearchOpen = false;
      searchInput.off("keydown.searchInputEsc");
    })
    .offAndOn("input", function () {
      const searchTerm = getInputValue(searchInput).toLowerCase();
      applyTagFilterForTerm(searchTerm);
    });
}

export function resetTagFilter(): void {
  if (_tagSearchOpen) {
    emit({
      event: UI_EVENTS.UI_TAG_SEARCH_CLOSE,
      target: TAG_SEARCH_CLOSE_TARGET.TAGS,
    });
    _tagSearchOpen = false;
  }
  const searchInput = $("#TagNameSearch");
  searchInput.val("");
  searchInput.off("keydown.searchInputEsc");
  $(".tagFilter").removeClass("hidden");
  applyAlternatingTagBackground();
  hideTagSearchNoResults();
}

// Re-apply the active filter term after a #listTags append so newly-added rows
// obey the current filter. Identical logic to the input handler's path.
export function reapplyTagFilter(): void {
  // Append sites call this from contexts where #TagNameSearch may not be in the
  // DOM (e.g. URL-tag renders before the tag deck is built); a missing input
  // yields no value, which means "no active filter" — show all rows.
  const searchTerm = (getInputValue($("#TagNameSearch")) ?? "").toLowerCase();
  applyTagFilterForTerm(searchTerm);
}

export function openTagNameFilter(): void {
  $("#TagDeck").addClass("tag-search-open");
  $("#tagNameFilterBtn").addClass("hidden").attr("aria-expanded", "true");
  $("#tagNameFilterBtnClose").removeClass("hidden");
  $("#TagNameSearch").trigger("focus");
}

// Collapse the filter back to the funnel-only state and clear any active filter.
// The open state is read from the DOM class (not the focus flag) because the X
// button blurs the input first — clearing _tagSearchOpen before this handler
// runs — so a flag-only check would silently drop the close on the X path.
export function closeTagNameFilter(): void {
  const wasOpen = $("#TagDeck").hasClass("tag-search-open");
  $("#TagDeck").removeClass("tag-search-open");
  $("#tagNameFilterBtnClose").addClass("hidden");
  $("#tagNameFilterBtn").removeClass("hidden").attr("aria-expanded", "false");
  if (wasOpen) {
    emit({
      event: UI_EVENTS.UI_TAG_SEARCH_CLOSE,
      target: TAG_SEARCH_CLOSE_TARGET.TAGS,
    });
    // Suppress resetTagFilter's own CLOSE emit so the hide is recorded once
    // (the Escape path reaches here with the input still focused / flag set).
    _tagSearchOpen = false;
  }
  resetTagFilter();
}

export function setTagNameFilterToggleListeners(): void {
  $("#tagNameFilterBtn").offAndOnExact(
    "click.tagNameFilterShow",
    openTagNameFilter,
  );
  $("#tagNameFilterBtnClose").offAndOnExact(
    "click.tagNameFilterClose",
    closeTagNameFilter,
  );
}

// Reveal the funnel toggle for the selected UTub and start collapsed. Unlike
// showUTubSearchBar, this does NOT remove `.hidden` from #SearchTagWrap (the CSS
// gate `#TagDeck:not(.tag-search-open) #SearchTagWrap` is the sole visibility
// controller) and there is no subheader to hide.
export function showTagFilterBar(): void {
  $("#tagNameFilterBtn").removeClass("hidden");
  closeTagNameFilter();
}

// Hide the funnel/X toggles and collapse the filter. Does NOT manipulate
// `.hidden` on #SearchTagWrap — the CSS state-class gate handles its visibility.
export function hideTagFilterBar(): void {
  $("#tagNameFilterBtn").addClass("hidden");
  $("#tagNameFilterBtnClose").addClass("hidden");
  $("#TagDeck").removeClass("tag-search-open");
  resetTagFilter();
}
