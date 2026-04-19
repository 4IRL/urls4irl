import { $, getInputValue } from "../../lib/globals.js";
import { KEYS } from "../../lib/constants.js";
import { APP_CONFIG } from "../../lib/config.js";
import { AppEvents, emit, on } from "../../lib/event-bus.js";
import { filterURLsBySearchTerm } from "../../logic/url-search.js";
import { getState } from "../../store/app-store.js";

type URLDOMEntry = { id: number; title: string; urlString: string };

const MAX_SEARCH_LENGTH = 500;
const NO_RESULTS_TEXT = "No URLs found";

function readURLsFromDOM(): URLDOMEntry[] {
  return $.map($(".urlRow[filterable=true]").toArray(), (el: HTMLElement) => {
    const urlID = parseInt($(el).attr("utuburlid")!);
    if (isNaN(urlID)) return null!;
    return {
      id: urlID,
      title: $(el).find(".urlTitle").text(),
      urlString: $(el).find(".urlString").attr("href")!,
    };
  }).filter(Boolean);
}

on(AppEvents.URL_TAG_FILTER_APPLIED, () => {
  reapplyURLSearchFilter();
});

function updateURLCardSearchVisibility(urlIDsToHide: number[]): void {
  const filterableRows = $(".urlRow[filterable=true]");

  if (urlIDsToHide.length === 0) {
    filterableRows.attr("searchable", "true");
    hideNoResultsMessage();
    emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);
    return;
  }

  const hideSet = new Set(urlIDsToHide);

  for (let index = 0; index < filterableRows.length; index++) {
    const row = $(filterableRows[index]);
    const urlID = parseInt(row.attr("utuburlid")!);
    row.attr("searchable", hideSet.has(urlID) ? "false" : "true");
  }

  const hasVisibleURLs =
    $(".urlRow[filterable=true][searchable=true]").length > 0;
  if (hasVisibleURLs) {
    hideNoResultsMessage();
  } else {
    showNoResultsMessage();
  }

  emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);
}

function showNoResultsMessage(): void {
  $("#URLSearchNoResults").text(NO_RESULTS_TEXT).removeClass("hidden");
}

function hideNoResultsMessage(): void {
  $("#URLSearchNoResults").addClass("hidden").text("");
}

export function setURLSearchEventListener(): void {
  const wrapper = $("#SearchURLWrap");
  const searchIcon = $("#URLSearchFilterIcon");
  const searchIconClose = $("#URLSearchFilterIconClose");
  const searchInput = $("#URLContentSearch");

  searchIcon.offAndOnExact("click.urlSearchInputShow", function () {
    wrapper.addClass("visible-flex").removeClass("hidden");
    $("#URLDeckSubheaderCreateDescription").addClass("hidden");
    $("#URLDeckNoDescription").hideClass();
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
      if (searchTerm.length > MAX_SEARCH_LENGTH) {
        searchInput.val(searchTerm.slice(0, MAX_SEARCH_LENGTH));
        return;
      }
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
}

export function closeURLSearchAndEraseInput(): void {
  collapseURLSearchInput();
  $("#URLContentSearch").val("");
  $(".urlRow").removeAttr("searchable");
  hideNoResultsMessage();
  emit(AppEvents.URL_SEARCH_VISIBILITY_CHANGED);
}

export function collapseURLSearchInput(): void {
  $("#URLSearchFilterIconClose").addClass("hidden");
  $("#URLSearchFilterIcon").removeClass("hidden");
  $("#SearchURLWrap").addClass("hidden").removeClass("visible-flex");
  $("#URLDeckSubheaderCreateDescription").removeClass("hidden");
  $("#URLContentSearch").removeClass("url-search-expanded");

  const hasNoDescription =
    !$("#URLDeckSubheader").text().length &&
    $("#UTubDescriptionSubheaderWrap").hasClass("hidden");
  const isOwner = getState().isCurrentUserOwner;
  if (hasNoDescription && !isOwner) {
    $("#URLDeckNoDescription").showClassNormal();
  }
}

export function showURLSearchIcon(): void {
  $("#URLSearchFilterIcon").removeClass("hidden");
  $("#SearchURLWrap").addClass("search-ready");
}

function _collapseAndHideIcon(removeSearchReady: boolean): void {
  if ($("#SearchURLWrap").hasClass("visible-flex")) {
    collapseURLSearchInput();
  }
  $("#URLSearchFilterIcon").addClass("hidden");
  if (removeSearchReady) {
    $("#SearchURLWrap").removeClass("search-ready");
  }
}

export function hideURLSearchIcon(): void {
  _collapseAndHideIcon(true);
}

export function temporarilyHideSearchForEdit(): void {
  _collapseAndHideIcon(false);
}

export function disableURLSearch(): void {
  closeURLSearchAndEraseInput();
  hideURLSearchIcon();
}

export function reapplyURLSearchFilter(): void {
  const searchTerm = getInputValue($("#URLContentSearch"));
  const searchWrap = $("#SearchURLWrap");
  const isVisible =
    searchWrap.hasClass("visible-flex") || searchWrap.hasClass("search-ready");
  if (searchTerm.length < APP_CONFIG.constants.URLS_MIN_LENGTH || !isVisible) {
    return;
  }
  const urlIDsToHide = filterURLsBySearchTerm(readURLsFromDOM(), searchTerm);
  updateURLCardSearchVisibility(urlIDsToHide);
}
