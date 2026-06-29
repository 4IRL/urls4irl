import {
  closeTagNameFilter,
  hideTagFilterBar,
  isTagFilterActive,
  openTagNameFilter,
  resetTagFilter,
  setTagNameFilterToggleListeners,
  setTagSelectorSearchEventListener,
  showTagFilterBar,
} from "../search.js";

import { APP_CONFIG } from "../../../lib/config.js";

import { filterTagsByName } from "../../../logic/tag-search.js";

vi.mock("../../../logic/tag-search.js", () => ({
  filterTagsByName: vi.fn(() => []),
}));

const $ = window.jQuery;

const FILTER_HTML = `
  <div id="TagDeck">
    <button id="tagNameFilterBtn" aria-expanded="false"></button>
    <button id="tagNameFilterBtnClose" class="hidden"></button>
    <div id="SearchTagWrap">
      <div class="text-input-inner-container">
        <span class="tag-search-prefix-icon" aria-hidden="true"></span>
        <input id="TagNameSearch" type="search" value="" />
        <label class="text-input-label" for="TagNameSearch">Filter tags</label>
      </div>
    </div>
    <p id="TagSearchNoResults" class="hidden"></p>
    <span id="TagSearchAnnouncement" class="visually-hidden" aria-live="polite"></span>
    <div id="listTags">
      <div class="tagFilter" data-utub-tag-id="1"><span>Alpha</span></div>
      <div class="tagFilter" data-utub-tag-id="2"><span>Beta</span></div>
      <div class="tagFilter" data-utub-tag-id="3"><span>Gamma</span></div>
    </div>
  </div>
`;

describe("Tag Filter", () => {
  beforeEach(() => {
    document.body.innerHTML = FILTER_HTML;
    vi.mocked(filterTagsByName).mockReset().mockReturnValue([]);
    setTagSelectorSearchEventListener();
  });

  describe("isTagFilterActive", () => {
    it("returns true at the TAGS_MIN_LENGTH threshold", () => {
      const thresholdTerm = "x".repeat(APP_CONFIG.constants.TAGS_MIN_LENGTH);

      expect(isTagFilterActive(thresholdTerm)).toBe(true);
    });

    it("returns false for an empty term", () => {
      expect(isTagFilterActive("")).toBe(false);
    });
  });

  describe("resetTagFilter", () => {
    it("clears the search input value", () => {
      $("#TagNameSearch").val("some search text");

      resetTagFilter();

      expect($("#TagNameSearch").val()).toBe("");
    });

    it("removes hidden class from all .tagFilter elements", () => {
      $(".tagFilter").addClass("hidden");

      resetTagFilter();

      $(".tagFilter").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
    });

    it("hides the no-results message", () => {
      $("#TagSearchNoResults")
        .removeClass("hidden")
        .text(APP_CONFIG.strings.TAG_SEARCH_NO_RESULTS);

      resetTagFilter();

      expect($("#TagSearchNoResults").hasClass("hidden")).toBe(true);
      expect($("#TagSearchNoResults").text()).toBe("");
    });
  });

  describe("typing into #TagNameSearch", () => {
    it("hides tag rows returned by filterTagsByName", () => {
      vi.mocked(filterTagsByName).mockReturnValue([2]);

      $("#TagNameSearch").val("alpha").trigger("input");

      expect($('.tagFilter[data-utub-tag-id="1"]').hasClass("hidden")).toBe(
        false,
      );
      expect($('.tagFilter[data-utub-tag-id="2"]').hasClass("hidden")).toBe(
        true,
      );
      expect($('.tagFilter[data-utub-tag-id="3"]').hasClass("hidden")).toBe(
        false,
      );
    });

    it("shows all tag rows when search input is empty", () => {
      vi.mocked(filterTagsByName).mockReturnValue([2]);
      $("#TagNameSearch").val("alpha").trigger("input");
      expect($('.tagFilter[data-utub-tag-id="2"]').hasClass("hidden")).toBe(
        true,
      );

      $("#TagNameSearch").val("").trigger("input");

      $(".tagFilter").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
    });

    it("shows the no-results message when all tags are filtered out", () => {
      vi.mocked(filterTagsByName).mockReturnValue([1, 2, 3]);

      $("#TagNameSearch").val("zzzzz").trigger("input");

      const noResults = $("#TagSearchNoResults");
      expect(noResults.hasClass("hidden")).toBe(false);
      expect(noResults.text()).toBe(APP_CONFIG.strings.TAG_SEARCH_NO_RESULTS);
    });

    it("hides the no-results message when search has matches", () => {
      vi.mocked(filterTagsByName).mockReturnValue([1, 2, 3]);
      $("#TagNameSearch").val("zzzzz").trigger("input");
      expect($("#TagSearchNoResults").hasClass("hidden")).toBe(false);

      vi.mocked(filterTagsByName).mockReturnValue([2]);
      $("#TagNameSearch").val("alpha").trigger("input");

      expect($("#TagSearchNoResults").hasClass("hidden")).toBe(true);
    });

    it("updates the accessibility announcement with visible/total counts", () => {
      vi.mocked(filterTagsByName).mockReturnValue([2]);

      $("#TagNameSearch").val("alpha").trigger("input");

      const expectedAnnouncement =
        APP_CONFIG.strings.TAG_SEARCH_COUNT_TEMPLATE.replace(
          "{{ visible }}",
          "2",
        ).replace("{{ total }}", "3");
      expect($("#TagSearchAnnouncement").text()).toBe(expectedAnnouncement);
    });

    it("announces 'No tags found' when no tags match", () => {
      vi.mocked(filterTagsByName).mockReturnValue([1, 2, 3]);

      $("#TagNameSearch").val("zzzzz").trigger("input");

      expect($("#TagSearchAnnouncement").text()).toBe(
        APP_CONFIG.strings.TAG_SEARCH_NO_RESULTS,
      );
    });
  });

  describe("pressing Escape", () => {
    it("clears the input and shows all tag rows", () => {
      vi.mocked(filterTagsByName).mockReturnValue([1, 2, 3]);
      $("#TagNameSearch").val("zzzzz").trigger("input");
      expect($("#TagSearchNoResults").hasClass("hidden")).toBe(false);

      $("#TagNameSearch").trigger("focus");
      $("#TagNameSearch").trigger($.Event("keydown", { key: "Escape" }));

      expect($("#TagNameSearch").val()).toBe("");
      $(".tagFilter").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
      expect($("#TagSearchNoResults").hasClass("hidden")).toBe(true);
    });
  });

  describe("tag name filter toggle", () => {
    it("openTagNameFilter opens the filter and swaps the toggle buttons", () => {
      openTagNameFilter();

      expect($("#TagDeck").hasClass("tag-search-open")).toBe(true);
      expect($("#tagNameFilterBtn").hasClass("hidden")).toBe(true);
      expect($("#tagNameFilterBtn").attr("aria-expanded")).toBe("true");
      expect($("#tagNameFilterBtnClose").hasClass("hidden")).toBe(false);
    });

    it("closeTagNameFilter collapses the filter and resets the search", () => {
      vi.mocked(filterTagsByName).mockReturnValue([2]);
      openTagNameFilter();
      $("#TagNameSearch").val("alpha").trigger("input");
      expect($('.tagFilter[data-utub-tag-id="2"]').hasClass("hidden")).toBe(
        true,
      );

      closeTagNameFilter();

      expect($("#TagDeck").hasClass("tag-search-open")).toBe(false);
      expect($("#tagNameFilterBtnClose").hasClass("hidden")).toBe(true);
      expect($("#tagNameFilterBtn").hasClass("hidden")).toBe(false);
      expect($("#tagNameFilterBtn").attr("aria-expanded")).toBe("false");
      expect($("#TagNameSearch").val()).toBe("");
      $(".tagFilter").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
    });

    it("setTagNameFilterToggleListeners wires the funnel and close buttons", () => {
      setTagNameFilterToggleListeners();

      $("#tagNameFilterBtn").trigger("click");
      expect($("#TagDeck").hasClass("tag-search-open")).toBe(true);

      $("#tagNameFilterBtnClose").trigger("click");
      expect($("#TagDeck").hasClass("tag-search-open")).toBe(false);
    });
  });

  describe("showTagFilterBar", () => {
    it("reveals the funnel toggle and keeps the box collapsed", () => {
      $("#tagNameFilterBtn").addClass("hidden");
      $("#TagDeck").addClass("tag-search-open");

      showTagFilterBar();

      expect($("#tagNameFilterBtn").hasClass("hidden")).toBe(false);
      expect($("#TagDeck").hasClass("tag-search-open")).toBe(false);
    });

    it("does NOT add or remove .hidden on #SearchTagWrap", () => {
      expect($("#SearchTagWrap").hasClass("hidden")).toBe(false);

      showTagFilterBar();

      expect($("#SearchTagWrap").hasClass("hidden")).toBe(false);
    });
  });

  describe("hideTagFilterBar", () => {
    it("hides the funnel toggle, removes .tag-search-open, and resets the filter", () => {
      vi.mocked(filterTagsByName).mockReturnValue([2]);
      openTagNameFilter();
      $("#TagNameSearch").val("alpha").trigger("input");
      expect($('.tagFilter[data-utub-tag-id="2"]').hasClass("hidden")).toBe(
        true,
      );

      hideTagFilterBar();

      expect($("#tagNameFilterBtn").hasClass("hidden")).toBe(true);
      expect($("#tagNameFilterBtnClose").hasClass("hidden")).toBe(true);
      expect($("#TagDeck").hasClass("tag-search-open")).toBe(false);
      expect($("#TagNameSearch").val()).toBe("");
      $(".tagFilter").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
    });

    it("does NOT add .hidden to #SearchTagWrap", () => {
      hideTagFilterBar();

      expect($("#SearchTagWrap").hasClass("hidden")).toBe(false);
    });
  });
});
