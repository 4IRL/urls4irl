import {
  hideUTubSearchBar,
  resetUTubSearch,
  setUTubSelectorSearchEventListener,
  showUTubSearchBar,
} from "../search.js";

import { APP_CONFIG } from "../../../lib/config.js";

import { filterUTubsByName } from "../../../logic/utub-search.js";

vi.mock("../../../logic/utub-search.js", () => ({
  filterUTubsByName: vi.fn(() => []),
}));

const $ = window.jQuery;

const SEARCH_HTML = `
  <div id="UTubDeckSubheader" class="hidden">Create a UTub</div>
  <div id="SearchUTubWrap">
    <div class="text-input-inner-container">
      <span class="utub-search-prefix-icon" aria-hidden="true"></span>
      <input id="UTubNameSearch" type="search" value="" />
      <label class="text-input-label" for="UTubNameSearch">Search UTub Names</label>
    </div>
  </div>
  <p id="UTubSearchNoResults" class="hidden"></p>
  <span id="UTubSearchAnnouncement" class="visually-hidden" aria-live="polite"></span>
  <button id="memberBtnCreate"></button>
  <div id="listUTubs">
    <div class="UTubSelector" utubid="1"><span class="UTubName">Alpha</span></div>
    <div class="UTubSelector" utubid="2"><span class="UTubName">Beta</span></div>
    <div class="UTubSelector" utubid="3"><span class="UTubName">Gamma</span></div>
  </div>
`;

describe("UTub Search", () => {
  beforeEach(() => {
    document.body.innerHTML = SEARCH_HTML;
    vi.mocked(filterUTubsByName).mockReset().mockReturnValue([]);
    setUTubSelectorSearchEventListener();
  });

  describe("resetUTubSearch", () => {
    it("clears the search input value", () => {
      $("#UTubNameSearch").val("some search text");

      resetUTubSearch();

      expect($("#UTubNameSearch").val()).toBe("");
    });

    it("removes hidden class from all .UTubSelector elements", () => {
      $(".UTubSelector").addClass("hidden");

      resetUTubSearch();

      $(".UTubSelector").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
    });

    it("hides the no-results message", () => {
      $("#UTubSearchNoResults")
        .removeClass("hidden")
        .text(APP_CONFIG.strings.UTUB_SEARCH_NO_RESULTS);

      resetUTubSearch();

      expect($("#UTubSearchNoResults").hasClass("hidden")).toBe(true);
      expect($("#UTubSearchNoResults").text()).toBe("");
    });
  });

  describe("typing into #UTubNameSearch", () => {
    it("hides UTub selectors returned by filterUTubsByName", () => {
      vi.mocked(filterUTubsByName).mockReturnValue([2]);

      $("#UTubNameSearch").val("alpha").trigger("input");

      expect($('.UTubSelector[utubid="1"]').hasClass("hidden")).toBe(false);
      expect($('.UTubSelector[utubid="2"]').hasClass("hidden")).toBe(true);
      expect($('.UTubSelector[utubid="3"]').hasClass("hidden")).toBe(false);
    });

    it("shows all UTub selectors when search input is empty", () => {
      vi.mocked(filterUTubsByName).mockReturnValue([2]);
      $("#UTubNameSearch").val("alpha").trigger("input");
      expect($('.UTubSelector[utubid="2"]').hasClass("hidden")).toBe(true);

      $("#UTubNameSearch").val("").trigger("input");

      $(".UTubSelector").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
    });

    it("shows the no-results message when all UTubs are filtered out", () => {
      vi.mocked(filterUTubsByName).mockReturnValue([1, 2, 3]);

      $("#UTubNameSearch").val("zzzzz").trigger("input");

      const noResults = $("#UTubSearchNoResults");
      expect(noResults.hasClass("hidden")).toBe(false);
      expect(noResults.text()).toBe(APP_CONFIG.strings.UTUB_SEARCH_NO_RESULTS);
    });

    it("hides the no-results message when search has matches", () => {
      vi.mocked(filterUTubsByName).mockReturnValue([1, 2, 3]);
      $("#UTubNameSearch").val("zzzzz").trigger("input");
      expect($("#UTubSearchNoResults").hasClass("hidden")).toBe(false);

      vi.mocked(filterUTubsByName).mockReturnValue([2]);
      $("#UTubNameSearch").val("alpha").trigger("input");

      expect($("#UTubSearchNoResults").hasClass("hidden")).toBe(true);
    });

    it("updates the accessibility announcement with visible/total counts", () => {
      vi.mocked(filterUTubsByName).mockReturnValue([2]);

      $("#UTubNameSearch").val("alpha").trigger("input");

      expect($("#UTubSearchAnnouncement").text()).toBe("2 of 3 UTubs shown");
    });

    it("announces 'No UTubs found' when no UTubs match", () => {
      vi.mocked(filterUTubsByName).mockReturnValue([1, 2, 3]);

      $("#UTubNameSearch").val("zzzzz").trigger("input");

      expect($("#UTubSearchAnnouncement").text()).toBe(
        APP_CONFIG.strings.UTUB_SEARCH_NO_RESULTS,
      );
    });
  });

  describe("pressing Escape", () => {
    it("clears the input and shows all UTub selectors", () => {
      vi.mocked(filterUTubsByName).mockReturnValue([1, 2, 3]);
      $("#UTubNameSearch").val("zzzzz").trigger("input");
      expect($("#UTubSearchNoResults").hasClass("hidden")).toBe(false);

      $("#UTubNameSearch").trigger("focus");
      $("#UTubNameSearch").trigger($.Event("keydown", { key: "Escape" }));

      expect($("#UTubNameSearch").val()).toBe("");
      $(".UTubSelector").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
      expect($("#UTubSearchNoResults").hasClass("hidden")).toBe(true);
    });
  });

  describe("showUTubSearchBar", () => {
    it("shows the search wrap and hides the subheader", () => {
      $("#SearchUTubWrap").addClass("hidden");
      $("#UTubDeckSubheader").removeClass("hidden");

      showUTubSearchBar();

      expect($("#SearchUTubWrap").hasClass("hidden")).toBe(false);
      expect($("#UTubDeckSubheader").hasClass("hidden")).toBe(true);
    });
  });

  describe("hideUTubSearchBar", () => {
    it("hides the search wrap and shows the subheader with create message", () => {
      $("#SearchUTubWrap").removeClass("hidden");
      $("#UTubDeckSubheader").addClass("hidden");

      hideUTubSearchBar();

      expect($("#SearchUTubWrap").hasClass("hidden")).toBe(true);
      expect($("#UTubDeckSubheader").hasClass("hidden")).toBe(false);
      expect($("#UTubDeckSubheader").text()).toBe(
        APP_CONFIG.strings.UTUB_CREATE_MSG,
      );
    });

    it("clears the active search input and shows all selectors", () => {
      vi.mocked(filterUTubsByName).mockReturnValue([2]);
      $("#UTubNameSearch").val("alpha").trigger("input");
      expect($('.UTubSelector[utubid="2"]').hasClass("hidden")).toBe(true);

      hideUTubSearchBar();

      expect($("#UTubNameSearch").val()).toBe("");
      $(".UTubSelector").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
    });
  });

  describe("native clear button (change event)", () => {
    it("resets the search when change fires with an empty value", () => {
      vi.mocked(filterUTubsByName).mockReturnValue([1, 2, 3]);
      $("#UTubNameSearch").val("zzzzz").trigger("input");
      expect($("#UTubSearchNoResults").hasClass("hidden")).toBe(false);

      $("#UTubNameSearch").val("").trigger("change");

      expect($("#UTubNameSearch").val()).toBe("");
      $(".UTubSelector").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
      expect($("#UTubSearchNoResults").hasClass("hidden")).toBe(true);
    });
  });
});
