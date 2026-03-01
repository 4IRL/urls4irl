import {
  setUTubSelectorSearchEventListener,
  closeUTubSearchAndEraseInput,
} from "../search.js";

vi.mock("../../../logic/utub-search.js", () => ({
  filterUTubsByName: vi.fn(() => []),
}));

const $ = window.jQuery;

const SEARCH_HTML = `
  <div id="SearchUTubWrap" class="hidden"></div>
  <span id="UTubSearchFilterIcon"></span>
  <span id="UTubSearchFilterIconClose" class="hidden"></span>
  <input id="UTubNameSearch" value="" />
  <div id="UTubDeckSubheader"></div>
  <div class="UTubSelector" utubid="1"></div>
  <div class="UTubSelector" utubid="2"></div>
  <div class="UTubSelector" utubid="3"></div>
`;

describe("UTub Search", () => {
  beforeEach(() => {
    document.body.innerHTML = SEARCH_HTML;
    setUTubSelectorSearchEventListener();
  });

  describe("closeUTubSearchAndEraseInput", () => {
    it("hides #SearchUTubWrap and shows #UTubDeckSubheader", () => {
      $("#SearchUTubWrap").addClass("visible").removeClass("hidden");
      $("#UTubDeckSubheader").addClass("hidden");

      closeUTubSearchAndEraseInput();

      expect($("#SearchUTubWrap").hasClass("hidden")).toBe(true);
      expect($("#SearchUTubWrap").hasClass("visible")).toBe(false);
      expect($("#UTubDeckSubheader").hasClass("hidden")).toBe(false);
    });

    it("shows search icon and hides close icon", () => {
      $("#UTubSearchFilterIconClose").removeClass("hidden");
      $("#UTubSearchFilterIcon").addClass("hidden");

      closeUTubSearchAndEraseInput();

      expect($("#UTubSearchFilterIcon").hasClass("hidden")).toBe(false);
      expect($("#UTubSearchFilterIconClose").hasClass("hidden")).toBe(true);
    });

    it("clears the search input value", () => {
      $("#UTubNameSearch").val("some search text");

      closeUTubSearchAndEraseInput();

      expect($("#UTubNameSearch").val()).toBe("");
    });

    it("removes hidden class from all .UTubSelector elements", () => {
      $(".UTubSelector").addClass("hidden");

      closeUTubSearchAndEraseInput();

      $(".UTubSelector").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
    });
  });

  describe("clicking #UTubSearchFilterIcon", () => {
    it("makes #SearchUTubWrap visible and hides #UTubDeckSubheader", () => {
      $("#UTubSearchFilterIcon").trigger("click");

      expect($("#SearchUTubWrap").hasClass("visible")).toBe(true);
      expect($("#SearchUTubWrap").hasClass("hidden")).toBe(false);
      expect($("#UTubDeckSubheader").hasClass("hidden")).toBe(true);
    });

    it("shows close icon and hides search icon", () => {
      $("#UTubSearchFilterIcon").trigger("click");

      expect($("#UTubSearchFilterIconClose").hasClass("hidden")).toBe(false);
      expect($("#UTubSearchFilterIcon").hasClass("hidden")).toBe(true);
    });
  });

  describe("clicking #UTubSearchFilterIconClose", () => {
    beforeEach(() => {
      $("#UTubSearchFilterIcon").trigger("click");
    });

    it("resets to closed state matching closeUTubSearchAndEraseInput", () => {
      $("#UTubSearchFilterIconClose").trigger("click");

      expect($("#SearchUTubWrap").hasClass("hidden")).toBe(true);
      expect($("#SearchUTubWrap").hasClass("visible")).toBe(false);
      expect($("#UTubDeckSubheader").hasClass("hidden")).toBe(false);
      expect($("#UTubSearchFilterIcon").hasClass("hidden")).toBe(false);
      expect($("#UTubSearchFilterIconClose").hasClass("hidden")).toBe(true);
    });
  });
});
