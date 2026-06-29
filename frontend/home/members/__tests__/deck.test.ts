import {
  resetMemberDeck,
  setMemberDeckForUTub,
  setMemberDeckOnUTubSelected,
  setMemberDeckWhenNoUTubSelected,
} from "../deck.js";

vi.mock("../../../logic/apply-deck-diff.js", () => ({
  applyDeckDiff: vi.fn(),
}));

vi.mock("../members.js", () => ({
  createMemberBadge: vi.fn(() =>
    window.jQuery(`<span class="member">member</span>`),
  ),
  createOwnerBadge: vi.fn(() =>
    window.jQuery(`<span class="member">owner</span>`),
  ),
}));

vi.mock("../create.js", () => ({
  setupShowCreateMemberFormEventListeners: vi.fn(),
}));

vi.mock("../delete.js", () => ({
  createLeaveUTubAsMemberIcon: vi.fn(),
}));

const MEMBER_DECK_HTML = `
  <div id="MemberDeck">
    <div class="titleElement">
      <h2 id="MemberDeckHeader">Members<span id="MemberDeckCount" class="deck-title-count"></span></h2>
    </div>
    <button id="memberNameFilterBtn" class="hidden" aria-expanded="false"></button>
    <button id="memberNameFilterBtnClose" class="hidden"></button>
    <button id="memberBtnCreate" class="hidden"></button>
    <button id="memberSelfBtnDelete" class="hidden"></button>
    <div id="SearchMemberWrap">
      <input id="MemberNameSearch" type="search" value="" />
    </div>
    <p id="MemberSearchNoResults" class="hidden"></p>
    <span id="MemberSearchAnnouncement" class="visually-hidden" aria-live="polite"></span>
    <div id="displayMemberWrap" class="flex-column hidden">
      <div id="UTubOwner"></div>
      <div id="listMembers"></div>
    </div>
  </div>
`;

describe("Member deck visibility on UTub selection", () => {
  beforeEach(() => {
    document.body.innerHTML = MEMBER_DECK_HTML;
  });

  it("reveals the member list and shows the inline count when a UTub is selected", () => {
    const wrap = window.jQuery("#displayMemberWrap");
    expect(wrap.hasClass("hidden")).toBe(true);

    setMemberDeckOnUTubSelected([{ id: 1, username: "owner" }], 1, true, 1, 42);

    expect(wrap.hasClass("hidden")).toBe(false);
    expect(window.jQuery("#MemberDeckCount").text()).toBe("(1)");
  });

  it("hides the member list and clears the inline count when no UTub is selected", () => {
    const wrap = window.jQuery("#displayMemberWrap");
    wrap.removeClass("hidden");
    window.jQuery("#MemberDeckCount").text("(3)");

    setMemberDeckWhenNoUTubSelected();

    expect(wrap.hasClass("hidden")).toBe(true);
    expect(window.jQuery("#MemberDeckCount").text()).toBe("");
  });

  it("shows the inline member count for a multi-member UTub", () => {
    window
      .jQuery("#listMembers")
      .append(`<span class="member">a</span><span class="member">b</span>`);

    setMemberDeckForUTub(true);

    expect(window.jQuery("#MemberDeckCount").text()).toBe("(3)");
  });

  it("hides the add-member button and shows the inline count for a non-owner UTub", () => {
    window.jQuery("#listMembers").append(`<span class="member">a</span>`);
    window.jQuery("#memberBtnCreate").removeClass("hidden");

    setMemberDeckForUTub(false);

    expect(window.jQuery("#MemberDeckCount").text()).toBe("(2)");
    // The leave button lives in the UTub deck now and is not managed here.
    expect(window.jQuery("#memberBtnCreate").hasClass("hidden")).toBe(true);
  });
});

describe("resetMemberDeck clears the member search/filter state", () => {
  beforeEach(() => {
    document.body.innerHTML = MEMBER_DECK_HTML;
  });

  it("collapses the filter bar, hides no-results, and clears the search input", () => {
    // Dirty the search/filter into an "open + active" pre-reset state.
    window.jQuery("#MemberNameSearch").val("some search text");
    window.jQuery("#MemberDeck").addClass("member-search-open");
    window.jQuery("#memberNameFilterBtnClose").removeClass("hidden");
    window.jQuery("#MemberSearchNoResults").removeClass("hidden").text("none");

    // Before-state: prove the reset is what clears these.
    expect(window.jQuery("#MemberNameSearch").val()).toBe("some search text");
    expect(window.jQuery("#MemberDeck").hasClass("member-search-open")).toBe(
      true,
    );
    expect(window.jQuery("#memberNameFilterBtnClose").hasClass("hidden")).toBe(
      false,
    );
    expect(window.jQuery("#MemberSearchNoResults").hasClass("hidden")).toBe(
      false,
    );

    resetMemberDeck();

    expect(window.jQuery("#MemberDeck").hasClass("member-search-open")).toBe(
      false,
    );
    expect(window.jQuery("#memberNameFilterBtnClose").hasClass("hidden")).toBe(
      true,
    );
    expect(window.jQuery("#MemberSearchNoResults").hasClass("hidden")).toBe(
      true,
    );
    expect(window.jQuery("#MemberNameSearch").val()).toBe("");
  });
});
