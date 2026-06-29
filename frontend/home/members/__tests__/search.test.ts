import {
  closeMemberNameFilter,
  hideMemberFilterBar,
  isMemberFilterActive,
  openMemberNameFilter,
  resetMemberFilter,
  setMemberNameFilterToggleListeners,
  setMemberSelectorSearchEventListener,
  showMemberFilterBar,
} from "../search.js";

import { APP_CONFIG } from "../../../lib/config.js";

import { filterMembersByName } from "../../../logic/member-search.js";

vi.mock("../../../logic/member-search.js", () => ({
  filterMembersByName: vi.fn(() => []),
}));

const $ = window.jQuery;

const FILTER_HTML = `
  <div id="MemberDeck">
    <button id="memberNameFilterBtn" aria-expanded="false"></button>
    <button id="memberNameFilterBtnClose" class="hidden"></button>
    <div id="SearchMemberWrap">
      <div class="text-input-inner-container">
        <span class="member-search-prefix-icon" aria-hidden="true"></span>
        <input id="MemberNameSearch" type="search" value="" />
        <label class="text-input-label" for="MemberNameSearch">Filter members</label>
      </div>
    </div>
    <p id="MemberSearchNoResults" class="hidden"></p>
    <span id="MemberSearchAnnouncement" class="visually-hidden" aria-live="polite"></span>
    <div id="displayMemberWrap">
      <div id="UTubOwner">
        <span class="member" memberid="0"><b>alice_owner</b></span>
      </div>
      <div id="listMembers">
        <span class="member" memberid="1"><b>bob_dev</b></span>
        <span class="member" memberid="2"><b>carol_design</b></span>
        <span class="member" memberid="3"><b>dave_qa</b></span>
      </div>
    </div>
  </div>
`;

describe("Member Filter", () => {
  beforeEach(() => {
    document.body.innerHTML = FILTER_HTML;
    vi.mocked(filterMembersByName).mockReset().mockReturnValue([]);
    setMemberSelectorSearchEventListener();
  });

  describe("isMemberFilterActive", () => {
    it("returns true for a non-empty term", () => {
      expect(isMemberFilterActive("a")).toBe(true);
    });

    it("returns false for an empty term", () => {
      expect(isMemberFilterActive("")).toBe(false);
    });
  });

  describe("resetMemberFilter", () => {
    it("clears the input, unhides all rows in both containers, and hides the no-results message", () => {
      $("#MemberNameSearch").val("some search text");
      $("#UTubOwner .member, #listMembers .member").addClass("hidden");
      $("#MemberSearchNoResults")
        .removeClass("hidden")
        .text(APP_CONFIG.strings.MEMBER_SEARCH_NO_RESULTS);

      resetMemberFilter();

      expect($("#MemberNameSearch").val()).toBe("");
      $("#UTubOwner .member, #listMembers .member").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
      expect($("#MemberSearchNoResults").hasClass("hidden")).toBe(true);
      expect($("#MemberSearchNoResults").text()).toBe("");
    });
  });

  describe("typing into #MemberNameSearch", () => {
    it("hides member rows returned by filterMembersByName across both containers", () => {
      vi.mocked(filterMembersByName).mockReturnValue([0, 2]);

      $("#MemberNameSearch").val("bob").trigger("input");

      expect($('.member[memberid="0"]').hasClass("hidden")).toBe(true);
      expect($('.member[memberid="1"]').hasClass("hidden")).toBe(false);
      expect($('.member[memberid="2"]').hasClass("hidden")).toBe(true);
      expect($('.member[memberid="3"]').hasClass("hidden")).toBe(false);
    });

    it("shows all member rows when search input is empty", () => {
      vi.mocked(filterMembersByName).mockReturnValue([2]);
      $("#MemberNameSearch").val("carol").trigger("input");
      expect($('.member[memberid="2"]').hasClass("hidden")).toBe(true);

      $("#MemberNameSearch").val("").trigger("input");

      $("#UTubOwner .member, #listMembers .member").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
    });

    it("shows the no-results message when all members are filtered out", () => {
      vi.mocked(filterMembersByName).mockReturnValue([0, 1, 2, 3]);

      $("#MemberNameSearch").val("zzzzz").trigger("input");

      const noResults = $("#MemberSearchNoResults");
      expect(noResults.hasClass("hidden")).toBe(false);
      expect(noResults.text()).toBe(
        APP_CONFIG.strings.MEMBER_SEARCH_NO_RESULTS,
      );
    });

    it("hides the no-results message when search has matches", () => {
      vi.mocked(filterMembersByName).mockReturnValue([0, 1, 2, 3]);
      $("#MemberNameSearch").val("zzzzz").trigger("input");
      expect($("#MemberSearchNoResults").hasClass("hidden")).toBe(false);

      vi.mocked(filterMembersByName).mockReturnValue([2]);
      $("#MemberNameSearch").val("bob").trigger("input");

      expect($("#MemberSearchNoResults").hasClass("hidden")).toBe(true);
    });

    it("updates the accessibility announcement with visible/total counts", () => {
      vi.mocked(filterMembersByName).mockReturnValue([2]);

      $("#MemberNameSearch").val("bob").trigger("input");

      const expectedAnnouncement =
        APP_CONFIG.strings.MEMBER_SEARCH_COUNT_TEMPLATE.replace(
          "{{ visible }}",
          "3",
        ).replace("{{ total }}", "4");
      expect($("#MemberSearchAnnouncement").text()).toBe(expectedAnnouncement);
    });

    it("announces 'No members found' when no members match", () => {
      vi.mocked(filterMembersByName).mockReturnValue([0, 1, 2, 3]);

      $("#MemberNameSearch").val("zzzzz").trigger("input");

      expect($("#MemberSearchAnnouncement").text()).toBe(
        APP_CONFIG.strings.MEMBER_SEARCH_NO_RESULTS,
      );
    });

    it("hides the owner row when the term does not match the owner", () => {
      vi.mocked(filterMembersByName).mockReturnValue([0]);

      $("#MemberNameSearch").val("bob").trigger("input");

      expect($("#UTubOwner .member").hasClass("hidden")).toBe(true);
    });
  });

  describe("applyAlternatingMemberBackground (re-stripe)", () => {
    it("stripes visible #listMembers rows anchored on the owner and never stripes the owner", () => {
      vi.mocked(filterMembersByName).mockReturnValue([1]);

      $("#MemberNameSearch").val("o").trigger("input");

      // Owner visible (index 0), so #listMembers parity starts at 1.
      // memberid=1 is hidden; remaining visible: 2 (parity index 1 -> striped),
      // 3 (parity index 2 -> not striped).
      expect($("#UTubOwner .member").hasClass("member-stripe")).toBe(false);
      expect($('.member[memberid="2"]').hasClass("member-stripe")).toBe(true);
      expect($('.member[memberid="3"]').hasClass("member-stripe")).toBe(false);

      // Owner hidden, so #listMembers parity re-anchors starting at 0.
      // memberid=1 visible (parity index 0 -> not striped),
      // 2 (parity index 1 -> striped), 3 (parity index 2 -> not striped).
      vi.mocked(filterMembersByName).mockReturnValue([0]);
      $("#MemberNameSearch").val("dev").trigger("input");

      expect($("#UTubOwner .member").hasClass("member-stripe")).toBe(false);
      expect($('.member[memberid="1"]').hasClass("member-stripe")).toBe(false);
      expect($('.member[memberid="2"]').hasClass("member-stripe")).toBe(true);
      expect($('.member[memberid="3"]').hasClass("member-stripe")).toBe(false);
    });
  });

  describe("pressing Escape", () => {
    it("clears the input and shows all member rows", () => {
      vi.mocked(filterMembersByName).mockReturnValue([0, 1, 2, 3]);
      $("#MemberNameSearch").val("zzzzz").trigger("input");
      expect($("#MemberSearchNoResults").hasClass("hidden")).toBe(false);

      $("#MemberNameSearch").trigger("focus");
      $("#MemberNameSearch").trigger($.Event("keydown", { key: "Escape" }));

      expect($("#MemberNameSearch").val()).toBe("");
      $("#UTubOwner .member, #listMembers .member").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
      expect($("#MemberSearchNoResults").hasClass("hidden")).toBe(true);
    });
  });

  describe("member name filter toggle", () => {
    it("openMemberNameFilter opens the filter, swaps buttons, and sets aria-expanded", () => {
      openMemberNameFilter();

      expect($("#MemberDeck").hasClass("member-search-open")).toBe(true);
      expect($("#memberNameFilterBtn").hasClass("hidden")).toBe(true);
      expect($("#memberNameFilterBtnClose").hasClass("hidden")).toBe(false);
      expect($("#memberNameFilterBtn").attr("aria-expanded")).toBe("true");
    });

    it("closeMemberNameFilter collapses the filter, resets the search, and sets aria-expanded false", () => {
      vi.mocked(filterMembersByName).mockReturnValue([2]);
      openMemberNameFilter();
      $("#MemberNameSearch").val("carol").trigger("input");
      expect($('.member[memberid="2"]').hasClass("hidden")).toBe(true);

      closeMemberNameFilter();

      expect($("#MemberDeck").hasClass("member-search-open")).toBe(false);
      expect($("#memberNameFilterBtnClose").hasClass("hidden")).toBe(true);
      expect($("#memberNameFilterBtn").hasClass("hidden")).toBe(false);
      expect($("#memberNameFilterBtn").attr("aria-expanded")).toBe("false");
      expect($("#MemberNameSearch").val()).toBe("");
      $("#UTubOwner .member, #listMembers .member").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
    });

    it("setMemberNameFilterToggleListeners wires the funnel and close buttons", () => {
      setMemberNameFilterToggleListeners();

      $("#memberNameFilterBtn").trigger("click");
      expect($("#MemberDeck").hasClass("member-search-open")).toBe(true);

      $("#memberNameFilterBtnClose").trigger("click");
      expect($("#MemberDeck").hasClass("member-search-open")).toBe(false);
    });
  });

  describe("showMemberFilterBar", () => {
    it("reveals the funnel toggle, keeps the box collapsed, and does not touch #SearchMemberWrap .hidden", () => {
      $("#memberNameFilterBtn").addClass("hidden");
      $("#MemberDeck").addClass("member-search-open");
      expect($("#SearchMemberWrap").hasClass("hidden")).toBe(false);

      showMemberFilterBar();

      expect($("#memberNameFilterBtn").hasClass("hidden")).toBe(false);
      expect($("#MemberDeck").hasClass("member-search-open")).toBe(false);
      expect($("#SearchMemberWrap").hasClass("hidden")).toBe(false);
    });
  });

  describe("hideMemberFilterBar", () => {
    it("hides the toggles, removes .member-search-open, resets the filter, and does not add .hidden to #SearchMemberWrap", () => {
      vi.mocked(filterMembersByName).mockReturnValue([2]);
      openMemberNameFilter();
      $("#MemberNameSearch").val("carol").trigger("input");
      expect($('.member[memberid="2"]').hasClass("hidden")).toBe(true);

      hideMemberFilterBar();

      expect($("#memberNameFilterBtn").hasClass("hidden")).toBe(true);
      expect($("#memberNameFilterBtnClose").hasClass("hidden")).toBe(true);
      expect($("#MemberDeck").hasClass("member-search-open")).toBe(false);
      expect($("#MemberNameSearch").val()).toBe("");
      $("#UTubOwner .member, #listMembers .member").each(function () {
        expect($(this).hasClass("hidden")).toBe(false);
      });
      expect($("#SearchMemberWrap").hasClass("hidden")).toBe(false);
    });
  });
});
