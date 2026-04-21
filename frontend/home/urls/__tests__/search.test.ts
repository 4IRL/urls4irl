import {
  setURLSearchEventListener,
  closeURLSearchAndEraseInput,
  collapseURLSearchInput,
  showURLSearchIcon,
  hideURLSearchIcon,
  temporarilyHideSearchForEdit,
  disableURLSearch,
  reapplyURLSearchFilter,
} from "../search.js";

import { APP_CONFIG } from "../../../lib/config.js";
import { AppEvents, emit } from "../../../lib/event-bus.js";

import { filterURLsBySearchTerm } from "../../../logic/url-search.js";

vi.mock("../../../logic/url-search.js", () => ({
  filterURLsBySearchTerm: vi.fn(() => []),
}));

const $ = window.jQuery;

const SEARCH_HTML = `
  <button id="URLSearchFilterIcon"></button>
  <button id="URLSearchFilterIconClose" class="hidden"></button>
  <div id="SearchURLWrap" class="hidden"></div>
  <input id="URLContentSearch" value="" />
  <div id="UTubDescriptionSubheaderWrap"></div>
  <button id="URLDeckSubheaderCreateDescription"></button>
  <p id="URLSearchNoResults" class="hidden"></p>
  <span id="URLSearchAnnouncement"></span>
  <div id="listURLs">
    <div class="urlRow" utuburlid="1" filterable="true">
      <span class="urlTitle">Alpha News</span>
      <a class="urlString" href="https://alpha-news.com">https://alpha-news.com</a>
    </div>
    <div class="urlRow" utuburlid="2" filterable="true">
      <span class="urlTitle">Beta Blog</span>
      <a class="urlString" href="https://beta-blog.com">https://beta-blog.com</a>
    </div>
    <div class="urlRow" utuburlid="3" filterable="false">
      <span class="urlTitle">Gamma Docs</span>
      <a class="urlString" href="https://gamma-docs.com">https://gamma-docs.com</a>
    </div>
    <div class="urlRow" utuburlid="4" filterable="true">
      <span class="urlTitle">Delta Dev</span>
      <a class="urlString" href="https://delta-dev.com">https://delta-dev.com</a>
    </div>
  </div>
`;

describe("URL Search", () => {
  beforeEach(() => {
    document.body.innerHTML = SEARCH_HTML;
    vi.mocked(filterURLsBySearchTerm).mockReset().mockReturnValue([]);
    setURLSearchEventListener();
  });

  describe("clicking #URLSearchFilterIcon", () => {
    it("shows #SearchURLWrap", () => {
      $("#URLSearchFilterIcon").trigger("click");

      expect($("#SearchURLWrap").hasClass("visible-flex")).toBe(true);
      expect($("#SearchURLWrap").hasClass("hidden")).toBe(false);
    });

    it("shows close icon and hides search icon", () => {
      $("#URLSearchFilterIcon").trigger("click");

      expect($("#URLSearchFilterIconClose").hasClass("hidden")).toBe(false);
      expect($("#URLSearchFilterIcon").hasClass("hidden")).toBe(true);
    });

    it("adds url-search-expanded class to input and focuses it", async () => {
      $("#URLSearchFilterIcon").trigger("click");

      await vi.waitFor(() => {
        expect($("#URLContentSearch").hasClass("url-search-expanded")).toBe(
          true,
        );
      });

      expect(document.activeElement).toBe(
        document.getElementById("URLContentSearch"),
      );
    });
  });

  describe("clicking #URLSearchFilterIconClose", () => {
    beforeEach(() => {
      $("#URLSearchFilterIcon").trigger("click");
    });

    it("hides search wrap", () => {
      $("#URLSearchFilterIconClose").trigger("click");

      expect($("#SearchURLWrap").hasClass("hidden")).toBe(true);
      expect($("#SearchURLWrap").hasClass("visible-flex")).toBe(false);
    });

    it("shows search icon and hides close icon", () => {
      $("#URLSearchFilterIconClose").trigger("click");

      expect($("#URLSearchFilterIcon").hasClass("hidden")).toBe(false);
      expect($("#URLSearchFilterIconClose").hasClass("hidden")).toBe(true);
    });

    it("clears the search input value", () => {
      $("#URLContentSearch").val("some search text");

      $("#URLSearchFilterIconClose").trigger("click");

      expect($("#URLContentSearch").val()).toBe("");
    });

    it("removes searchable attribute from all .urlRow elements", () => {
      $(".urlRow").attr("searchable", "false");

      $("#URLSearchFilterIconClose").trigger("click");

      $(".urlRow").each(function () {
        expect($(this).attr("searchable")).toBeUndefined();
      });
    });
  });

  describe("typing into #URLContentSearch", () => {
    beforeEach(() => {
      vi.useFakeTimers();
      $("#URLSearchFilterIcon").trigger("click");
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("calls filterURLsBySearchTerm with only filterable=true URLs", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);

      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);

      expect(filterURLsBySearchTerm).toHaveBeenCalledWith(
        expect.arrayContaining([
          { id: 1, title: "Alpha News", urlString: "https://alpha-news.com" },
          { id: 2, title: "Beta Blog", urlString: "https://beta-blog.com" },
          { id: 4, title: "Delta Dev", urlString: "https://delta-dev.com" },
        ]),
        "alpha",
      );

      expect(filterURLsBySearchTerm).toHaveBeenCalledWith(
        expect.not.arrayContaining([expect.objectContaining({ id: 3 })]),
        expect.any(String),
      );
    });

    it("sets searchable attribute on filterable=true urlRow elements only", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);

      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);

      expect($('.urlRow[utuburlid="1"]').attr("searchable")).toBe("true");
      expect($('.urlRow[utuburlid="2"]').attr("searchable")).toBe("false");
      expect($('.urlRow[utuburlid="4"]').attr("searchable")).toBe("true");
    });

    it("never modifies searchable attribute on filterable=false urlRow elements", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);

      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);

      expect($('.urlRow[utuburlid="3"]').attr("searchable")).toBeUndefined();
    });

    it("treats whitespace-only input as empty and does not call filter", () => {
      $("#URLContentSearch").val("   ").trigger("input");
      vi.advanceTimersByTime(200);

      expect(filterURLsBySearchTerm).not.toHaveBeenCalled();
    });

    it("trims leading/trailing whitespace before filtering", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);

      $("#URLContentSearch").val("  alpha  ").trigger("input");
      vi.advanceTimersByTime(200);

      expect(filterURLsBySearchTerm).toHaveBeenCalledWith(
        expect.any(Array),
        "alpha",
      );
    });

    it("clears search announcement for whitespace-only input", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);
      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);
      expect($("#URLSearchAnnouncement").text()).toBe("2 of 3 URLs shown");

      $("#URLContentSearch").val("   ").trigger("input");
      vi.advanceTimersByTime(200);

      expect($("#URLSearchAnnouncement").text()).toBe("");
    });
  });

  describe("pressing Escape", () => {
    it("closes search the same as clicking close icon", () => {
      $("#URLSearchFilterIcon").trigger("click");

      $("#URLContentSearch").trigger("focus");
      $("#URLContentSearch").trigger($.Event("keydown", { key: "Escape" }));

      expect($("#SearchURLWrap").hasClass("hidden")).toBe(true);
      expect($("#SearchURLWrap").hasClass("visible-flex")).toBe(false);
      expect($("#URLSearchFilterIcon").hasClass("hidden")).toBe(false);
      expect($("#URLSearchFilterIconClose").hasClass("hidden")).toBe(true);
    });
  });

  describe("closeURLSearchAndEraseInput", () => {
    it("hides #SearchURLWrap", () => {
      $("#SearchURLWrap").addClass("visible-flex").removeClass("hidden");

      closeURLSearchAndEraseInput();

      expect($("#SearchURLWrap").hasClass("hidden")).toBe(true);
      expect($("#SearchURLWrap").hasClass("visible-flex")).toBe(false);
    });

    it("shows search icon and hides close icon", () => {
      $("#URLSearchFilterIconClose").removeClass("hidden");
      $("#URLSearchFilterIcon").addClass("hidden");

      closeURLSearchAndEraseInput();

      expect($("#URLSearchFilterIcon").hasClass("hidden")).toBe(false);
      expect($("#URLSearchFilterIconClose").hasClass("hidden")).toBe(true);
    });

    it("clears the search input value", () => {
      $("#URLContentSearch").val("some search text");

      closeURLSearchAndEraseInput();

      expect($("#URLContentSearch").val()).toBe("");
    });

    it("removes searchable attribute from all .urlRow elements", () => {
      $(".urlRow").attr("searchable", "false");

      closeURLSearchAndEraseInput();

      $(".urlRow").each(function () {
        expect($(this).attr("searchable")).toBeUndefined();
      });
    });
  });

  describe("showURLSearchIcon", () => {
    it("shows the search icon", () => {
      $("#URLSearchFilterIcon").addClass("hidden");

      showURLSearchIcon();

      expect($("#URLSearchFilterIcon").hasClass("hidden")).toBe(false);
    });

    it("adds search-ready class to the search wrap", () => {
      showURLSearchIcon();

      expect($("#SearchURLWrap").hasClass("search-ready")).toBe(true);
    });

    it("removes hidden class when restoring from temporarily hidden state", () => {
      showURLSearchIcon();
      temporarilyHideSearchForEdit();

      showURLSearchIcon();

      expect($("#SearchURLWrap").hasClass("hidden")).toBe(false);
      expect($("#SearchURLWrap").hasClass("search-ready")).toBe(true);
    });
  });

  describe("hideURLSearchIcon", () => {
    it("hides the search icon", () => {
      $("#URLSearchFilterIcon").removeClass("hidden");

      hideURLSearchIcon();

      expect($("#URLSearchFilterIcon").hasClass("hidden")).toBe(true);
    });

    it("removes search-ready class", () => {
      showURLSearchIcon();

      hideURLSearchIcon();

      expect($("#SearchURLWrap").hasClass("search-ready")).toBe(false);
    });
  });

  describe("disableURLSearch", () => {
    beforeEach(() => {
      showURLSearchIcon();
      $("#URLSearchFilterIcon").trigger("click");
      $("#URLContentSearch").val("test query");
      $(".urlRow").attr("searchable", "false");
    });

    it("removes search-ready class from the search wrap", () => {
      disableURLSearch();

      expect($("#SearchURLWrap").hasClass("search-ready")).toBe(false);
    });

    it("clears the search input and removes searchable attributes", () => {
      disableURLSearch();

      expect($("#URLContentSearch").val()).toBe("");
      $(".urlRow").each(function () {
        expect($(this).attr("searchable")).toBeUndefined();
      });
    });

    it("hides the search icon", () => {
      disableURLSearch();

      expect($("#URLSearchFilterIcon").hasClass("hidden")).toBe(true);
    });
  });

  describe("collapseURLSearchInput", () => {
    beforeEach(() => {
      $("#URLSearchFilterIcon").trigger("click");
      $("#URLContentSearch").val("test query");
      $(".urlRow").attr("searchable", "false");
    });

    it("hides the search wrap without clearing the input value", () => {
      collapseURLSearchInput();

      expect($("#SearchURLWrap").hasClass("hidden")).toBe(true);
      expect($("#SearchURLWrap").hasClass("visible-flex")).toBe(false);
      expect($("#URLContentSearch").val()).toBe("test query");
    });

    it("preserves searchable attributes on URL rows", () => {
      collapseURLSearchInput();

      $(".urlRow").each(function () {
        expect($(this).attr("searchable")).toBe("false");
      });
    });

    it("restores the search icon and hides the close icon", () => {
      collapseURLSearchInput();

      expect($("#URLSearchFilterIcon").hasClass("hidden")).toBe(false);
      expect($("#URLSearchFilterIconClose").hasClass("hidden")).toBe(true);
    });
  });

  describe("temporarilyHideSearchForEdit", () => {
    it("collapses search and hides icon when search is open", () => {
      $("#URLSearchFilterIcon").trigger("click");

      temporarilyHideSearchForEdit();

      expect($("#SearchURLWrap").hasClass("hidden")).toBe(true);
      expect($("#SearchURLWrap").hasClass("visible-flex")).toBe(false);
      expect($("#URLSearchFilterIcon").hasClass("hidden")).toBe(true);
    });

    it("removes search-ready and adds hidden when search is in desktop ready state", () => {
      showURLSearchIcon();

      temporarilyHideSearchForEdit();

      expect($("#URLSearchFilterIcon").hasClass("hidden")).toBe(true);
      expect($("#SearchURLWrap").hasClass("search-ready")).toBe(false);
      expect($("#SearchURLWrap").hasClass("hidden")).toBe(true);
    });

    it("preserves search input value for restore after edit", () => {
      showURLSearchIcon();
      $("#URLContentSearch").val("alpha");

      temporarilyHideSearchForEdit();

      expect($("#URLContentSearch").val()).toBe("alpha");
    });
  });

  describe("reapplyURLSearchFilter", () => {
    it("is a no-op when search input is empty", () => {
      showURLSearchIcon();
      $("#SearchURLWrap").addClass("visible-flex");
      $("#URLContentSearch").val("");

      reapplyURLSearchFilter();

      expect(filterURLsBySearchTerm).not.toHaveBeenCalled();
    });

    it("is a no-op when search wrap is not visible", () => {
      $("#URLContentSearch").val("alpha");

      reapplyURLSearchFilter();

      expect(filterURLsBySearchTerm).not.toHaveBeenCalled();
    });

    it("re-filters when search is active with visible-flex", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);
      $("#URLSearchFilterIcon").trigger("click");
      $("#URLContentSearch").val("alpha");

      reapplyURLSearchFilter();

      expect(filterURLsBySearchTerm).toHaveBeenCalledWith(
        expect.arrayContaining([expect.objectContaining({ id: 1 })]),
        "alpha",
      );
    });

    it("is a no-op when search input is whitespace-only", () => {
      showURLSearchIcon();
      $("#SearchURLWrap").addClass("visible-flex");
      $("#URLContentSearch").val("   ");

      reapplyURLSearchFilter();

      expect(filterURLsBySearchTerm).not.toHaveBeenCalled();
    });

    it("re-filters when search is active with search-ready (desktop)", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);
      showURLSearchIcon();
      $("#URLContentSearch").val("alpha");

      reapplyURLSearchFilter();

      expect(filterURLsBySearchTerm).toHaveBeenCalledWith(
        expect.arrayContaining([expect.objectContaining({ id: 1 })]),
        "alpha",
      );
    });
  });

  describe("URL_TAG_FILTER_APPLIED listener", () => {
    it("calls filterURLsBySearchTerm when search is active", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([]);
      $("#URLSearchFilterIcon").trigger("click");
      $("#URLContentSearch").val("alpha");

      emit(AppEvents.URL_TAG_FILTER_APPLIED);

      expect(filterURLsBySearchTerm).toHaveBeenCalledWith(
        expect.any(Array),
        "alpha",
      );
    });
  });

  describe("no results message", () => {
    const FILTERABLE_IDS = [1, 2, 4];

    beforeEach(() => {
      vi.useFakeTimers();
      $("#URLSearchFilterIcon").trigger("click");
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("shows #URLSearchNoResults when search hides all filterable URLs", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue(FILTERABLE_IDS);

      $("#URLContentSearch").val("zzzzz").trigger("input");
      vi.advanceTimersByTime(200);

      const noResults = $("#URLSearchNoResults");
      expect(noResults.hasClass("hidden")).toBe(false);
      expect(noResults.text()).toBe(APP_CONFIG.strings.URL_SEARCH_NO_RESULTS);
    });

    it("hides #URLSearchNoResults when search matches some URLs", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2, 4]);

      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);

      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(true);
    });

    it("hides #URLSearchNoResults when search input is cleared", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue(FILTERABLE_IDS);
      $("#URLContentSearch").val("zzzzz").trigger("input");
      vi.advanceTimersByTime(200);

      vi.mocked(filterURLsBySearchTerm).mockReturnValue([]);
      $("#URLContentSearch").val("").trigger("input");

      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(true);
    });

    it("hides #URLSearchNoResults when search is closed via close icon", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue(FILTERABLE_IDS);
      $("#URLContentSearch").val("zzzzz").trigger("input");
      vi.advanceTimersByTime(200);

      $("#URLSearchFilterIconClose").trigger("click");

      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(true);
    });

    it("hides #URLSearchNoResults when search is closed via Escape", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue(FILTERABLE_IDS);
      $("#URLContentSearch").val("zzzzz").trigger("input");
      vi.advanceTimersByTime(200);

      $("#URLContentSearch").trigger("focus");
      $("#URLContentSearch").trigger($.Event("keydown", { key: "Escape" }));

      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(true);
    });

    it("hides #URLSearchNoResults when closeURLSearchAndEraseInput is called", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue(FILTERABLE_IDS);
      $("#URLContentSearch").val("zzzzz").trigger("input");
      vi.advanceTimersByTime(200);

      closeURLSearchAndEraseInput();

      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(true);
    });

    it("hides #URLSearchNoResults when disableURLSearch is called", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue(FILTERABLE_IDS);
      $("#URLContentSearch").val("zzzzz").trigger("input");
      vi.advanceTimersByTime(200);

      disableURLSearch();

      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(true);
    });

    it("shows #URLSearchNoResults when reapplyURLSearchFilter hides all URLs", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue(FILTERABLE_IDS);
      $("#URLContentSearch").val("zzzzz");

      reapplyURLSearchFilter();

      const noResults = $("#URLSearchNoResults");
      expect(noResults.hasClass("hidden")).toBe(false);
      expect(noResults.text()).toBe(APP_CONFIG.strings.URL_SEARCH_NO_RESULTS);
    });

    it("is hidden by default before any search", () => {
      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(true);
    });

    it("hides when no-results is showing and search transitions to partial match", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue(FILTERABLE_IDS);
      $("#URLContentSearch").val("zzzzz").trigger("input");
      vi.advanceTimersByTime(200);
      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(false);

      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);
      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);

      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(true);
    });

    it("shows when tag filter change causes all remaining URLs to be hidden", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2, 4]);
      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);
      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(true);

      vi.mocked(filterURLsBySearchTerm).mockReturnValue(FILTERABLE_IDS);
      emit(AppEvents.URL_TAG_FILTER_APPLIED);

      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(false);
      expect($("#URLSearchNoResults").text()).toBe(
        APP_CONFIG.strings.URL_SEARCH_NO_RESULTS,
      );
    });

    it("hides when tag filter change restores some URLs from zero results", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue(FILTERABLE_IDS);
      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);
      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(false);

      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);
      emit(AppEvents.URL_TAG_FILTER_APPLIED);

      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(true);
    });

    it("does not show when tag filter hides all URLs leaving zero filterable rows", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2, 4]);
      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);
      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(true);

      $(".urlRow").attr("filterable", "false");
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([]);
      emit(AppEvents.URL_TAG_FILTER_APPLIED);

      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(true);
    });

    it("shows when tag filter removes the only search-matching URL but filterable rows remain", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2, 4]);
      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);
      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(true);

      $('.urlRow[utuburlid="1"]').attr("filterable", "false");
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2, 4]);
      emit(AppEvents.URL_TAG_FILTER_APPLIED);

      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(false);
      expect($("#URLSearchNoResults").text()).toBe(
        APP_CONFIG.strings.URL_SEARCH_NO_RESULTS,
      );
    });

    it("hides when all tag filters are cleared while no-results is showing", () => {
      $(".urlRow[utuburlid='2'], .urlRow[utuburlid='4']").attr(
        "filterable",
        "false",
      );
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([1]);
      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);
      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(false);

      $(".urlRow").attr("filterable", "true");
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([4]);
      emit(AppEvents.URL_TAG_FILTER_APPLIED);

      expect($("#URLSearchNoResults").hasClass("hidden")).toBe(true);
    });
  });

  describe("search results announcement (aria-live)", () => {
    const FILTERABLE_IDS = [1, 2, 4];

    beforeEach(() => {
      vi.useFakeTimers();
      $("#URLSearchFilterIcon").trigger("click");
    });

    afterEach(() => {
      vi.useRealTimers();
    });

    it("announces partial match count after debounce", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);

      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);

      expect($("#URLSearchAnnouncement").text()).toBe("2 of 3 URLs shown");
    });

    it("announces 'No URLs found' when search hides all filterable URLs", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue(FILTERABLE_IDS);

      $("#URLContentSearch").val("zzzzz").trigger("input");
      vi.advanceTimersByTime(200);

      expect($("#URLSearchAnnouncement").text()).toBe(
        APP_CONFIG.strings.URL_SEARCH_NO_RESULTS,
      );
    });

    it("clears announcement when search input is emptied", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);
      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);
      expect($("#URLSearchAnnouncement").text()).toBe("2 of 3 URLs shown");

      $("#URLContentSearch").val("").trigger("input");

      expect($("#URLSearchAnnouncement").text()).toBe("");
    });

    it("clears announcement when search is closed via close icon", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);
      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);

      $("#URLSearchFilterIconClose").trigger("click");

      expect($("#URLSearchAnnouncement").text()).toBe("");
    });

    it("clears announcement when search is closed via Escape", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);
      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);

      $("#URLContentSearch").trigger("focus");
      $("#URLContentSearch").trigger($.Event("keydown", { key: "Escape" }));

      expect($("#URLSearchAnnouncement").text()).toBe("");
    });

    it("clears announcement when disableURLSearch is called", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);
      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);

      disableURLSearch();

      expect($("#URLSearchAnnouncement").text()).toBe("");
    });

    it("updates announcement when tag filter changes search results", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);
      $("#URLContentSearch").val("alpha").trigger("input");
      vi.advanceTimersByTime(200);
      expect($("#URLSearchAnnouncement").text()).toBe("2 of 3 URLs shown");

      vi.mocked(filterURLsBySearchTerm).mockReturnValue(FILTERABLE_IDS);
      emit(AppEvents.URL_TAG_FILTER_APPLIED);

      expect($("#URLSearchAnnouncement").text()).toBe(
        APP_CONFIG.strings.URL_SEARCH_NO_RESULTS,
      );
    });

    it("announces all URLs shown when search matches everything", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([]);

      $("#URLContentSearch").val("a").trigger("input");
      vi.advanceTimersByTime(200);

      expect($("#URLSearchAnnouncement").text()).toBe("3 of 3 URLs shown");
    });
  });
});
