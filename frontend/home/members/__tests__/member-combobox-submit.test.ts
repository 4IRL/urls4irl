import { createMemberComboboxBlock } from "../member-combobox.js";
import { submitStagedMembers } from "../member-combobox-submit.js";
import { APP_CONFIG } from "../../../lib/config.js";
import { getState, resetStore, setState } from "../../../store/app-store.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { createMockJqXHR } from "../../../__tests__/helpers/mock-jquery.js";
import { applyRowCountDelta } from "../../utubs/row-counts.js";
import { learnMemberAddRefused } from "../add-refusal.js";
import { EMPTY_UTUB_SETTINGS } from "../../../types/settings.js";

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

vi.mock("../add-refusal.js", async () => {
  const actual =
    await vi.importActual<typeof import("../add-refusal.js")>(
      "../add-refusal.js",
    );
  return { ...actual, learnMemberAddRefused: vi.fn() };
});

vi.mock("../deck.js", () => ({
  setMemberDeckForUTub: vi.fn(),
  reorderMemberDeck: vi.fn(() => []),
}));

vi.mock("../../utubs/row-counts.js", () => ({
  applyRowCountDelta: vi.fn(),
}));

vi.mock("../search.js", () => ({
  closeMemberNameFilter: vi.fn(),
  reapplyMemberFilter: vi.fn(),
}));

vi.mock("../members.js", () => ({
  createMemberBadge: vi.fn(
    ({ memberID, username }: { memberID: number; username: string }) =>
      window.jQuery(
        `<span class="member" memberid="${memberID}"><b>${username}</b></span>`,
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

vi.mock("../../../lib/event-bus.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../../lib/event-bus.js")
  >("../../../lib/event-bus.js");
  return {
    ...actual,
    emit: vi.fn(),
  };
});

const $ = window.jQuery;

const MEMBER_DECK_HTML = `
  <div id="MemberDeck">
    <button id="memberBtnCreate" class="green-clickable hidden"></button>
    <span id="MemberSearchAnnouncement" aria-live="polite"></span>
    <span id="MobilePanelAnnouncement" aria-live="polite"></span>
    <span id="MemberRowActionAnnouncement" aria-live="polite"></span>
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
  it("200 + 400: succeeded chip removed, failed chip retained with red warning icon + reason tooltip, input refocused", async () => {
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
      {
        utubID: 7,
        member: {
          id: 1,
          username: "Bob",
          memberRole: "member",
          joinedAt: "2026-01-02T03:04:05.123Z",
        },
      },
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

    // Failed chip retained with a red warning-triangle icon + the reason in its
    // title tooltip (never rendered inline beside the username); siblings
    // unaffected. The failure marker is a warning icon, NOT an ✗ — it must not
    // collide with the `×` remove button.
    const failedChip = chips.filter(
      (_i, el) => $(el).attr("data-staged-username") === "Ghost",
    );
    expect(failedChip.hasClass("memberAddStagedChipFailed")).toBe(true);
    // The failure marker is an inline warning-triangle SVG (NOT an ✗ that would
    // collide with the `×` remove button, and NOT an icon-font `<i>` — this
    // project ships no bootstrap-icons font).
    expect(
      failedChip.find(
        ".memberAddStagedChipStatus svg.bi-exclamation-triangle-fill",
      ).length,
    ).toBe(1);
    expect(failedChip.attr("title")).toBe("That user does not exist.");

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
    const { setMemberDeckForUTub, reorderMemberDeck } =
      await import("../deck.js");
    const { reapplyMemberFilter } = await import("../search.js");
    const { emit, AppEvents } = await import("../../../lib/event-bus.js");

    const settle = submitStagedMembers({ utubID: 7, wrap });

    firstDeferred.resolve(
      {
        utubID: 7,
        member: {
          id: 1,
          username: "Bob",
          memberRole: "member",
          joinedAt: "2026-01-02T03:04:05.123Z",
        },
      },
      "success",
      okXhr,
    );
    secondDeferred.resolve(
      {
        utubID: 7,
        member: {
          id: 2,
          username: "Ghost",
          memberRole: "cocreator",
          joinedAt: "2026-01-02T03:04:06.123Z",
        },
      },
      "success",
      okXhr,
    );

    await settle;

    expect(getState().members.map((member) => member.username)).toEqual([
      "Bob",
      "Ghost",
    ]);
    // The store-mutating add site notifies the onboarding nudge system (and any
    // future member-deck consumer) that the deck's member set changed —
    // mirroring the URL_DECK_CHANGED precedent.
    expect(emit).toHaveBeenCalledWith(AppEvents.MEMBER_DECK_CHANGED);
    expect(applyRowCountDelta).toHaveBeenCalledTimes(1);
    expect(applyRowCountDelta).toHaveBeenCalledWith({
      utubID: 7,
      urlDelta: 0,
      memberDelta: 2,
    });
    // Freshly-added members carry the server's role and join date verbatim.
    expect(getState().members.map((member) => member.memberRole)).toEqual([
      "member",
      "cocreator",
    ]);
    expect(getState().members.map((member) => member.joinedAt)).toEqual([
      "2026-01-02T03:04:05.123Z",
      "2026-01-02T03:04:06.123Z",
    ]);
    // Deck sync runs ONCE total, from the resolved results array.
    expect(vi.mocked(createMemberBadge)).toHaveBeenCalledTimes(2);
    expect(vi.mocked(setMemberDeckForUTub)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(reapplyMemberFilter)).toHaveBeenCalledTimes(1);
    // The batch is placed in the viewer's sort ONCE, after the filter pass, from
    // the store's members (which already include the added ones).
    expect(vi.mocked(reorderMemberDeck)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(reorderMemberDeck)).toHaveBeenCalledWith({
      members: getState().members,
      memberSort: getState().preferences.memberSort,
    });
    expect(
      vi.mocked(reapplyMemberFilter).mock.invocationCallOrder[0],
    ).toBeLessThan(vi.mocked(reorderMemberDeck).mock.invocationCallOrder[0]);
  });

  it("200 + non-400 (unrecognized status / 403 HTML): the fatal redirect fires and the batch still settles with that chip excluded", async () => {
    seed({});
    const wrap = mount();
    stageTwoChips(wrap);

    const firstDeferred = createMockJqXHR();
    const secondDeferred = createMockJqXHR();
    vi.mocked(ajaxCall)
      .mockReturnValueOnce(firstDeferred)
      .mockReturnValueOnce(secondDeferred);

    const locationAssignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});

    const settle = submitStagedMembers({ utubID: 7, wrap });

    // Bob (co-member) succeeds; Ghost (outsider) rejects with an unrecognized
    // status carrying no field-level responseJSON, so markChipFailed returns null
    // and the fatal-redirect path runs (a non-403-HTML status falls through to
    // the hard error-page navigation).
    firstDeferred.resolve(
      {
        utubID: 7,
        member: {
          id: 1,
          username: "Bob",
          memberRole: "member",
          joinedAt: "2026-01-02T03:04:05.123Z",
        },
      },
      "success",
      okXhr,
    );
    secondDeferred.reject({ status: 500 });

    // The batch still settles — Promise.allSettled never hangs on the fatal chip.
    await settle;

    // redirectOnFatalFailure fired exactly once, to the error page.
    expect(locationAssignSpy).toHaveBeenCalledTimes(1);
    expect(locationAssignSpy).toHaveBeenCalledWith(APP_CONFIG.routes.errorPage);

    // The succeeded chip is still applied after settle; the fatal chip
    // contributes no member to the store (excluded from the added set).
    expect(getState().members.map((member) => member.username)).toEqual([
      "Bob",
    ]);
  });
});

describe("member-combobox-submit — add not allowed (403 errorCode 7)", () => {
  const notAllowed = { status: 403, responseJSON: { errorCode: 7 } };

  it("marks the chip failed, never redirects, learns once and writes one combined announcement", async () => {
    seed({});
    const wrap = mount();
    stageTwoChips(wrap);

    const firstDeferred = createMockJqXHR();
    const secondDeferred = createMockJqXHR();
    vi.mocked(ajaxCall)
      .mockReturnValueOnce(firstDeferred)
      .mockReturnValueOnce(secondDeferred);
    const locationAssignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
    let refocused = false;
    wrap.find(".memberAddComboboxInput").on("focus", () => {
      refocused = true;
    });
    // The real learn flips the ability and the subscription empties the wrap.
    vi.mocked(learnMemberAddRefused).mockImplementationOnce(() => {
      $("#createMemberWrap").empty();
    });

    const settle = submitStagedMembers({ utubID: 7, wrap });
    firstDeferred.reject(notAllowed);
    secondDeferred.reject(notAllowed);
    await settle;

    expect(locationAssignSpy).not.toHaveBeenCalled();
    const chips = wrap.find(".memberAddStagedChipFailed");
    expect(chips.length).toBe(2);
    expect(chips.first().attr("title")).toBe(
      APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED,
    );
    expect(vi.mocked(learnMemberAddRefused)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(learnMemberAddRefused)).toHaveBeenCalledWith({
      utubID: 7,
      announce: false,
    });
    const live = $("#MemberRowActionAnnouncement");
    expect(live.attr("aria-live")).toBe("assertive");
    expect(live.text()).toBe(
      `${APP_CONFIG.strings.MEMBER_ADD_SUMMARY_FAILED.replace("{{ count }}", () => "2")} ${APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED}`,
    );
    expect(refocused).toBe(false);
  });

  it("mixed batch (one added, one refused): exact combined text, summary kept out of the combobox", async () => {
    seed({});
    const wrap = mount();
    stageTwoChips(wrap);

    const firstDeferred = createMockJqXHR();
    const secondDeferred = createMockJqXHR();
    vi.mocked(ajaxCall)
      .mockReturnValueOnce(firstDeferred)
      .mockReturnValueOnce(secondDeferred);
    const live = $("#MemberRowActionAnnouncement");

    const settle = submitStagedMembers({ utubID: 7, wrap });
    firstDeferred.resolve(
      {
        utubID: 7,
        member: {
          id: 1,
          username: "Bob",
          memberRole: "member",
          joinedAt: "2026-01-02T03:04:05.123Z",
        },
      },
      "success",
      okXhr,
    );
    secondDeferred.reject(notAllowed);
    await settle;

    const expected = `${APP_CONFIG.strings.MEMBER_ADD_SUMMARY_ADDED_ONE}, ${APP_CONFIG.strings.MEMBER_ADD_SUMMARY_FAILED_ONE} ${APP_CONFIG.strings.MEMBER_ADD_NOT_ALLOWED}`;
    expect(live.text()).toBe(expected);
    expect(live.attr("aria-live")).toBe("assertive");
    expect(wrap.find(".memberAddComboboxMsg").text()).toBe("");
  });

  it("keeps focus in the combobox when the learn does not close it", async () => {
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
    firstDeferred.reject(notAllowed);
    secondDeferred.reject(notAllowed);
    await settle;

    // learnMemberAddRefused is mocked here, so nothing closed the combobox.
    expect(refocused).toBe(true);
  });

  it("learns nothing when the viewer already switched to another UTub", async () => {
    seed({});
    const wrap = mount();
    stageTwoChips(wrap);

    const firstDeferred = createMockJqXHR();
    const secondDeferred = createMockJqXHR();
    vi.mocked(ajaxCall)
      .mockReturnValueOnce(firstDeferred)
      .mockReturnValueOnce(secondDeferred);

    const settle = submitStagedMembers({ utubID: 7, wrap });
    setState({ activeUTubID: 8 });
    firstDeferred.reject(notAllowed);
    secondDeferred.reject(notAllowed);
    await settle;

    expect(vi.mocked(learnMemberAddRefused)).not.toHaveBeenCalled();
  });
});

describe("member-combobox-submit — 429 short-circuit", () => {
  it("settles the 429 chip without a status marker and excludes it from the summary", async () => {
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
      {
        utubID: 7,
        member: {
          id: 1,
          username: "Bob",
          memberRole: "member",
          joinedAt: "2026-01-02T03:04:05.123Z",
        },
      },
      "success",
      okXhr,
    );
    secondDeferred.reject({ status: 429 });

    // Resolves (does not hang) — the 429 wrapper still settled.
    await settle;

    // The 429 chip stays visually pending — no status icon, no failure tooltip
    // (its global 429 UI fired instead) — and is excluded from the batched
    // summary.
    const ghostChip = wrap
      .find(".memberAddStagedChip")
      .filter((_i, el) => $(el).attr("data-staged-username") === "Ghost");
    expect(ghostChip.find(".memberAddStagedChipStatus").children().length).toBe(
      0,
    );
    expect(ghostChip.attr("title")).toBeUndefined();
    expect(ghostChip.hasClass("memberAddStagedChipFailed")).toBe(false);
    expect(wrap.find(".memberAddComboboxMsg").text()).toBe("1 member added");
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
      {
        utubID: 7,
        member: {
          id: 1,
          username: "Bob",
          memberRole: "member",
          joinedAt: "2026-01-02T03:04:05.123Z",
        },
      },
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

    expect(message.text()).toBe("1 member added, 1 member couldn't be added");
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
      {
        utubID: 7,
        member: {
          id: 1,
          username: "Bob",
          memberRole: "member",
          joinedAt: "2026-01-02T03:04:05.123Z",
        },
      },
      "success",
      okXhr,
    );
    secondDeferred.resolve(
      {
        utubID: 7,
        member: {
          id: 2,
          username: "Ghost",
          memberRole: "member",
          joinedAt: "2026-01-02T03:04:06.123Z",
        },
      },
      "success",
      okXhr,
    );

    await settle;

    // No deck-DOM mutations for a UTub the batch was not staged against.
    expect(vi.mocked(createMemberBadge)).not.toHaveBeenCalled();
    expect(vi.mocked(setMemberDeckForUTub)).not.toHaveBeenCalled();
    // Completion surfaced via the persistent non-deck aria-live region instead.
    expect($("#MobilePanelAnnouncement").text()).toBe("2 members added");
  });
});

describe("member-combobox-submit — dedupe on switch-away-and-back", () => {
  it("does not append a member (store entry + deck badge) twice when a mid-batch re-fetch already added them by id", async () => {
    seed({});
    const wrap = mount();
    stageTwoChips(wrap);

    const firstDeferred = createMockJqXHR();
    const secondDeferred = createMockJqXHR();
    vi.mocked(ajaxCall)
      .mockReturnValueOnce(firstDeferred)
      .mockReturnValueOnce(secondDeferred);

    const { createMemberBadge } = await import("../members.js");

    const settle = submitStagedMembers({ utubID: 7, wrap });

    // Mid-flight the creator switched away and back to the SAME UTub (activeUTubID
    // is still the batch's UTub 7). That select flow re-fetched `members` fresh —
    // already including Bob (id 1), whose independent POST had completed. This
    // stale batch must NOT append Bob a second time.
    setState({
      members: [
        { id: 1, username: "Bob", memberRole: "member", joinedAt: null },
      ],
    });

    firstDeferred.resolve(
      {
        utubID: 7,
        member: {
          id: 1,
          username: "Bob",
          memberRole: "member",
          joinedAt: "2026-01-02T03:04:05.123Z",
        },
      },
      "success",
      okXhr,
    );
    secondDeferred.resolve(
      {
        utubID: 7,
        member: {
          id: 2,
          username: "Ghost",
          memberRole: "member",
          joinedAt: "2026-01-02T03:04:06.123Z",
        },
      },
      "success",
      okXhr,
    );

    await settle;

    // Bob (already present) is deduped by id; only the genuinely-new Ghost is
    // pushed into the store and badged into the deck.
    expect(getState().members.map((member) => member.id)).toEqual([1, 2]);
    expect(vi.mocked(createMemberBadge)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(createMemberBadge)).toHaveBeenCalledWith({
      memberID: 2,
      username: "Ghost",
      memberRole: "member",
      viewerRole: "owner",
      utubID: 7,
    });
  });
});

describe("member-combobox-submit — hidden member list", () => {
  function seedHiddenViewer(): void {
    seed({ isOwner: false });
    setState({
      isCoCreator: false,
      settings: {
        ...EMPTY_UTUB_SETTINGS,
        members: { ...EMPTY_UTUB_SETTINGS.members, hide_member_list: true },
      },
    });
  }

  const addedMember = {
    utubID: 7,
    member: {
      id: 2,
      username: "Ghost",
      memberRole: "member",
      joinedAt: "2026-01-02T03:04:06.123Z",
    },
  };

  it("on a 200 writes the summary, removes the chip, and changes no store, count or deck", async () => {
    seedHiddenViewer();
    const wrap = mount();
    typeIn(wrap, "Ghost");
    wrap.find(".memberAddOptionOutsider").trigger("click.memberAddCombobox");
    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValueOnce(deferred);
    const { createMemberBadge } = await import("../members.js");
    const { setMemberDeckForUTub } = await import("../deck.js");

    const settle = submitStagedMembers({ utubID: 7, wrap });
    deferred.resolve(addedMember, "success", okXhr);
    await settle;

    expect(wrap.find(".memberAddComboboxMsg").text()).toBe(
      APP_CONFIG.strings.MEMBER_ADD_SUMMARY_ADDED_ONE,
    );
    expect(wrap.find(".memberAddStagedChip").length).toBe(0);
    expect(getState().members).toEqual([]);
    expect(applyRowCountDelta).not.toHaveBeenCalled();
    expect(vi.mocked(createMemberBadge)).not.toHaveBeenCalled();
    expect(vi.mocked(setMemberDeckForUTub)).not.toHaveBeenCalled();
  });

  it("a chip rejected with the unified reason announces summary + reason in one write", async () => {
    seedHiddenViewer();
    const wrap = mount();
    typeIn(wrap, "Ghost");
    wrap.find(".memberAddOptionOutsider").trigger("click.memberAddCombobox");
    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValueOnce(deferred);

    const settle = submitStagedMembers({ utubID: 7, wrap });
    deferred.reject({
      status: 400,
      responseJSON: {
        errors: { username: [APP_CONFIG.strings.MEMBER_CANNOT_BE_ADDED] },
      },
    });
    await settle;

    expect(wrap.find(".memberAddComboboxMsg").text()).toBe(
      `${APP_CONFIG.strings.MEMBER_ADD_SUMMARY_FAILED_ONE} ${APP_CONFIG.strings.MEMBER_CANNOT_BE_ADDED}`,
    );
    expect(wrap.find(".memberAddStagedChip").attr("title")).toBe(
      APP_CONFIG.strings.MEMBER_CANNOT_BE_ADDED,
    );
  });

  it("mixed batch (one added, one unified rejection) writes summary + unified once", async () => {
    seedHiddenViewer();
    const wrap = mount();
    // Hidden viewers get no suggestions, so both chips are exact-username outsiders.
    typeIn(wrap, "Ghost");
    wrap.find(".memberAddOptionOutsider").trigger("click.memberAddCombobox");
    typeIn(wrap, "Phantom");
    wrap.find(".memberAddOptionOutsider").trigger("click.memberAddCombobox");
    const first = createMockJqXHR();
    const second = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValueOnce(first).mockReturnValueOnce(second);

    const settle = submitStagedMembers({ utubID: 7, wrap });
    first.resolve({ utubID: 7, member: addedMember.member }, "success", okXhr);
    second.reject({
      status: 400,
      responseJSON: {
        errors: { username: [APP_CONFIG.strings.MEMBER_CANNOT_BE_ADDED] },
      },
    });
    await settle;

    expect(wrap.find(".memberAddComboboxMsg").text()).toBe(
      `${APP_CONFIG.strings.MEMBER_ADD_SUMMARY_ADDED_ONE}, ${APP_CONFIG.strings.MEMBER_ADD_SUMMARY_FAILED_ONE} ${APP_CONFIG.strings.MEMBER_CANNOT_BE_ADDED}`,
    );
  });

  it("a chip rejected for another reason (daily cap) does not append the unified text", async () => {
    seedHiddenViewer();
    const wrap = mount();
    typeIn(wrap, "Ghost");
    wrap.find(".memberAddOptionOutsider").trigger("click.memberAddCombobox");
    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValueOnce(deferred);

    const settle = submitStagedMembers({ utubID: 7, wrap });
    deferred.reject({
      status: 400,
      responseJSON: { message: "You've added too many members today." },
    });
    await settle;

    expect(wrap.find(".memberAddComboboxMsg").text()).toBe(
      APP_CONFIG.strings.MEMBER_ADD_SUMMARY_FAILED_ONE,
    );
  });

  it("a manager rejected with the same text never gets the unified announcement", async () => {
    seed({});
    const wrap = mount();
    typeIn(wrap, "Ghost");
    wrap.find(".memberAddOptionOutsider").trigger("click.memberAddCombobox");
    const deferred = createMockJqXHR();
    vi.mocked(ajaxCall).mockReturnValueOnce(deferred);

    const settle = submitStagedMembers({ utubID: 7, wrap });
    deferred.reject({
      status: 400,
      responseJSON: {
        errors: { username: [APP_CONFIG.strings.MEMBER_CANNOT_BE_ADDED] },
      },
    });
    await settle;

    expect(wrap.find(".memberAddComboboxMsg").text()).toBe(
      APP_CONFIG.strings.MEMBER_ADD_SUMMARY_FAILED_ONE,
    );
  });
});

describe("member-combobox-submit — viewer role for the added badge", () => {
  it("passes viewerRole co_owner when the adding viewer is a co-owner", async () => {
    seed({ isOwner: false });
    setState({ isCoCreator: true });
    const wrap = mount();
    stageTwoChips(wrap);

    const firstDeferred = createMockJqXHR();
    const secondDeferred = createMockJqXHR();
    vi.mocked(ajaxCall)
      .mockReturnValueOnce(firstDeferred)
      .mockReturnValueOnce(secondDeferred);

    const { createMemberBadge } = await import("../members.js");

    const settle = submitStagedMembers({ utubID: 7, wrap });

    firstDeferred.resolve(
      {
        utubID: 7,
        member: {
          id: 1,
          username: "Bob",
          memberRole: "member",
          joinedAt: "2026-01-02T03:04:05.123Z",
        },
      },
      "success",
      okXhr,
    );
    secondDeferred.resolve(
      {
        utubID: 7,
        member: {
          id: 2,
          username: "Ghost",
          memberRole: "member",
          joinedAt: "2026-01-02T03:04:06.123Z",
        },
      },
      "success",
      okXhr,
    );

    await settle;

    expect(vi.mocked(createMemberBadge)).toHaveBeenCalledTimes(2);
    for (const call of vi.mocked(createMemberBadge).mock.calls) {
      expect(call[0].viewerRole).toBe("co_owner");
    }
  });
});
