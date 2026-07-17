import { $, getInputValue } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { emit } from "../../lib/metrics-client.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { filterUTubsByName } from "../../logic/utub-search.js";
import {
  UTUB_SEARCH_CLOSE_TARGET,
  UTUB_SEARCH_OPEN_TARGET,
} from "../../types/metrics-dim-values.js";
import { debug } from "../../lib/debug.js";

const log = debug("utubs");

type UTubSelectorEntry = { id: number; name: string };

let _utubSearchOpen: boolean = false;

export function isUTubSearchActive(): boolean {
  const value = $("#UTubNameSearch").val();
  return (
    typeof value === "string" &&
    value.trim().length >= APP_CONFIG.constants.UTUBS_MIN_NAME_LENGTH
  );
}

function readUTubsFromDOM(): UTubSelectorEntry[] {
  return $.map($(".UTubSelector").toArray(), (el: HTMLElement) => ({
    id: parseInt($(el).attr("utubid")!),
    name: $(el).find(".UTubName").text(),
  }));
}

// Re-stripe the VISIBLE UTub selectors with alternating `.even`/`.odd` classes.
// The name filter hides non-matching rows via the `.hidden` class; a CSS
// `:nth-child` rule would still count those hidden rows and misalign the stripes
// among the visible subset, so the visible rows are re-indexed here instead.
// Mirrors reapplyAlternatingURLCardBackgroundAfterFilter for the URL deck. Called
// after every structural change (build/create/delete) and every filter show/hide.
export function applyAlternatingUTubSelectorBackground(): void {
  const visibleSelectors = $("#listUTubs > .UTubSelector").not(".hidden");
  visibleSelectors.each((index, utubSelectorElem) => {
    $(utubSelectorElem)
      .removeClass("odd even")
      .addClass(index % 2 === 0 ? "even" : "odd");
  });
}

// Updates displayed UTub selectors based on the provided array
function updatedUTubSelectorDisplay(filteredUTubIDsToHide: number[]): void {
  if (filteredUTubIDsToHide.length === 0) {
    $(".UTubSelector").removeClass("hidden");
    applyAlternatingUTubSelectorBackground();
    return;
  }
  const hideSet = new Set(filteredUTubIDsToHide);
  const utubSelectors = $(".UTubSelector");

  for (let index = 0; index < utubSelectors.length; index++) {
    const utubID = parseInt($(utubSelectors[index]).attr("utubid")!);
    if (hideSet.has(utubID)) {
      $(utubSelectors[index]).addClass("hidden");
    } else {
      $(utubSelectors[index]).removeClass("hidden");
    }
  }
  applyAlternatingUTubSelectorBackground();
}

function showUTubSearchNoResults(): void {
  $("#UTubSearchNoResults")
    .text(APP_CONFIG.strings.UTUB_SEARCH_NO_RESULTS)
    .removeClass("hidden");
  $("#UTubSearchAnnouncement").text(APP_CONFIG.strings.UTUB_SEARCH_NO_RESULTS);
}

function hideUTubSearchNoResults(): void {
  $("#UTubSearchNoResults").addClass("hidden").text("");
  $("#UTubSearchAnnouncement").text("");
}

export function setUTubSelectorSearchEventListener(): void {
  const searchInput = $("#UTubNameSearch");

  searchInput
    .offAndOn("focus.searchInputEsc", function () {
      if (!_utubSearchOpen) {
        _utubSearchOpen = true;
        emit({
          event: UI_EVENTS.UI_UTUB_SEARCH_OPEN,
          target: UTUB_SEARCH_OPEN_TARGET.UTUBS,
        });
      }
      searchInput.offAndOn(
        "keydown.searchInputEsc",
        function (event: JQuery.TriggeredEvent) {
          if (event.key === KEYS.ESCAPE) {
            closeUTubNameFilter();
            searchInput.blur();
            const firstVisibleSelector = $(".UTubSelector")
              .not(".hidden")
              .first();
            if (firstVisibleSelector.length > 0) {
              firstVisibleSelector.trigger("focus");
            } else {
              $("#memberBtnCreate").trigger("focus");
            }
          }
        },
      );
    })
    .offAndOn("blur.searchInputEsc", function () {
      _utubSearchOpen = false;
      searchInput.off("keydown.searchInputEsc");
    })
    .offAndOn("input", function () {
      const searchTerm = getInputValue(searchInput).toLowerCase();
      if (searchTerm.length < APP_CONFIG.constants.UTUBS_MIN_NAME_LENGTH) {
        updatedUTubSelectorDisplay([]);
        hideUTubSearchNoResults();
        return;
      }
      const filteredUTubIDsToHide = filterUTubsByName(
        readUTubsFromDOM(),
        searchTerm,
      );
      updatedUTubSelectorDisplay(filteredUTubIDsToHide);
      const visibleCount = $(".UTubSelector").not(".hidden").length;
      log("UTub search applied", {
        searchTerm,
        hidCount: filteredUTubIDsToHide.length,
        visibleCount,
        totalCount: $(".UTubSelector").length,
      });
      if (visibleCount === 0) {
        showUTubSearchNoResults();
      } else {
        hideUTubSearchNoResults();
        const totalCount = $(".UTubSelector").length;
        const announcement =
          APP_CONFIG.strings.UTUB_SEARCH_COUNT_TEMPLATE.replace(
            "{{ visible }}",
            String(visibleCount),
          ).replace("{{ total }}", String(totalCount));
        $("#UTubSearchAnnouncement").text(announcement);
      }
    })
    .offAndOn("change", function () {
      if (getInputValue(searchInput) === "") {
        resetUTubSearch();
      }
    });
}

export function resetUTubSearch(): void {
  if (_utubSearchOpen) {
    emit({
      event: UI_EVENTS.UI_UTUB_SEARCH_CLOSE,
      target: UTUB_SEARCH_CLOSE_TARGET.UTUBS,
    });
    _utubSearchOpen = false;
  }
  const searchInput = $("#UTubNameSearch");
  searchInput.val("");
  searchInput.off("keydown.searchInputEsc");
  $(".UTubSelector").removeClass("hidden");
  applyAlternatingUTubSelectorBackground();
  hideUTubSearchNoResults();
}

// Reveal the UTub-name filter input (desktop). On mobile the input is always
// visible (CSS) and the toggle buttons are hidden, so this is desktop-only in
// practice. Focus emits UI_UTUB_SEARCH_OPEN via the input's focus handler.
export function openUTubNameFilter(): void {
  $("#UTubDeck").addClass("utub-search-open");
  $("#utubNameFilterBtn").addClass("hidden").attr("aria-expanded", "true");
  $("#utubNameFilterBtnClose").removeClass("hidden");
  $("#UTubNameSearch").trigger("focus");
}

// Collapse the filter back to the funnel-only state and clear any active filter.
// Emits UI_UTUB_SEARCH_CLOSE for the funnel hide. The open state is read from the
// DOM (`utub-search-open`), not the focus flag, because clicking the X button
// blurs the input first — which clears _utubSearchOpen before this handler runs —
// so a flag-only check would silently drop the close on the X-button path.
export function closeUTubNameFilter(): void {
  const wasOpen = $("#UTubDeck").hasClass("utub-search-open");
  $("#UTubDeck").removeClass("utub-search-open");
  $("#utubNameFilterBtnClose").addClass("hidden");
  $("#utubNameFilterBtn").removeClass("hidden").attr("aria-expanded", "false");
  if (wasOpen) {
    emit({
      event: UI_EVENTS.UI_UTUB_SEARCH_CLOSE,
      target: UTUB_SEARCH_CLOSE_TARGET.UTUBS,
    });
    // Suppress resetUTubSearch's own CLOSE emit so the hide is recorded once
    // (the Escape path reaches here with the input still focused / flag set).
    _utubSearchOpen = false;
  }
  resetUTubSearch();
}

export function setUTubNameFilterToggleListeners(): void {
  $("#utubNameFilterBtn").offAndOnExact(
    "click.utubNameFilterShow",
    openUTubNameFilter,
  );
  $("#utubNameFilterBtnClose").offAndOnExact(
    "click.utubNameFilterClose",
    closeUTubNameFilter,
  );
}

export function showUTubSearchBar(): void {
  $("#SearchUTubWrap").removeClass("hidden");
  $("#UTubDeckSubheader").addClass("hidden");
  // Reveal the funnel toggle and start collapsed (the desktop CSS keeps the
  // input hidden until the toggle opens it; mobile shows it regardless).
  $("#utubNameFilterBtn").removeClass("hidden");
  closeUTubNameFilter();
}

export function hideUTubSearchBar(): void {
  $("#SearchUTubWrap").addClass("hidden");
  $("#UTubDeckSubheader")
    .removeClass("hidden")
    .text(APP_CONFIG.strings.UTUB_CREATE_MSG);
  $("#utubNameFilterBtn").addClass("hidden");
  $("#utubNameFilterBtnClose").addClass("hidden");
  $("#UTubDeck").removeClass("utub-search-open");
  resetUTubSearch();
}
