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

import { bootstrap } from "../../../lib/globals.js";

vi.mock("../../../logic/utub-search.js", () => ({
  filterUTubsByName: vi.fn(() => []),
}));

// The ambient test-setup Bootstrap mock returns null from getInstance(), which
// would make the tooltip-hide guard a silent no-op. Override lib/globals.js with
// a shared tooltip instance so the guard can be asserted on.
const { tooltipInstance, globalsMock } = await vi.hoisted(async () => {
  const { mockGlobalsWithTooltipInstance } =
    await import("../../../__tests__/helpers/mock-globals.js");
  return await mockGlobalsWithTooltipInstance();
});

vi.mock("../../../lib/globals.js", () => globalsMock);

const $ = window.jQuery;

const SEARCH_HTML = `
  <div id="UTubDeck">
    <button id="utubNameFilterBtn" aria-expanded="false"></button>
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
    <!-- The Member deck's own disclosure button. It lives in the sibling
         #MemberDeck in production; it is mounted here because the Escape
         handler's last-resort focus target is this button, and without it the
         fallback branch cannot be exercised at all. -->
    <button type="button" id="MemberDeckHeaderAndCaret" aria-expanded="true" aria-controls="MemberDeckContent"></button>
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

    // Focus is handed to the first visible UTub row when there is one. With no
    // rows at all (a brand-new account, or the last UTub just deleted) the next
    // target is #memberBtnCreate in the deck below — the closest live control.
    it("returns focus to #memberBtnCreate when there is no UTub row to return to", () => {
      $("#listUTubs").empty();

      $("#UTubNameSearch").trigger("focus");
      $("#UTubNameSearch").trigger($.Event("keydown", { key: "Escape" }));

      expect(document.activeElement).toBe(
        document.getElementById("memberBtnCreate"),
      );
    });

    // #memberBtnCreate sits in the Member deck's .button-container, which is
    // visibility:hidden while that deck is collapsed — focusing it there is a
    // silent no-op that drops focus to <body>. The fallback is the Member
    // deck's own header button, which is never hidden.
    it("falls back to the Member deck header when #memberBtnCreate is unfocusable", () => {
      $("#listUTubs").empty();
      const memberBtnCreate = document.getElementById(
        "memberBtnCreate",
      ) as HTMLElement;
      // decks.css is never loaded into the test DOM, so stand the collapsed
      // deck's inherited visibility:hidden up directly on the button.
      memberBtnCreate.style.visibility = "hidden";

      $("#UTubNameSearch").trigger("focus");
      $("#UTubNameSearch").trigger($.Event("keydown", { key: "Escape" }));

      expect(document.activeElement).toBe(
        document.getElementById("MemberDeckHeaderAndCaret"),
      );
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
    // Records whether #utubNameFilterBtn already carried the `hidden` class at
    // the moment hide() ran. Asserting it is false proves the tooltip is hidden
    // BEFORE the button — swapping the two production lines flips it to true.
    let buttonHiddenWhenTooltipHidden: boolean | null = null;

    beforeEach(() => {
      buttonHiddenWhenTooltipHidden = null;
      tooltipInstance.hide.mockClear();
      tooltipInstance.hide.mockImplementation(() => {
        buttonHiddenWhenTooltipHidden =
          $("#utubNameFilterBtn").hasClass("hidden");
      });
    });

    afterEach(() => {
      // Drop the recording implementation so it cannot leak into other describes
      // that share this hoisted tooltipInstance.
      tooltipInstance.hide.mockReset();
    });

    it("openUTubNameFilter opens the filter and swaps the toggle buttons", () => {
      openUTubNameFilter();

      expect($("#UTubDeck").hasClass("utub-search-open")).toBe(true);
      expect($("#utubNameFilterBtn").hasClass("hidden")).toBe(true);
      expect($("#utubNameFilterBtn").attr("aria-expanded")).toBe("true");
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
      expect($("#utubNameFilterBtn").attr("aria-expanded")).toBe("false");
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

    it("hides the funnel button's hover tooltip before the click hides the button", () => {
      setUTubNameFilterToggleListeners();

      $("#utubNameFilterBtn").trigger("click.utubNameFilterShow");

      expect(tooltipInstance.hide).toHaveBeenCalled();
      expect(buttonHiddenWhenTooltipHidden).toBe(false);
      expect($("#utubNameFilterBtn").hasClass("hidden")).toBe(true);
    });

    it("still hides the funnel button and does not throw when no tooltip instance exists", () => {
      // Touch devices never construct a Tooltip, so getInstance() returns null
      // and the `?.` guard must no-op without breaking the toggle.
      vi.mocked(bootstrap.Tooltip.getInstance).mockReturnValueOnce(null);
      setUTubNameFilterToggleListeners();

      expect(() =>
        $("#utubNameFilterBtn").trigger("click.utubNameFilterShow"),
      ).not.toThrow();

      expect(tooltipInstance.hide).not.toHaveBeenCalled();
      expect($("#utubNameFilterBtn").hasClass("hidden")).toBe(true);
    });
  });
});
