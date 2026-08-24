import {
  createMemberComboboxBlock,
  handleMemberFilterOpened,
  hideAndResetMemberCombobox,
  reapplyMemberDeckSiblingControlSuppression,
  RENDER_KEY,
  showMemberCombobox,
} from "../member-combobox.js";
import { resetMemberDeck } from "../deck.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { APP_CONFIG } from "../../../lib/config.js";

import type { MemberCandidate, MemberItem } from "../../../types/member.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../co-member-fetch.js", () => ({
  loadCoMemberCandidates: vi.fn(),
  cancelCoMemberCandidatesFetch: vi.fn(),
}));

vi.mock("../search.js", () => ({
  closeMemberNameFilter: vi.fn(),
  resetMemberFilter: vi.fn(),
  hideMemberFilterBar: vi.fn(),
  reapplyMemberFilter: vi.fn(),
  setMemberSelectorSearchEventListener: vi.fn(),
  setMemberNameFilterToggleListeners: vi.fn(),
  showMemberFilterBar: vi.fn(),
  applyAlternatingMemberBackground: vi.fn(),
}));

vi.mock("../members.js", () => ({
  createMemberBadge: vi.fn(() => window.jQuery(`<span class="member"></span>`)),
  createOwnerBadge: vi.fn(() => window.jQuery(`<span class="member"></span>`)),
}));

vi.mock("../create.js", () => ({
  setupShowCreateMemberFormEventListeners: vi.fn(),
}));

vi.mock("../delete.js", () => ({
  createLeaveUTubAsMemberIcon: vi.fn(),
}));

vi.mock("../../../logic/apply-deck-diff.js", () => ({
  applyDeckDiff: vi.fn(),
}));

vi.mock("../../../lib/event-bus.js", () => ({
  on: vi.fn(),
  AppEvents: {
    UTUB_SELECTED: "utub_selected",
    STALE_DATA_DETECTED: "stale_data_detected",
    MEMBER_FILTER_OPENED: "member-filter:opened",
  },
}));

vi.mock("../../../lib/modal-tracking.js", () => ({
  setOpenForm: vi.fn(),
  clearOpenForm: vi.fn(),
}));

vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
}));

const $ = window.jQuery;

const MEMBER_DECK_HTML = `
  <div id="MemberDeck">
    <button id="memberNameFilterBtn" class="hidden"></button>
    <button id="memberNameFilterBtnClose" class="hidden"></button>
    <button id="memberBtnCreate" class="green-clickable hidden"></button>
    <div id="SearchMemberWrap"><input id="MemberNameSearch" type="search" value="" /></div>
    <p id="MemberSearchNoResults" class="hidden"></p>
    <span id="MemberSearchAnnouncement" aria-live="polite"></span>
    <div id="createMemberWrap" class="hidden"></div>
    <div id="displayMemberWrap" class="hidden">
      <div id="UTubOwner"></div>
      <div id="listMembers"></div>
    </div>
  </div>
`;

const BOB: MemberCandidate = { id: 1, username: "Bob", sharedUtubCount: 2 };
const BOBBY: MemberCandidate = { id: 2, username: "Bobby", sharedUtubCount: 1 };
const ALICE: MemberCandidate = { id: 3, username: "Alice", sharedUtubCount: 3 };

function seed({
  candidates = [] as MemberCandidate[],
  members = [] as MemberItem[],
  loaded = true,
  activeUTubID = 7 as number | null,
  isOwner = true,
}): void {
  setState({
    coMemberCandidates: candidates,
    members,
    coMemberCandidatesLoaded: loaded,
    activeUTubID,
    isCurrentUserOwner: isOwner,
  });
}

function mount(utubID = 7): JQuery {
  document.body.innerHTML = MEMBER_DECK_HTML;
  const wrap = createMemberComboboxBlock(utubID);
  $("#createMemberWrap").append(wrap).removeClass("hidden");
  wrap.removeClass("hidden");
  return wrap;
}

function typeIn(wrap: JQuery, value: string): void {
  const input = wrap.find(".memberAddComboboxInput");
  input.val(value).trigger("input");
  vi.runAllTimers();
}

beforeEach(() => {
  resetStore();
  vi.clearAllMocks();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("member-combobox — suggestions", () => {
  it("renders co-member suggestions with a right-pinned count pill", () => {
    seed({ candidates: [BOB, BOBBY, ALICE] });
    const wrap = mount();
    typeIn(wrap, "bob");

    const options = wrap.find(".memberAddOption:not(.memberAddOptionOutsider)");
    const labels = options
      .map((_, el) => $(el).find(".memberAddOptionLabel").text())
      .get();
    expect(labels).toEqual(["Bob", "Bobby"]);

    const counts = options
      .map((_, el) => $(el).find(".memberAddOptionCount").text())
      .get();
    expect(counts).toEqual(["shares 2 UTubs", "shares 1 UTub"]);
  });
});

describe("member-combobox — outsider fallback row", () => {
  it("shows the outsider row when the query matches no co-member exactly", () => {
    seed({ candidates: [BOB], members: [] });
    const wrap = mount();
    typeIn(wrap, "new");

    const outsider = wrap.find(".memberAddOptionOutsider");
    expect(outsider.length).toBe(1);
    expect(outsider.find(".memberAddOptionLabel").text()).toBe(
      'Add "new" as an exact username',
    );
  });

  it("suppresses the outsider row when the query exactly matches a co-member", () => {
    seed({ candidates: [BOB], members: [] });
    const wrap = mount();
    typeIn(wrap, "Bob");

    expect(wrap.find(".memberAddOptionOutsider").length).toBe(0);
  });

  it("suppresses the outsider row (and hints) when the query matches a current member", () => {
    seed({ candidates: [BOB], members: [{ id: 9, username: "Zed" }] });
    const wrap = mount();
    typeIn(wrap, "Zed");

    expect(wrap.find(".memberAddOptionOutsider").length).toBe(0);
    expect(wrap.find(".memberAddListboxHint").text()).toBe(
      '"Zed" is already a member',
    );
  });
});

describe("member-combobox — staging", () => {
  it("stages a co-member's canonical username (not the typed casing)", () => {
    seed({ candidates: [BOB], members: [] });
    const wrap = mount();
    typeIn(wrap, "bo");

    wrap
      .find(".memberAddOption:not(.memberAddOptionOutsider)")
      .filter((_, el) => $(el).find(".memberAddOptionLabel").text() === "Bob")
      .trigger("click.memberAddCombobox");

    const chip = wrap.find(".memberAddStagedChip");
    expect(chip.length).toBe(1);
    expect(chip.attr("data-staged-username")).toBe("Bob");
    expect(chip.attr("data-staged-source")).toBe("search_result");
    expect(chip.hasClass("memberAddStagedChipOutsider")).toBe(false);
  });

  it("stages the outsider row with the exact typed casing + NEW marker", () => {
    seed({ candidates: [], members: [] });
    const wrap = mount();
    typeIn(wrap, "NewGuy");

    wrap.find(".memberAddOptionOutsider").trigger("click.memberAddCombobox");

    const chip = wrap.find(".memberAddStagedChip");
    expect(chip.attr("data-staged-username")).toBe("NewGuy");
    expect(chip.attr("data-staged-source")).toBe("exact_username");
    expect(chip.hasClass("memberAddStagedChipOutsider")).toBe(true);
    expect(chip.find(".memberAddStagedChipNew").text()).toBe("NEW");
  });

  it("removes a staged chip and returns focus to the input", () => {
    seed({ candidates: [BOB], members: [] });
    const wrap = mount();
    typeIn(wrap, "bo");
    wrap
      .find(".memberAddOption:not(.memberAddOptionOutsider)")
      .first()
      .trigger("click.memberAddCombobox");
    expect(wrap.find(".memberAddStagedChip").length).toBe(1);

    let refocused = false;
    wrap.find(".memberAddComboboxInput").on("focus", () => {
      refocused = true;
    });

    wrap.find(".memberAddStagedChipRemove").trigger("click.memberAddCombobox");

    expect(wrap.find(".memberAddStagedChip").length).toBe(0);
    expect(refocused).toBe(true);
  });
});

describe("member-combobox — keyboard", () => {
  it("ArrowDown then Enter stages the active option", () => {
    seed({ candidates: [BOB], members: [] });
    const wrap = mount();
    typeIn(wrap, "bo");
    const input = wrap.find(".memberAddComboboxInput");

    input.trigger($.Event("keydown", { key: "ArrowDown" }));
    input.trigger($.Event("keydown", { key: "Enter" }));

    expect(wrap.find(".memberAddStagedChip").length).toBe(1);
  });

  it("Backspace on an empty input removes the last chip", () => {
    seed({ candidates: [], members: [] });
    const wrap = mount();
    typeIn(wrap, "someone");
    wrap.find(".memberAddOptionOutsider").trigger("click.memberAddCombobox");
    expect(wrap.find(".memberAddStagedChip").length).toBe(1);

    const input = wrap.find(".memberAddComboboxInput");
    input.val("");
    input.trigger($.Event("keydown", { key: "Backspace" }));

    expect(wrap.find(".memberAddStagedChip").length).toBe(0);
  });

  it("first Escape closes only the dropdown; second cancels the whole combobox", () => {
    seed({ candidates: [BOB], members: [] });
    const wrap = mount();
    typeIn(wrap, "bo");
    expect(wrap.find(".memberAddListbox").hasClass("hidden")).toBe(false);

    const input = wrap.find(".memberAddComboboxInput");
    const firstEscape = $.Event("keydown", { key: "Escape" });
    input.trigger(firstEscape);

    expect(wrap.find(".memberAddListbox").hasClass("hidden")).toBe(true);
    expect(firstEscape.isPropagationStopped()).toBe(true);
    expect($("#createMemberWrap").find(".memberAddComboboxWrap").length).toBe(
      1,
    );

    input.trigger($.Event("keydown", { key: "Escape" }));

    expect($("#createMemberWrap").find(".memberAddComboboxWrap").length).toBe(
      0,
    );
  });
});

describe("member-combobox — empty + loading states", () => {
  it("shows a distinct hint row when the requester has zero co-members", () => {
    seed({ candidates: [], members: [] });
    const wrap = mount();
    (wrap.data(RENDER_KEY) as () => void)();

    expect(wrap.find(".memberAddListboxHint").text()).toBe(
      APP_CONFIG.strings.MEMBER_ADD_NO_COMEMBERS_HINT,
    );
    expect(wrap.find(".memberAddOption").length).toBe(0);
  });

  it("renders ONLY the loading hint until the fetch settles, then real content", () => {
    seed({ candidates: [ALICE], members: [], loaded: false });
    const wrap = mount();
    wrap.find(".memberAddComboboxInput").val("al");
    (wrap.data(RENDER_KEY) as () => void)();

    // Not loaded yet: only the loading hint, no suggestions, no outsider row.
    expect(wrap.find(".memberAddListboxHint").text()).toBe(
      APP_CONFIG.strings.MEMBER_ADD_LOADING_HINT,
    );
    expect(wrap.find(".memberAddOption").length).toBe(0);

    // Flip to loaded and re-render: real content (a suggestion) now appears.
    setState({ coMemberCandidatesLoaded: true });
    (wrap.data(RENDER_KEY) as () => void)();

    expect(wrap.find(".memberAddListboxHint").length).toBe(0);
    const labels = wrap
      .find(
        ".memberAddOption:not(.memberAddOptionOutsider) .memberAddOptionLabel",
      )
      .map((_, el) => $(el).text())
      .get();
    expect(labels).toContain("Alice");
  });
});

describe("member-combobox — Escape non-propagation (Step 7)", () => {
  it("first Escape does not bubble to a deck-level keydown handler (stopPropagation)", () => {
    seed({ candidates: [BOB], members: [] });
    const wrap = mount();
    typeIn(wrap, "bo");
    expect(wrap.find(".memberAddListbox").hasClass("hidden")).toBe(false);

    // A deck-level Escape consumer (the deck / #confirmModal analog) must NOT see
    // the first Escape — the combobox owns it and closes only its own dropdown.
    const deckHandler = vi.fn();
    $("#MemberDeck").on("keydown", deckHandler);

    wrap
      .find(".memberAddComboboxInput")
      .trigger($.Event("keydown", { key: "Escape" }));

    expect(deckHandler).not.toHaveBeenCalled();
    expect(wrap.find(".memberAddListbox").hasClass("hidden")).toBe(true);
  });
});

describe("member-combobox — reverse mutual exclusion (Step 7)", () => {
  it("handleMemberFilterOpened tears down an OPEN combobox, but no-ops (cache intact) when none is open", () => {
    document.body.innerHTML = MEMBER_DECK_HTML;
    seed({ candidates: [BOB], members: [] });

    // No combobox open → cheap no-op: nothing torn down, co-member cache intact.
    handleMemberFilterOpened();
    expect($("#createMemberWrap").find(".memberAddComboboxWrap").length).toBe(
      0,
    );
    expect(getState().coMemberCandidates.length).toBe(1);

    // Open the combobox, then simulate the filter opening → combobox is torn down
    // (this is the payload wired to the MEMBER_FILTER_OPENED event bus signal).
    showMemberCombobox(7);
    expect($("#createMemberWrap").find(".memberAddComboboxWrap").length).toBe(
      1,
    );

    handleMemberFilterOpened();

    expect($("#createMemberWrap").find(".memberAddComboboxWrap").length).toBe(
      0,
    );
  });
});

describe("member-combobox — sibling-control suppression (Step 7)", () => {
  it("disables the per-row remove buttons + filter funnel while open, re-enables on close", () => {
    seed({ candidates: [BOB], members: [{ id: 9, username: "Zed" }] });
    document.body.innerHTML = MEMBER_DECK_HTML;
    $("#UTubOwner").append(
      '<span class="member" memberid="8"><b>Owner</b></span>',
    );
    $("#listMembers").append(
      '<span class="member" memberid="9"><b>Zed</b>' +
        '<button class="memberOtherBtnDelete"></button></span>',
    );

    // Combobox open → funnel + per-row remove buttons disabled, deck flagged.
    showMemberCombobox(7);

    expect($("#MemberDeck").hasClass("member-add-open")).toBe(true);
    expect($("#memberNameFilterBtn").prop("disabled")).toBe(true);
    expect($("#memberNameFilterBtn").attr("aria-disabled")).toBe("true");
    expect($(".memberOtherBtnDelete").prop("disabled")).toBe(true);

    // Combobox closed → everything re-enabled, deck flag cleared.
    hideAndResetMemberCombobox();

    expect($("#MemberDeck").hasClass("member-add-open")).toBe(false);
    expect($("#memberNameFilterBtn").prop("disabled")).toBe(false);
    expect($("#memberNameFilterBtn").attr("aria-disabled")).toBeUndefined();
    expect($(".memberOtherBtnDelete").prop("disabled")).toBe(false);
  });

  it("re-suppression re-disables a remove button appended while the combobox is open", () => {
    seed({ candidates: [], members: [] });
    document.body.innerHTML = MEMBER_DECK_HTML;
    showMemberCombobox(7);
    expect($("#MemberDeck").hasClass("member-add-open")).toBe(true);

    // A badge appended by a successful batch add while the combobox stays open.
    $("#listMembers").append(
      '<span class="member" memberid="5"><b>New</b>' +
        '<button class="memberOtherBtnDelete"></button></span>',
    );
    // Not yet suppressed (appended after open) …
    expect($(".memberOtherBtnDelete").prop("disabled")).toBe(false);

    reapplyMemberDeckSiblingControlSuppression();

    // … now re-disabled.
    expect($(".memberOtherBtnDelete").prop("disabled")).toBe(true);
  });
});

describe("member-combobox — UTub-switch reset (DD-8)", () => {
  it("resetMemberDeck tears down the combobox and clears combobox store state", () => {
    seed({ candidates: [BOB], members: [] });
    const wrap = mount();
    typeIn(wrap, "someone");
    wrap.find(".memberAddOptionOutsider").trigger("click.memberAddCombobox");
    expect(wrap.find(".memberAddStagedChip").length).toBe(1);
    expect(getState().coMemberCandidates.length).toBe(1);

    resetMemberDeck();

    // Combobox torn down (wrap removed) and the co-member slice cleared.
    expect($("#createMemberWrap").find(".memberAddComboboxWrap").length).toBe(
      0,
    );
    expect(getState().coMemberCandidates).toEqual([]);
    expect(getState().coMemberCandidatesLoaded).toBe(false);
    expect($("#createMemberWrap").find(".memberAddStagedChip").length).toBe(0);
  });
});
