import { setMemberDeckOnUTubSelected } from "../deck.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";

// Real members.js / row-menu.js / deck.js: a permission change delivered by the
// stale-data refresh rebuilds the deck through setMemberDeckOnUTubSelected, so
// driving it with a changed isCoCreator proves the kebab set follows the role.
vi.mock("../create.js", () => ({
  setupShowCreateMemberFormEventListeners: vi.fn(),
}));
vi.mock("../delete.js", () => ({
  createLeaveUTubAsMemberIcon: vi.fn(),
  removeMemberShowModal: vi.fn(),
}));
vi.mock("../../btns-forms.js", () => ({ hideInputs: vi.fn() }));
vi.mock("../../urls/cards/selection.js", () => ({ deselectAllURLs: vi.fn() }));

import { createLeaveUTubAsMemberIcon } from "../delete.js";

const $ = window.jQuery;

const DECK_HTML = `
  <div id="MemberDeck">
    <button type="button" id="MemberDeckHeaderAndCaret">
      <span id="MemberDeckHeader">Members<span id="MemberDeckCount"></span></span>
    </button>
    <button id="memberNameFilterBtn" class="hidden"></button>
    <button id="memberNameFilterBtnClose" class="hidden"></button>
    <button id="memberBtnCreate" class="hidden"></button>
    <div id="MemberDeckNotice" class="hidden"></div>
    <button id="memberSelfBtnDelete" class="hidden"></button>
    <input id="MemberNameSearch" type="search" value="" />
    <p id="MemberSearchNoResults" class="hidden"></p>
    <div id="displayMemberWrap" class="flex-column hidden">
      <div id="UTubOwner"></div>
      <div id="listMembers"></div>
    </div>
  </div>
`;

const MEMBERS = [
  { id: 1, username: "owner", memberRole: "creator", joinedAt: null },
  { id: 2, username: "coowner", memberRole: "cocreator", joinedAt: null },
  { id: 3, username: "plain", memberRole: "member", joinedAt: null },
];

function rebuild({
  isCoCreator,
  currentUserID,
}: {
  isCoCreator: boolean;
  currentUserID: number;
}): void {
  setState({
    members: MEMBERS,
    isCurrentUserOwner: false,
    isCoCreator,
    activeUTubID: 42,
  });
  setMemberDeckOnUTubSelected(MEMBERS, 1, false, currentUserID, 42);
}

describe("member deck rebuild after a permission change", () => {
  beforeEach(() => {
    document.body.innerHTML = DECK_HTML;
    resetStore();
    vi.clearAllMocks();
  });

  afterEach(() => {
    resetStore();
  });

  it("a promoted viewer gets a kebab on plain-member rows only", () => {
    rebuild({ isCoCreator: false, currentUserID: 3 });
    expect($(".memberRowKebab").length).toBe(0);

    rebuild({ isCoCreator: true, currentUserID: 2 });

    const kebabs = $("#listMembers .memberRowKebab--coOwner");
    expect(kebabs.length).toBe(1);
    expect(kebabs.closest(".member").attr("memberid")).toBe("3");
    expect($(".memberRowKebab").length).toBe(1);
  });

  it("a demoted viewer loses every kebab", () => {
    rebuild({ isCoCreator: true, currentUserID: 2 });
    expect($(".memberRowKebab").length).toBe(1);

    rebuild({ isCoCreator: false, currentUserID: 2 });

    expect($(".memberRowKebab").length).toBe(0);
    expect($(".memberRowMenu").length).toBe(0);
  });

  it("the Leave control still targets the viewer's own id after the role change", () => {
    rebuild({ isCoCreator: true, currentUserID: 2 });
    rebuild({ isCoCreator: false, currentUserID: 2 });

    const calls = vi.mocked(createLeaveUTubAsMemberIcon).mock.calls;
    expect(calls.length).toBeGreaterThan(0);
    for (const [args] of calls) {
      expect(args).toEqual({ currentUserID: 2, utubID: 42 });
    }
    expect(getState().isCoCreator).toBe(false);
  });
});
