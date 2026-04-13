import { $ } from "../../lib/globals.js";
import { APP_CONFIG } from "../../lib/config.js";
import { KEYS } from "../../lib/constants.js";
import { filterUTubsByName } from "../../logic/utub-search.js";

type UTubSelectorEntry = { id: number; name: string };

function readUTubsFromDOM(): UTubSelectorEntry[] {
  return $.map($(".UTubSelector"), (el: HTMLElement) => ({
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

  let utubID: number;
  for (let index = 0; index < utubSelectors.length; index++) {
    utubID = parseInt($(utubSelectors[index]).attr("utubid")!);
    if (hideSet.has(utubID)) {
      $(utubSelectors[index]).addClass("hidden");
    } else {
      $(utubSelectors[index]).removeClass("hidden");
    }
  }
}

export function setUTubSelectorSearchEventListener(): void {
  const wrapper = $("#SearchUTubWrap");
  const searchIcon = $("#UTubSearchFilterIcon");
  const searchIconClose = $("#UTubSearchFilterIconClose");
  const searchInput = $("#UTubNameSearch");

  searchIcon.offAndOnExact("click.searchInputShow", function () {
    wrapper.addClass("visible").removeClass("hidden");
    $("#UTubDeckSubheader").addClass("hidden");
    searchIcon.addClass("hidden");
    searchIconClose.removeClass("hidden");

    setTimeout(() => {
      searchInput.addClass("utub-search-expanded");
    }, 0);

    searchInput.focus();
  });

  searchIconClose.offAndOnExact("click.searchInputClose", function () {
    closeUTubSearchAndEraseInput();
    searchInput.removeClass("utub-search-expanded");
  });

  searchInput
    .offAndOn("focus.searchInputEsc", function () {
      searchInput.offAndOn(
        "keydown.searchInputEsc",
        function (event: JQuery.TriggeredEvent) {
          if (event.key === KEYS.ESCAPE) {
            searchInput.blur();
            closeUTubSearchAndEraseInput();
            searchInput.removeClass("utub-search-expanded");
          }
        },
      );
    })
    .offAndOn("blur.searchInputEsc", function () {
      searchInput.off("keydown.searchInputEsc");
    })
    .offAndOn("input", function () {
      const searchTerm = (searchInput.val() as string).toLowerCase();
      if (searchTerm.length < APP_CONFIG.constants.UTUBS_MIN_NAME_LENGTH) {
        updatedUTubSelectorDisplay([]);
        return;
      }
      const filteredUTubIDsToHide = filterUTubsByName(
        readUTubsFromDOM(),
        searchTerm,
      );
      updatedUTubSelectorDisplay(filteredUTubIDsToHide);
    });
}

export function closeUTubSearchAndEraseInput(): void {
  $("#UTubSearchFilterIconClose").addClass("hidden");
  $("#UTubSearchFilterIcon").removeClass("hidden");
  $("#SearchUTubWrap").addClass("hidden").removeClass("visible");
  $("#UTubDeckSubheader").removeClass("hidden");
  $("#UTubNameSearch").val("");
  $(".UTubSelector").removeClass("hidden");
}
