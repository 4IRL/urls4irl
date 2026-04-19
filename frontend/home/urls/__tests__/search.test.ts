import {
  setURLSearchEventListener,
  closeURLSearchAndEraseInput,
  showURLSearchIcon,
  hideURLSearchIcon,
} from "../search.js";

import { filterURLsBySearchTerm } from "../../../logic/url-search.js";

vi.mock("../../../logic/url-search.js", () => ({
  filterURLsBySearchTerm: vi.fn(() => []),
}));

const $ = window.jQuery;

const SEARCH_HTML = `
  <button id="urlSearchFilterIcon"></button>
  <button id="urlSearchFilterIconClose" class="hidden"></button>
  <div id="SearchURLWrap" class="hidden"></div>
  <input id="URLContentSearch" value="" />
  <div id="UTubDescriptionSubheaderWrap"></div>
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

  describe("clicking #urlSearchFilterIcon", () => {
    it("shows #SearchURLWrap and hides #UTubDescriptionSubheaderWrap", () => {
      $("#urlSearchFilterIcon").trigger("click");

      expect($("#SearchURLWrap").hasClass("visible")).toBe(true);
      expect($("#SearchURLWrap").hasClass("hidden")).toBe(false);
      expect($("#UTubDescriptionSubheaderWrap").hasClass("hidden")).toBe(true);
    });

    it("shows close icon and hides search icon", () => {
      $("#urlSearchFilterIcon").trigger("click");

      expect($("#urlSearchFilterIconClose").hasClass("hidden")).toBe(false);
      expect($("#urlSearchFilterIcon").hasClass("hidden")).toBe(true);
    });

    it("adds url-search-expanded class to input and focuses it", async () => {
      $("#urlSearchFilterIcon").trigger("click");

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

  describe("clicking #urlSearchFilterIconClose", () => {
    beforeEach(() => {
      $("#urlSearchFilterIcon").trigger("click");
    });

    it("hides search wrap and shows description subheader", () => {
      $("#urlSearchFilterIconClose").trigger("click");

      expect($("#SearchURLWrap").hasClass("hidden")).toBe(true);
      expect($("#SearchURLWrap").hasClass("visible")).toBe(false);
      expect($("#UTubDescriptionSubheaderWrap").hasClass("hidden")).toBe(false);
    });

    it("shows search icon and hides close icon", () => {
      $("#urlSearchFilterIconClose").trigger("click");

      expect($("#urlSearchFilterIcon").hasClass("hidden")).toBe(false);
      expect($("#urlSearchFilterIconClose").hasClass("hidden")).toBe(true);
    });

    it("clears the search input value", () => {
      $("#URLContentSearch").val("some search text");

      $("#urlSearchFilterIconClose").trigger("click");

      expect($("#URLContentSearch").val()).toBe("");
    });

    it("removes searchable attribute from all .urlRow elements", () => {
      $(".urlRow").attr("searchable", "false");

      $("#urlSearchFilterIconClose").trigger("click");

      $(".urlRow").each(function () {
        expect($(this).attr("searchable")).toBeUndefined();
      });
    });
  });

  describe("typing into #URLContentSearch", () => {
    beforeEach(() => {
      $("#urlSearchFilterIcon").trigger("click");
    });

    it("calls filterURLsBySearchTerm with only filterable=true URLs", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);

      $("#URLContentSearch").val("alpha").trigger("input");

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

      expect($('.urlRow[utuburlid="1"]').attr("searchable")).toBe("true");
      expect($('.urlRow[utuburlid="2"]').attr("searchable")).toBe("false");
      expect($('.urlRow[utuburlid="4"]').attr("searchable")).toBe("true");
    });

    it("never modifies searchable attribute on filterable=false urlRow elements", () => {
      vi.mocked(filterURLsBySearchTerm).mockReturnValue([2]);

      $("#URLContentSearch").val("alpha").trigger("input");

      expect($('.urlRow[utuburlid="3"]').attr("searchable")).toBeUndefined();
    });
  });

  describe("pressing Escape", () => {
    it("closes search the same as clicking close icon", () => {
      $("#urlSearchFilterIcon").trigger("click");

      $("#URLContentSearch").trigger("focus");
      $("#URLContentSearch").trigger($.Event("keydown", { key: "Escape" }));

      expect($("#SearchURLWrap").hasClass("hidden")).toBe(true);
      expect($("#SearchURLWrap").hasClass("visible")).toBe(false);
      expect($("#UTubDescriptionSubheaderWrap").hasClass("hidden")).toBe(false);
      expect($("#urlSearchFilterIcon").hasClass("hidden")).toBe(false);
      expect($("#urlSearchFilterIconClose").hasClass("hidden")).toBe(true);
    });
  });

  describe("closeURLSearchAndEraseInput", () => {
    it("hides #SearchURLWrap and shows #UTubDescriptionSubheaderWrap", () => {
      $("#SearchURLWrap").addClass("visible").removeClass("hidden");
      $("#UTubDescriptionSubheaderWrap").addClass("hidden");

      closeURLSearchAndEraseInput();

      expect($("#SearchURLWrap").hasClass("hidden")).toBe(true);
      expect($("#SearchURLWrap").hasClass("visible")).toBe(false);
      expect($("#UTubDescriptionSubheaderWrap").hasClass("hidden")).toBe(false);
    });

    it("shows search icon and hides close icon", () => {
      $("#urlSearchFilterIconClose").removeClass("hidden");
      $("#urlSearchFilterIcon").addClass("hidden");

      closeURLSearchAndEraseInput();

      expect($("#urlSearchFilterIcon").hasClass("hidden")).toBe(false);
      expect($("#urlSearchFilterIconClose").hasClass("hidden")).toBe(true);
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
      $("#urlSearchFilterIcon").addClass("hidden");

      showURLSearchIcon();

      expect($("#urlSearchFilterIcon").hasClass("hidden")).toBe(false);
    });
  });

  describe("hideURLSearchIcon", () => {
    it("hides the search icon", () => {
      $("#urlSearchFilterIcon").removeClass("hidden");

      hideURLSearchIcon();

      expect($("#urlSearchFilterIcon").hasClass("hidden")).toBe(true);
    });
  });
});
