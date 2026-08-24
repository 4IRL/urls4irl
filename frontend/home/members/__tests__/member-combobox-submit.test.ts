import { createMemberComboboxBlock } from "../member-combobox.js";
import { submitStagedMembers } from "../member-combobox-submit.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { createMockJqXHR } from "../../../__tests__/helpers/mock-jquery.js";

import type { MemberCandidate, MemberItem } from "../../../types/member.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(),
}));

vi.mock("../co-member-fetch.js", () => ({
  loadCoMemberCandidates: vi.fn(),
  cancelCoMemberCandidatesFetch: vi.fn(),
}));

vi.mock("../deck.js", () => ({
  setMemberDeckForUTub: vi.fn(),
}));

vi.mock("../search.js", () => ({
  closeMemberNameFilter: vi.fn(),
  reapplyMemberFilter: vi.fn(),
}));

vi.mock("../members.js", () => ({
  createMemberBadge: vi.fn((id: number, username: string) =>
    window.jQuery(
      `<span class="member" memberid="${id}"><b>${username}</b></span>`,
    ),
  ),
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
    <button id="memberBtnCreate" class="green-clickable hidden"></button>
    <span id="MemberSearchAnnouncement" aria-live="polite"></span>
    <span id="MobilePanelAnnouncement" aria-live="polite"></span>
    <div id="createMemberWrap" class="hidden"></div>
    <div id="displayMemberWrap" class="hidden">
      <div id="UTubOwner"></div>
      <div id="listMembers"></div>
    </div>
  </div>
`;

const BOB: MemberCandidate = { id: 1, username: "Bob", sharedUtubCount: 2 };

function seed({
  candidates = [BOB] as MemberCandidate[],
  members = [] as MemberItem[],
  activeUTubID = 7 as number | null,
  isOwner = true,
}): void {
  setState({
    coMemberCandidates: candidates,
    members,
    coMemberCandidatesLoaded: true,
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

// Stages a co-member chip (Bob → search_result) and an outsider chip (the exact
// typed casing → exact_username) so both `source` paths are exercised.
function stageTwoChips(wrap: JQuery): void {
  typeIn(wrap, "bo");
  wrap
    .find(".memberAddOption:not(.memberAddOptionOutsider)")
    .first()
    .trigger("click.memberAddCombobox");

  typeIn(wrap, "Ghost");
  wrap.find(".memberAddOptionOutsider").trigger("click.memberAddCombobox");
}

const okXhr = { status: 200 } as unknown as JQuery.jqXHR;

beforeEach(() => {
  resetStore();
  vi.clearAllMocks();
  vi.useFakeTimers();
  vi.mocked(is429Handled).mockReturnValue(false);
});

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("member-combobox-submit — per-chip POSTs", () => {
  it("fires one independent POST per staged chip with the correct source + casing", () => {
    seed({});
    const wrap = mount();
    stageTwoChips(wrap);

    vi.mocked(ajaxCall)
      .mockReturnValueOnce(createMockJqXHR())
      .mockReturnValueOnce(createMockJqXHR());

    void submitStagedMembers({ utubID: 7, wrap });

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(2);

    const [firstMethod, firstUrl, firstBody] =
      vi.mocked(ajaxCall).mock.calls[0];
    expect(firstMethod).toBe("post");
    expect(firstUrl).toBe("/utubs/7/members");
    expect(firstBody).toEqual({ username: "Bob", source: "search_result" });

    const [, , secondBody] = vi.mocked(ajaxCall).mock.calls[1];
    // Outsider chip carries the EXACT typed casing (never lowercased).
    expect(secondBody).toEqual({ username: "Ghost", source: "exact_username" });
  });

  it("guards against a double-submit while a batch is in flight (Enter pressed twice)", () => {
    seed({});
    const wrap = mount();
    stageTwoChips(wrap);

    vi.mocked(ajaxCall)
      .mockReturnValueOnce(createMockJqXHR())
      .mockReturnValueOnce(createMockJqXHR());

    const input = wrap.find(".memberAddComboboxInput");
    input.val("");
    input.trigger($.Event("keydown", { key: "Enter" }));
    // Second Enter before the first batch settles must NOT re-fire the POSTs
    // (the button-disable alone would not stop the Enter path).
    input.trigger($.Event("keydown", { key: "Enter" }));

    expect(vi.mocked(ajaxCall)).toHaveBeenCalledTimes(2);
  });
});

describe("member-combobox-submit — mixed outcomes", () => {
  it("200 + 400: succeeded chip removed, failed chip retained with inline error, input refocused", async () => {
    seed({});
    const wrap = mount();
    stageTwoChips(wrap);

    const firstDeferred = createMockJqXHR();
    const secondDeferred = createMockJqXHR();
    vi.mocked(ajaxCall)
      .mockReturnValueOnce(firstDeferred)
      .mockReturnValueOnce(secondDeferred);

    let refocused = false;
    wrap.find(".memberAddComboboxInput").on("focus", () => {
      refocused = true;
    });

    const settle = submitStagedMembers({ utubID: 7, wrap });

    firstDeferred.resolve(
      { utubID: 7, member: { id: 1, username: "Bob" } },
      "success",
      okXhr,
    );
    secondDeferred.reject({
      status: 400,
      responseJSON: { errors: { username: ["That user does not exist."] } },
    });

    await settle;

    // Succeeded chip (Bob) dropped from the strip + staged state.
    const chips = wrap.find(".memberAddStagedChip");
    const usernames = chips
      .map((_i, el) => $(el).attr("data-staged-username"))
      .get();
    expect(usernames).toEqual(["Ghost"]);

    // Failed chip retained WITH its inline error visible; siblings unaffected.
    const failedChip = chips.filter(
      (_i, el) => $(el).attr("data-staged-username") === "Ghost",
    );
    const error = failedChip.find(".memberAddStagedChipError");
    expect(error.hasClass("hidden")).toBe(false);
    expect(error.text()).toBe("That user does not exist.");

    // DD-10 post-settle refocus.
    expect(refocused).toBe(true);
  });

  it("pushes the added member into the store and appends the deck badge once after settle", async () => {
    seed({});
    const wrap = mount();
    stageTwoChips(wrap);

    const firstDeferred = createMockJqXHR();
    const secondDeferred = createMockJqXHR();
    vi.mocked(ajaxCall)
      .mockReturnValueOnce(firstDeferred)
      .mockReturnValueOnce(secondDeferred);

    const { createMemberBadge } = await import("../members.js");
    const { setMemberDeckForUTub } = await import("../deck.js");
    const { reapplyMemberFilter } = await import("../search.js");

    const settle = submitStagedMembers({ utubID: 7, wrap });

    firstDeferred.resolve(
      { utubID: 7, member: { id: 1, username: "Bob" } },
      "success",
      okXhr,
    );
    secondDeferred.resolve(
      { utubID: 7, member: { id: 2, username: "Ghost" } },
      "success",
      okXhr,
    );

    await settle;

    expect(getState().members.map((member) => member.username)).toEqual([
      "Bob",
      "Ghost",
    ]);
    // Deck sync runs ONCE total, from the resolved results array.
    expect(vi.mocked(createMemberBadge)).toHaveBeenCalledTimes(2);
    expect(vi.mocked(setMemberDeckForUTub)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(reapplyMemberFilter)).toHaveBeenCalledTimes(1);
  });
});

describe("member-combobox-submit — 429 short-circuit", () => {
  it("settles the 429 chip without an inline error and excludes it from the summary", async () => {
    seed({});
    const wrap = mount();
    stageTwoChips(wrap);

    const firstDeferred = createMockJqXHR();
    const secondDeferred = createMockJqXHR();
    vi.mocked(ajaxCall)
      .mockReturnValueOnce(firstDeferred)
      .mockReturnValueOnce(secondDeferred);

    // The second (outsider) chip is the one that 429s.
    vi.mocked(is429Handled).mockImplementation(
      (xhr: JQuery.jqXHR) => (xhr as { status?: number }).status === 429,
    );

    const settle = submitStagedMembers({ utubID: 7, wrap });

    firstDeferred.resolve(
      { utubID: 7, member: { id: 1, username: "Bob" } },
      "success",
      okXhr,
    );
    secondDeferred.reject({ status: 429 });

    // Resolves (does not hang) — the 429 wrapper still settled.
    await settle;

    // The 429 chip shows no inline error (its global 429 UI fired instead) and
    // is excluded from the batched summary.
    const ghostChip = wrap
      .find(".memberAddStagedChip")
      .filter((_i, el) => $(el).attr("data-staged-username") === "Ghost");
    expect(ghostChip.find(".memberAddStagedChipError").hasClass("hidden")).toBe(
      true,
    );
    expect(wrap.find(".memberAddComboboxMsg").text()).toBe("Bob added");
  });
});

describe("member-combobox-submit — batched aria-live", () => {
  it("writes the combobox's own aria-live region exactly once, only after all settle", async () => {
    seed({});
    const wrap = mount();
    stageTwoChips(wrap);

    const firstDeferred = createMockJqXHR();
    const secondDeferred = createMockJqXHR();
    vi.mocked(ajaxCall)
      .mockReturnValueOnce(firstDeferred)
      .mockReturnValueOnce(secondDeferred);

    const message = wrap.find(".memberAddComboboxMsg");
    const settle = submitStagedMembers({ utubID: 7, wrap });

    // First chip settles (200) — the aria-live region must remain EMPTY until
    // Promise.allSettled resolves (batched, not per-chip).
    firstDeferred.resolve(
      { utubID: 7, member: { id: 1, username: "Bob" } },
      "success",
      okXhr,
    );
    await Promise.resolve();
    expect(message.text()).toBe("");

    // Second chip settles (400) — now the single combined summary is written.
    secondDeferred.reject({
      status: 400,
      responseJSON: { message: "Member already in UTub." },
    });
    await settle;

    expect(message.text()).toBe(
      "Bob added, Ghost failed: Member already in UTub.",
    );
  });
});

describe("member-combobox-submit — cross-UTub relevance", () => {
  it("skips deck mutations when the creator switched UTubs mid-flight", async () => {
    seed({});
    const wrap = mount();
    stageTwoChips(wrap);

    const firstDeferred = createMockJqXHR();
    const secondDeferred = createMockJqXHR();
    vi.mocked(ajaxCall)
      .mockReturnValueOnce(firstDeferred)
      .mockReturnValueOnce(secondDeferred);

    const { createMemberBadge } = await import("../members.js");
    const { setMemberDeckForUTub } = await import("../deck.js");

    const settle = submitStagedMembers({ utubID: 7, wrap });

    // Simulate a UTub switch while the batch is in flight.
    setState({ activeUTubID: 99 });

    firstDeferred.resolve(
      { utubID: 7, member: { id: 1, username: "Bob" } },
      "success",
      okXhr,
    );
    secondDeferred.resolve(
      { utubID: 7, member: { id: 2, username: "Ghost" } },
      "success",
      okXhr,
    );

    await settle;

    // No deck-DOM mutations for a UTub the batch was not staged against.
    expect(vi.mocked(createMemberBadge)).not.toHaveBeenCalled();
    expect(vi.mocked(setMemberDeckForUTub)).not.toHaveBeenCalled();
    // Completion surfaced via the persistent non-deck aria-live region instead.
    expect($("#MobilePanelAnnouncement").text()).toBe("Bob added, Ghost added");
  });
});
