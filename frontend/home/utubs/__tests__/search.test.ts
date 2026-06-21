import {
  applyAlternatingUTubSelectorBackground,
  closeUTubNameFilter,
  hideUTubSearchBar,
  isUTubSearchActive,
  openUTubNameFilter,
  resetUTubSearch,
  setUTubNameFilterToggleListeners,
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
  <div id="UTubDeck">
    <button id="utubNameFilterBtn"></button>
    <button id="utubNameFilterBtnClose" class="hidden"></button>
    <div id="UTubDeckSubheader" class="hidden">Create a UTub</div>
    <div id="SearchUTubWrap">
      <div class="text-input-inner-container">
        <span class="utub-search-prefix-icon" aria-hidden="true"></span>
        <input id="UTubNameSearch" type="search" value="" />
        <label class="text-input-label" for="UTubNameSearch">Filter UTubs</label>
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
  </div>
`;

describe("UTub Search", () => {
  beforeEach(() => {
    document.body.innerHTML = SEARCH_HTML;
    vi.mocked(filterUTubsByName).mockReset().mockReturnValue([]);
    setUTubSelectorSearchEventListener();
  });

  describe("isUTubSearchActive", () => {
    it("returns false for an empty input value", () => {
      $("#UTubNameSearch").val("");

      expect(isUTubSearchActive()).toBe(false);
    });

    it("returns true at the UTUBS_MIN_NAME_LENGTH threshold", () => {
      const thresholdValue = "x".repeat(
        APP_CONFIG.constants.UTUBS_MIN_NAME_LENGTH,
      );

      $("#UTubNameSearch").val(thresholdValue);

      expect(isUTubSearchActive()).toBe(true);
    });

    it("returns false when #UTubNameSearch is absent from the DOM", () => {
      $("#UTubNameSearch").remove();

      expect(isUTubSearchActive()).toBe(false);
    });
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

    it("re-applies alternating even/odd classes after un-hiding rows", () => {
      $(".UTubSelector").addClass("hidden");

      resetUTubSearch();

      expect($('.UTubSelector[utubid="1"]').hasClass("even")).toBe(true);
      expect($('.UTubSelector[utubid="2"]').hasClass("odd")).toBe(true);
      expect($('.UTubSelector[utubid="3"]').hasClass("even")).toBe(true);
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

      const expectedAnnouncement =
        APP_CONFIG.strings.UTUB_SEARCH_COUNT_TEMPLATE.replace(
          "{{ visible }}",
          "2",
        ).replace("{{ total }}", "3");
      expect($("#UTubSearchAnnouncement").text()).toBe(expectedAnnouncement);
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

  describe("alternating background (zebra striping)", () => {
    it("assigns alternating even/odd classes across all visible selectors", () => {
      applyAlternatingUTubSelectorBackground();

      expect($('.UTubSelector[utubid="1"]').hasClass("even")).toBe(true);
      expect($('.UTubSelector[utubid="2"]').hasClass("odd")).toBe(true);
      expect($('.UTubSelector[utubid="3"]').hasClass("even")).toBe(true);
    });

    it("excludes .hidden rows from the alternating index after filtering", () => {
      // Filter out the middle row: the visible rows (1 and 3) must alternate as
      // even/odd by VISIBLE order — not keep the even/even they'd get from a
      // :nth-child rule that counts the hidden row.
      vi.mocked(filterUTubsByName).mockReturnValue([2]);

      $("#UTubNameSearch").val("a").trigger("input");

      expect($('.UTubSelector[utubid="2"]').hasClass("hidden")).toBe(true);
      expect($('.UTubSelector[utubid="1"]').hasClass("even")).toBe(true);
      expect($('.UTubSelector[utubid="1"]').hasClass("odd")).toBe(false);
      expect($('.UTubSelector[utubid="3"]').hasClass("odd")).toBe(true);
      expect($('.UTubSelector[utubid="3"]').hasClass("even")).toBe(false);
    });

    it("restripes by full order again once the filter is cleared", () => {
      vi.mocked(filterUTubsByName).mockReturnValue([2]);
      $("#UTubNameSearch").val("a").trigger("input");
      expect($('.UTubSelector[utubid="3"]').hasClass("odd")).toBe(true);

      $("#UTubNameSearch").val("").trigger("input");

      expect($('.UTubSelector[utubid="1"]').hasClass("even")).toBe(true);
      expect($('.UTubSelector[utubid="2"]').hasClass("odd")).toBe(true);
      expect($('.UTubSelector[utubid="3"]').hasClass("even")).toBe(true);
    });
  });

  describe("UTub name filter toggle", () => {
    it("openUTubNameFilter opens the filter and swaps the toggle buttons", () => {
      openUTubNameFilter();

      expect($("#UTubDeck").hasClass("utub-search-open")).toBe(true);
      expect($("#utubNameFilterBtn").hasClass("hidden")).toBe(true);
      expect($("#utubNameFilterBtnClose").hasClass("hidden")).toBe(false);
    });

    it("closeUTubNameFilter collapses the filter and resets the search", () => {
      vi.mocked(filterUTubsByName).mockReturnValue([2]);
      openUTubNameFilter();
      $("#UTubNameSearch").val("alpha").trigger("input");
      expect($('.UTubSelector[utubid="2"]').hasClass("hidden")).toBe(true);

      closeUTubNameFilter();

      expect($("#UTubDeck").hasClass("utub-search-open")).toBe(false);
      expect($("#utubNameFilterBtnClose").hasClass("hidden")).toBe(true);
      expect($("#utubNameFilterBtn").hasClass("hidden")).toBe(false);
      expect($("#UTubNameSearch").val()).toBe("");
      $(".UTubSelector").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
    });

    it("setUTubNameFilterToggleListeners wires the funnel and close buttons", () => {
      setUTubNameFilterToggleListeners();

      $("#utubNameFilterBtn").trigger("click");
      expect($("#UTubDeck").hasClass("utub-search-open")).toBe(true);

      $("#utubNameFilterBtnClose").trigger("click");
      expect($("#UTubDeck").hasClass("utub-search-open")).toBe(false);
    });
  });
});
