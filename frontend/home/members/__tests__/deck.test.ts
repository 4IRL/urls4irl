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
    <div class="titleElement dynamic-subheader hidden">
      <h5 id="MemberDeckSubheader"></h5>
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

  it("reveals the Owner/Members labels and subheader when a UTub is selected", () => {
    const wrap = window.jQuery("#displayMemberWrap");
    const subheader = window
      .jQuery("#MemberDeckSubheader")
      .closest(".titleElement");
    expect(wrap.hasClass("hidden")).toBe(true);
    expect(subheader.hasClass("hidden")).toBe(true);

    setMemberDeckOnUTubSelected([{ id: 1, username: "owner" }], 1, true, 1, 42);

    expect(wrap.hasClass("hidden")).toBe(false);
    expect(subheader.hasClass("hidden")).toBe(false);
    expect(window.jQuery("#MemberDeckSubheader").text()).toBe("Add a member");
  });

  it("hides the Owner/Members labels and collapses the subheader when no UTub is selected", () => {
    const wrap = window.jQuery("#displayMemberWrap");
    const subheader = window
      .jQuery("#MemberDeckSubheader")
      .closest(".titleElement");
    wrap.removeClass("hidden");
    subheader.removeClass("hidden").addClass("height-2rem");
    window.jQuery("#MemberDeckSubheader").text("3 members");

    setMemberDeckWhenNoUTubSelected();

    expect(wrap.hasClass("hidden")).toBe(true);
    expect(subheader.hasClass("hidden")).toBe(true);
    expect(subheader.hasClass("height-2rem")).toBe(false);
    expect(window.jQuery("#MemberDeckSubheader").text()).toBe("");
  });

  it("shows member count in the subheader for a multi-member UTub", () => {
    window
      .jQuery("#listMembers")
      .append(`<span class="member">a</span><span class="member">b</span>`);

    setMemberDeckForUTub(true);

    expect(window.jQuery("#MemberDeckSubheader").text()).toBe("3 members");
    expect(
      window
        .jQuery("#MemberDeckSubheader")
        .closest(".titleElement")
        .hasClass("hidden"),
    ).toBe(false);
  });

  it("shows the leave button and count-only subheader for a non-owner UTub", () => {
    window.jQuery("#listMembers").append(`<span class="member">a</span>`);

    setMemberDeckForUTub(false);

    expect(window.jQuery("#MemberDeckSubheader").text()).toBe("2 members");
    expect(
      window
        .jQuery("#MemberDeckSubheader")
        .closest(".titleElement")
        .hasClass("hidden"),
    ).toBe(false);
    expect(window.jQuery("#memberSelfBtnDelete").hasClass("hidden")).toBe(
      false,
    );
    expect(window.jQuery("#memberBtnCreate").hasClass("hidden")).toBe(true);
  });
});
