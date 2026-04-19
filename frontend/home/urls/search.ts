import { $, getInputValue } from "../../lib/globals.js";
import { KEYS } from "../../lib/constants.js";
import { APP_CONFIG } from "../../lib/config.js";
import { AppEvents, emit, on } from "../../lib/event-bus.js";
import { filterURLsBySearchTerm } from "../../logic/url-search.js";

type URLDOMEntry = { id: number; title: string; urlString: string };

function readURLsFromDOM(): URLDOMEntry[] {
  return $.map($(".urlRow[filterable=true]").toArray(), (el: HTMLElement) => ({
    id: parseInt($(el).attr("utuburlid")!),
    title: $(el).find(".urlTitle").text(),
    urlString: $(el).find(".urlString").attr("href")!,
  }));
}

function updateURLCardSearchVisibility(urlIDsToHide: number[]): void {
  const filterableRows = $(".urlRow[filterable=true]");

  if (urlIDsToHide.length === 0) {
    filterableRows.attr("searchable", "true");
    emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);
    return;
  }

  const hideSet = new Set(urlIDsToHide);

  for (let index = 0; index < filterableRows.length; index++) {
    const row = $(filterableRows[index]);
    const urlID = parseInt(row.attr("utuburlid")!);
    row.attr("searchable", hideSet.has(urlID) ? "false" : "true");
  }

  emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);
}

export function setURLSearchEventListener(): void {
  const wrapper = $("#SearchURLWrap");
  const searchIcon = $("#urlSearchFilterIcon");
  const searchIconClose = $("#urlSearchFilterIconClose");
  const searchInput = $("#URLContentSearch");

  searchIcon.offAndOnExact("click.urlSearchInputShow", function () {
    wrapper.addClass("visible").removeClass("hidden");
    $("#UTubDescriptionSubheaderWrap").addClass("hidden");
    searchIcon.addClass("hidden");
    searchIconClose.removeClass("hidden");

    setTimeout(() => {
      searchInput.addClass("url-search-expanded");
    }, 0);

    searchInput.focus();
  });

  searchIconClose.offAndOnExact("click.urlSearchInputClose", function () {
    closeURLSearchAndEraseInput();
    searchInput.removeClass("url-search-expanded");
  });

  searchInput
    .offAndOn("focus.searchInputEsc", function () {
      searchInput.offAndOn(
        "keydown.searchInputEsc",
        function (event: JQuery.TriggeredEvent) {
          if (event.key === KEYS.ESCAPE) {
            searchInput.blur();
            closeURLSearchAndEraseInput();
            searchInput.removeClass("url-search-expanded");
          }
        },
      );
    })
    .offAndOn("blur.searchInputEsc", function () {
      searchInput.off("keydown.searchInputEsc");
    })
    .offAndOn("input", function () {
      const searchTerm = getInputValue(searchInput);
      if (searchTerm.length < APP_CONFIG.constants.URLS_MIN_LENGTH) {
        updateURLCardSearchVisibility([]);
        return;
      }
      const urlIDsToHide = filterURLsBySearchTerm(
        readURLsFromDOM(),
        searchTerm,
      );
      updateURLCardSearchVisibility(urlIDsToHide);
    });

  on(AppEvents.URL_TAG_FILTER_APPLIED, () => {
    if (wrapper.hasClass("visible")) {
      reapplyURLSearchFilter();
    }
  });
}

export function closeURLSearchAndEraseInput(): void {
  $("#urlSearchFilterIconClose").addClass("hidden");
  $("#urlSearchFilterIcon").removeClass("hidden");
  $("#SearchURLWrap").addClass("hidden").removeClass("visible");
  $("#UTubDescriptionSubheaderWrap").removeClass("hidden");
  $("#URLContentSearch").val("");
  $("#URLContentSearch").removeClass("url-search-expanded");
  $(".urlRow").removeAttr("searchable");
  emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);
}

export function showURLSearchIcon(): void {
  $("#urlSearchFilterIcon").removeClass("hidden");
}

export function hideURLSearchIcon(): void {
  if ($("#SearchURLWrap").hasClass("visible")) {
    closeURLSearchAndEraseInput();
  }
  $("#urlSearchFilterIcon").addClass("hidden");
}

export function reapplyURLSearchFilter(): void {
  const searchTerm = getInputValue($("#URLContentSearch"));
  if (searchTerm === "" || !$("#SearchURLWrap").hasClass("visible")) {
    return;
  }
  const urlIDsToHide = filterURLsBySearchTerm(readURLsFromDOM(), searchTerm);
  updateURLCardSearchVisibility(urlIDsToHide);
}
