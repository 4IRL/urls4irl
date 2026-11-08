import {
  resetMemberDeck,
  setMemberDeckForUTub,
  setMemberDeckOnUTubSelected,
  setMemberDeckWhenNoUTubSelected,
  updateMemberDeck,
} from "../deck.js";
import { applyDeckDiff } from "../../../logic/apply-deck-diff.js";
import { createMemberBadge, swapMemberRoleInRow } from "../members.js";
import { makeUTubRoleIcon } from "../../utubs/selectors.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { resolveUtubSettings } from "../../../types/settings.js";
import { setupShowCreateMemberFormEventListeners } from "../create.js";
import { showMemberDeckNotice } from "../notice.js";

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
  swapMemberRoleInRow: vi.fn(),
}));

vi.mock("../create.js", () => ({
  setupShowCreateMemberFormEventListeners: vi.fn(),
}));

vi.mock("../delete.js", () => ({
  createLeaveUTubAsMemberIcon: vi.fn(),
  // The DD-17 case un-mocks members.js, whose real module imports
  // removeMemberShowModal from delete.js (used only inside a click handler the
  // test never fires) — stub it so the named import resolves.
  removeMemberShowModal: vi.fn(),
}));

const MEMBER_DECK_HTML = `
  <div id="MemberDeck">
    <div class="titleElement">
      <button type="button" id="MemberDeckHeaderAndCaret">
        <span id="MemberDeckHeader">Members<span id="MemberDeckCount" class="deck-title-count"></span></span>
      </button>
      <h2 id="MemberDeckHeaderA11y" class="visually-hidden">Members</h2>
    </div>
    <button id="memberNameFilterBtn" class="hidden" aria-expanded="false"></button>
    <button id="memberNameFilterBtnClose" class="hidden"></button>
    <button id="memberBtnCreate" class="hidden"></button>
    <div id="MemberDeckNotice" class="hidden"></div>
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
    resetStore();
    // jsdom has no layout, so every element reads as unfocusable; report all
    // as rendered. Removed in afterEach so a failed expect cannot leak the patch.
    Object.defineProperty(HTMLElement.prototype, "offsetParent", {
      configurable: true,
      get() {
        return document.body;
      },
    });
  });

  afterEach(() => {
    delete (HTMLElement.prototype as unknown as Record<string, unknown>)
      .offsetParent;
    resetStore();
  });

  it("reveals the member list and shows the inline count when a UTub is selected", () => {
    const wrap = window.jQuery("#displayMemberWrap");
    expect(wrap.hasClass("hidden")).toBe(true);

    setMemberDeckOnUTubSelected(
      [{ id: 1, username: "owner", memberRole: "creator", joinedAt: null }],
      1,
      true,
      1,
      42,
    );

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

    setMemberDeckForUTub();

    expect(window.jQuery("#MemberDeckCount").text()).toBe("(3)");
  });

  it("hides the add-member button and shows the inline count for a non-owner UTub", () => {
    window.jQuery("#listMembers").append(`<span class="member">a</span>`);
    window.jQuery("#memberBtnCreate").removeClass("hidden");

    // Default store: not owner, not co-owner, no settings -> cannot add.
    setMemberDeckForUTub();

    expect(window.jQuery("#MemberDeckCount").text()).toBe("(2)");
    // The leave button lives in the UTub deck now and is not managed here.
    expect(window.jQuery("#memberBtnCreate").hasClass("hidden")).toBe(true);
  });

  it("shows the add-member button for a non-owner co-owner on UTub selection (DD-1)", () => {
    // A co-owner (isCurrentUserOwner: false, isCoCreator: true) can add members,
    // so setMemberDeckOnUTubSelected's canManageMembers OR-gate must reveal the
    // add button even though the literal owner flag is false.
    resetStore();
    setState({ isCoCreator: true });

    setMemberDeckOnUTubSelected(
      [{ id: 1, username: "owner", memberRole: "creator", joinedAt: null }],
      1,
      false,
      1,
      42,
    );

    expect(window.jQuery("#memberBtnCreate").hasClass("hidden")).toBe(false);
  });

  it("keeps the add-member button hidden for a plain non-owner member on UTub selection (DD-12 sad path)", () => {
    // Neither owner nor co-owner: canManageMembers is false, so the add button
    // stays hidden. Guards the OR-gate against a regression that would leak the
    // add affordance to plain members.
    resetStore();
    setState({ isCoCreator: false });

    setMemberDeckOnUTubSelected(
      [{ id: 1, username: "owner", memberRole: "creator", joinedAt: null }],
      1,
      false,
      1,
      42,
    );

    expect(window.jQuery("#memberBtnCreate").hasClass("hidden")).toBe(true);
  });

  it("shows the add-member button and binds the opener for a plain member while members_can_add is on", () => {
    resetStore();
    vi.mocked(setupShowCreateMemberFormEventListeners).mockClear();
    setState({
      isCoCreator: false,
      settings: resolveUtubSettings({
        members: { members_can_add: true },
      } as never),
    });

    setMemberDeckOnUTubSelected(
      [{ id: 1, username: "owner", memberRole: "creator", joinedAt: null }],
      1,
      false,
      1,
      42,
    );

    expect(setupShowCreateMemberFormEventListeners).toHaveBeenCalledTimes(1);
    expect(setupShowCreateMemberFormEventListeners).toHaveBeenCalledWith(42);
    expect(window.jQuery("#memberBtnCreate").hasClass("hidden")).toBe(false);
  });

  it("does not bind the opener for a plain member while members_can_add is off", () => {
    resetStore();
    setState({
      settings: resolveUtubSettings({
        members: { members_can_add: false },
      } as never),
    });
    vi.mocked(setupShowCreateMemberFormEventListeners).mockClear();

    setMemberDeckOnUTubSelected(
      [{ id: 1, username: "owner", memberRole: "creator", joinedAt: null }],
      1,
      false,
      1,
      42,
    );

    expect(setupShowCreateMemberFormEventListeners).not.toHaveBeenCalled();
  });

  it("setMemberDeckForUTub reads the store, so a revoked plain member cannot be forced on", () => {
    resetStore();
    window.jQuery("#memberBtnCreate").removeClass("hidden");

    setMemberDeckForUTub();

    expect(window.jQuery("#memberBtnCreate").hasClass("hidden")).toBe(true);
  });

  it("falls back to the deck header when the rebuild destroys the focused row", () => {
    resetStore();
    window
      .jQuery("#listMembers")
      .append(
        `<span class="member" memberid="9"><button class="memberRowKebab" id="kebab9">k</button></span>`,
      );
    (document.getElementById("kebab9") as HTMLElement).focus();

    setMemberDeckOnUTubSelected(
      [{ id: 1, username: "owner", memberRole: "creator", joinedAt: null }],
      1,
      true,
      1,
      42,
    );

    expect(document.activeElement?.id).toBe("MemberDeckHeaderAndCaret");
  });

  it("falls back to the deck header when the rebuild destroys a focused bare row", () => {
    resetStore();
    window
      .jQuery("#listMembers")
      .append(
        `<span class="member" memberid="9" tabindex="-1" id="row9">r</span>`,
      );
    (document.getElementById("row9") as HTMLElement).focus();
    expect(document.activeElement?.id).toBe("row9");

    setMemberDeckOnUTubSelected(
      [{ id: 1, username: "owner", memberRole: "creator", joinedAt: null }],
      1,
      true,
      1,
      42,
    );

    expect(document.activeElement?.id).toBe("MemberDeckHeaderAndCaret");
  });

  it("clears the refusal notice when no UTub is selected", () => {
    window.jQuery("#MemberDeckNotice").text("stale").removeClass("hidden");
    setMemberDeckWhenNoUTubSelected();
    expect(window.jQuery("#MemberDeckNotice").text()).toBe("");
  });

  it("keeps the refusal notice through a same-UTub rebuild and an updateMemberDeck diff", () => {
    resetStore();
    setState({ activeUTubID: 42 });
    showMemberDeckNotice({ message: "Not allowed" });

    setMemberDeckOnUTubSelected(
      [{ id: 1, username: "owner", memberRole: "creator", joinedAt: null }],
      1,
      false,
      1,
      42,
    );
    expect(window.jQuery("#MemberDeckNotice").hasClass("hidden")).toBe(false);
    expect(window.jQuery("#MemberDeckNotice").text()).toBe("Not allowed");

    updateMemberDeck(
      [{ id: 1, username: "owner", memberRole: "creator", joinedAt: null }],
      false,
      42,
    );
    expect(window.jQuery("#MemberDeckNotice").hasClass("hidden")).toBe(false);
    expect(window.jQuery("#MemberDeckNotice").text()).toBe("Not allowed");
  });
});

describe("updateMemberDeck — targeted role swap via real applyDeckDiff (DD-17/DD-24)", () => {
  beforeEach(() => {
    document.body.innerHTML = MEMBER_DECK_HTML;
    resetStore();
  });

  afterEach(() => {
    // Restore the module-level mocks so later tests keep their vi.fn() stubs.
    vi.mocked(applyDeckDiff).mockReset();
    vi.mocked(swapMemberRoleInRow).mockReset();
    resetStore();
  });

  function seedRow(
    memberID: number,
    memberRole: string,
    label: string,
  ): string {
    return (
      `<span class="member" memberid="${memberID}"><b>u${memberID}</b>` +
      `<span class="member-right"><span class="member-role-wrap">` +
      `<span aria-hidden="true">${makeUTubRoleIcon({ memberRole, isLocked: false })}</span>` +
      `<span class="visually-hidden">${label}</span></span></span></span>`
    );
  }

  it("swaps only the row whose role changed and skips the unchanged distractor (real diff + real swap)", async () => {
    const { applyDeckDiff: realApplyDeckDiff } = await vi.importActual<
      typeof import("../../../logic/apply-deck-diff.js")
    >("../../../logic/apply-deck-diff.js");
    const { swapMemberRoleInRow: realSwap } =
      await vi.importActual<typeof import("../members.js")>("../members.js");
    vi.mocked(applyDeckDiff).mockImplementation(realApplyDeckDiff);
    vi.mocked(swapMemberRoleInRow).mockImplementation(realSwap);

    // Member A: plain member (will flip). Member B: co-creator (unchanged distractor).
    window.jQuery("#listMembers").append(seedRow(101, "member", "Member"));
    window.jQuery("#listMembers").append(seedRow(202, "cocreator", "Co-owner"));

    setState({
      members: [
        { id: 101, username: "u101", memberRole: "member", joinedAt: null },
        { id: 202, username: "u202", memberRole: "cocreator", joinedAt: null },
      ],
    });

    updateMemberDeck(
      [
        { id: 101, username: "u101", memberRole: "cocreator", joinedAt: null },
        { id: 202, username: "u202", memberRole: "cocreator", joinedAt: null },
      ],
      true,
      42,
    );

    // Member A now shows the co-owner icon + updated screen-reader label.
    expect(
      window.jQuery(`.member[memberid="101"] svg.bi-diamond-half.memberRole`)
        .length,
    ).toBe(1);
    expect(
      window
        .jQuery(`.member[memberid="101"] .member-role-wrap .visually-hidden`)
        .text(),
    ).toBe("Co-owner");
    // Member B untouched (still co-owner) — proves the unchanged-role skip fired.
    expect(
      window.jQuery(`.member[memberid="202"] svg.bi-diamond-half.memberRole`)
        .length,
    ).toBe(1);

    // DD-24: the helper fired exactly once, for member A only.
    expect(vi.mocked(swapMemberRoleInRow)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(swapMemberRoleInRow)).toHaveBeenCalledWith({
      memberID: 101,
      targetRole: "cocreator",
    });
    expect(
      getState().members.find((member) => member.id === 101)?.memberRole,
    ).toBe("member");
  });
});

describe("updateMemberDeck — addElement carries the viewer's role to the badge", () => {
  beforeEach(() => {
    document.body.innerHTML = MEMBER_DECK_HTML;
    resetStore();
    vi.mocked(applyDeckDiff).mockReset();
    vi.mocked(createMemberBadge).mockClear();
  });

  afterEach(() => {
    vi.mocked(applyDeckDiff).mockReset();
    resetStore();
  });

  const NEW_MEMBER = {
    id: 9,
    username: "Dana",
    memberRole: "member",
    joinedAt: null,
  };

  function addedViewerRole({
    isCurrentUserOwner,
    isCoCreator,
  }: {
    isCurrentUserOwner: boolean;
    isCoCreator: boolean;
  }): unknown {
    setState({ isCurrentUserOwner, isCoCreator });
    updateMemberDeck([NEW_MEMBER], isCurrentUserOwner, 42);
    vi.mocked(applyDeckDiff).mock.calls[0][0].addElement(NEW_MEMBER);
    return vi.mocked(createMemberBadge).mock.calls[0][0].viewerRole;
  }

  it("is co_owner for a co-owner viewer", () => {
    expect(
      addedViewerRole({ isCurrentUserOwner: false, isCoCreator: true }),
    ).toBe("co_owner");
  });

  it("is owner for the owner viewer", () => {
    expect(
      addedViewerRole({ isCurrentUserOwner: true, isCoCreator: false }),
    ).toBe("owner");
  });

  it("is member for a plain-member viewer", () => {
    expect(
      addedViewerRole({ isCurrentUserOwner: false, isCoCreator: false }),
    ).toBe("member");
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
