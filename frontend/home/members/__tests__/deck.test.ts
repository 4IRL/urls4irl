import {
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
    <button id="memberBtnCreate" class="hidden"></button>
    <button id="memberSelfBtnDelete" class="hidden"></button>
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

  it("shows the leave button and inline count for a non-owner UTub", () => {
    window.jQuery("#listMembers").append(`<span class="member">a</span>`);

    setMemberDeckForUTub(false);

    expect(window.jQuery("#MemberDeckCount").text()).toBe("(2)");
    expect(window.jQuery("#memberSelfBtnDelete").hasClass("hidden")).toBe(
      false,
    );
    expect(window.jQuery("#memberBtnCreate").hasClass("hidden")).toBe(true);
  });
});
