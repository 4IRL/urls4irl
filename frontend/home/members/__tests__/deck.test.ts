import {
  resetMemberDeck,
  setMemberDeckForUTub,
  setMemberDeckOnUTubSelected,
  setMemberDeckWhenNoUTubSelected,
  updateMemberDeck,
} from "../deck.js";
import { applyDeckDiff } from "../../../logic/apply-deck-diff.js";
import { emit, AppEvents } from "../../../lib/event-bus.js";
import { swapMemberRoleInRow } from "../members.js";
import { makeUTubRoleIcon } from "../../utubs/selectors.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";

vi.mock("../../../logic/apply-deck-diff.js", () => ({
  applyDeckDiff: vi.fn(),
}));

// Spy on the event-bus emit (the transfer trigger opens the picker via the
// TRANSFER_PICKER_REQUESTED event) while keeping `on`/`AppEvents` real so
// deck.ts's own module-level subscriptions still register.
vi.mock("../../../lib/event-bus.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../../lib/event-bus.js")
  >("../../../lib/event-bus.js");
  return { ...actual, emit: vi.fn() };
});

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
      <h2 id="MemberDeckHeader">Members<span id="MemberDeckCount" class="deck-title-count"></span></h2>
    </div>
    <button id="memberNameFilterBtn" class="hidden" aria-expanded="false"></button>
    <button id="memberNameFilterBtnClose" class="hidden"></button>
    <button id="memberBtnTransferOwner" class="hidden"></button>
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
    resetStore();
  });

  afterEach(() => {
    resetStore();
  });

  it("reveals the member list and shows the inline count when a UTub is selected", () => {
    const wrap = window.jQuery("#displayMemberWrap");
    expect(wrap.hasClass("hidden")).toBe(true);

    setMemberDeckOnUTubSelected(
      [{ id: 1, username: "owner", memberRole: "creator" }],
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

  it("shows the add-member button for a non-owner co-owner on UTub selection (DD-1)", () => {
    // A co-owner (isCurrentUserOwner: false, isCoCreator: true) can add members,
    // so setMemberDeckOnUTubSelected's canManageMembers OR-gate must reveal the
    // add button even though the literal owner flag is false.
    resetStore();
    setState({ isCoCreator: true });

    setMemberDeckOnUTubSelected(
      [{ id: 1, username: "owner", memberRole: "creator" }],
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
      [{ id: 1, username: "owner", memberRole: "creator" }],
      1,
      false,
      1,
      42,
    );

    expect(window.jQuery("#memberBtnCreate").hasClass("hidden")).toBe(true);
  });
});

describe("Standalone transfer-ownership trigger visibility (Step 4)", () => {
  const OWNER = { id: 1, username: "owner", memberRole: "creator" };
  const MEMBER = { id: 2, username: "devin", memberRole: "member" };

  beforeEach(() => {
    document.body.innerHTML = MEMBER_DECK_HTML;
    resetStore();
    vi.mocked(emit).mockClear();
  });

  afterEach(() => {
    resetStore();
  });

  // The trigger's visibility reads live state (isCurrentUserOwner, members,
  // utubOwnerID), which buildSelectedUTub sets before UTUB_SELECTED fires, so
  // seed state to match the members being rendered.
  function selectUTub(
    members: { id: number; username: string; memberRole: string }[],
    {
      isCurrentUserOwner,
      isCurrentUTubLocked = false,
    }: { isCurrentUserOwner: boolean; isCurrentUTubLocked?: boolean },
  ): void {
    setState({
      members,
      isCurrentUserOwner,
      utubOwnerID: OWNER.id,
      isCurrentUTubLocked,
    });
    setMemberDeckOnUTubSelected(
      members,
      OWNER.id,
      isCurrentUserOwner,
      OWNER.id,
      42,
    );
  }

  it("shows the transfer button for the owner with at least one other member", () => {
    selectUTub([OWNER, MEMBER], { isCurrentUserOwner: true });

    const btn = window.jQuery("#memberBtnTransferOwner");
    expect(btn.hasClass("hidden")).toBe(false);
    expect(btn.attr("aria-label")).toBe("Transfer ownership");
  });

  it("shows the transfer button for the owner even when the UTub is locked (no client lock gate; DD-2/DD-11)", () => {
    selectUTub([OWNER, MEMBER], {
      isCurrentUserOwner: true,
      isCurrentUTubLocked: true,
    });

    expect(window.jQuery("#memberBtnTransferOwner").hasClass("hidden")).toBe(
      false,
    );
  });

  it("hides the transfer button for a non-owner (co-owner or plain member)", () => {
    selectUTub([OWNER, MEMBER], { isCurrentUserOwner: false });

    expect(window.jQuery("#memberBtnTransferOwner").hasClass("hidden")).toBe(
      true,
    );
  });

  it("hides the transfer button for a sole-owner UTub (no transfer target)", () => {
    selectUTub([OWNER], { isCurrentUserOwner: true });

    expect(window.jQuery("#memberBtnTransferOwner").hasClass("hidden")).toBe(
      true,
    );
  });

  it("hides the transfer button when no UTub is selected", () => {
    selectUTub([OWNER, MEMBER], { isCurrentUserOwner: true });
    expect(window.jQuery("#memberBtnTransferOwner").hasClass("hidden")).toBe(
      false,
    );

    setMemberDeckWhenNoUTubSelected();

    expect(window.jQuery("#memberBtnTransferOwner").hasClass("hidden")).toBe(
      true,
    );
  });

  it("requests the transfer picker (with its own selector as the opener) when clicked", () => {
    selectUTub([OWNER, MEMBER], { isCurrentUserOwner: true });

    // The deck build above emits its own unrelated events; clear so the
    // assertion isolates the click's TRANSFER_PICKER_REQUESTED emit.
    vi.mocked(emit).mockClear();
    window.jQuery("#memberBtnTransferOwner").trigger("click");

    expect(vi.mocked(emit)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(emit)).toHaveBeenCalledWith(
      AppEvents.TRANSFER_PICKER_REQUESTED,
      { opener: "#memberBtnTransferOwner" },
    );
  });

  it("does not double-bind the click handler across repeated UTub selections", () => {
    selectUTub([OWNER, MEMBER], { isCurrentUserOwner: true });
    selectUTub([OWNER, MEMBER], { isCurrentUserOwner: true });

    // Isolate the click: a single trigger must fire exactly one emit even after
    // two selections (the off("click") clears any prior handler before re-bind).
    vi.mocked(emit).mockClear();
    window.jQuery("#memberBtnTransferOwner").trigger("click");

    expect(vi.mocked(emit)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(emit)).toHaveBeenCalledWith(
      AppEvents.TRANSFER_PICKER_REQUESTED,
      { opener: "#memberBtnTransferOwner" },
    );
  });

  it("re-hides the transfer button on a stale-data update when the last non-owner member leaves", () => {
    selectUTub([OWNER, MEMBER], { isCurrentUserOwner: true });
    expect(window.jQuery("#memberBtnTransferOwner").hasClass("hidden")).toBe(
      false,
    );

    // Background membership change (STALE_DATA_DETECTED): the only other member
    // left, dropping the non-owner count to 0 — the trigger must hide without
    // waiting for the next full UTUB_SELECTED.
    updateMemberDeck([OWNER], true, 42);

    expect(window.jQuery("#memberBtnTransferOwner").hasClass("hidden")).toBe(
      true,
    );
  });

  it("reveals the transfer button on a stale-data update when a non-owner member joins a sole-owner UTub (0→1 show)", () => {
    // Sole-owner UTub: no eligible transfer target, so the trigger starts hidden.
    selectUTub([OWNER], { isCurrentUserOwner: true });
    expect(window.jQuery("#memberBtnTransferOwner").hasClass("hidden")).toBe(
      true,
    );

    // Background membership change (STALE_DATA_DETECTED): a non-owner member joins,
    // lifting the non-owner count 0→1 — the trigger must reveal without waiting
    // for the next full UTUB_SELECTED (the show side of the 0↔1 threshold, the
    // mirror of the re-hide test above).
    updateMemberDeck([OWNER, MEMBER], true, 42);

    const btn = window.jQuery("#memberBtnTransferOwner");
    expect(btn.hasClass("hidden")).toBe(false);
    expect(btn.attr("aria-label")).toBe("Transfer ownership");
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
        { id: 101, username: "u101", memberRole: "member" },
        { id: 202, username: "u202", memberRole: "cocreator" },
      ],
    });

    updateMemberDeck(
      [
        { id: 101, username: "u101", memberRole: "cocreator" },
        { id: 202, username: "u202", memberRole: "cocreator" },
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
