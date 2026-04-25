import { $, getInputValue } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { filterUTubsByName } from "../../logic/utub-search.js";

type UTubSelectorEntry = { id: number; name: string };

function readUTubsFromDOM(): UTubSelectorEntry[] {
  return $.map($(".UTubSelector").toArray(), (el: HTMLElement) => ({
    id: parseInt($(el).attr("utubid")!),
    name: $(el).find(".UTubName").text(),
  }));
}

// Updates displayed UTub selectors based on the provided array
function updatedUTubSelectorDisplay(filteredUTubIDsToHide: number[]): void {
  if (filteredUTubIDsToHide.length === 0) {
    $(".UTubSelector").removeClass("hidden");
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
      searchInput.offAndOn(
        "keydown.searchInputEsc",
        function (event: JQuery.TriggeredEvent) {
          if (event.key === KEYS.ESCAPE) {
            searchInput.blur();
            resetUTubSearch();
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
      if (visibleCount === 0) {
        showUTubSearchNoResults();
      } else {
        hideUTubSearchNoResults();
        const totalCount = $(".UTubSelector").length;
        $("#UTubSearchAnnouncement").text(
          `${visibleCount} of ${totalCount} UTubs shown`,
        );
      }
    })
    .offAndOn("change", function () {
      if (getInputValue(searchInput) === "") {
        resetUTubSearch();
      }
    });
}

export function resetUTubSearch(): void {
  const searchInput = $("#UTubNameSearch");
  searchInput.val("");
  searchInput.off("keydown.searchInputEsc");
  $(".UTubSelector").removeClass("hidden");
  hideUTubSearchNoResults();
}

export function showUTubSearchBar(): void {
  $("#SearchUTubWrap").removeClass("hidden");
  $("#UTubDeckSubheader").addClass("hidden");
}

export function hideUTubSearchBar(): void {
  $("#SearchUTubWrap").addClass("hidden");
  $("#UTubDeckSubheader")
    .removeClass("hidden")
    .text(APP_CONFIG.strings.UTUB_CREATE_MSG);
  resetUTubSearch();
}
