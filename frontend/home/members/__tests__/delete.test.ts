import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import { getNumOfUTubs } from "../../utubs/utils.js";
import {
  hideInputsAndUpdateUTubDeck,
  resetUTubDeckIfNoUTubs,
} from "../../utubs/deck.js";
import { getState, setState } from "../../../store/app-store.js";
import { applyRowCountDelta } from "../../utubs/row-counts.js";
import { closeTagSheet, isTagSheetOpen } from "../../tags/sheet.js";
import { TAG_SHEET_TOGGLE_TRIGGER } from "../../../types/metrics-dim-values.js";
import {
  createLeaveUTubAsMemberIcon,
  leaveUTubSuccess,
  removeMemberShowModal,
} from "../delete.js";
import { bootstrap } from "../../../lib/globals.js";
import { APP_CONFIG } from "../../../lib/config.js";

// The ambient test-setup Bootstrap mock returns null from getInstance(), which
// would make the tooltip-hide guard a silent no-op. Override lib/globals.js with
// a shared tooltip instance so the guard can be asserted on.
const { tooltipInstance, globalsMock } = await vi.hoisted(async () => {
  const { mockGlobalsWithTooltipInstance } =
    await import("../../../__tests__/helpers/mock-globals.js");
  return await mockGlobalsWithTooltipInstance();
});

vi.mock("../../../lib/globals.js", () => globalsMock);

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));
vi.mock("../../utub-locked.js", () => ({
  isUtubLockedHandled: vi.fn(() => false),
}));
vi.mock("../../../lib/metrics-client.js", () => ({ emit: vi.fn() }));
vi.mock("../deck.js", () => ({ setMemberDeckForUTub: vi.fn() }));
vi.mock("../../btns-forms.js", () => ({ hideInputs: vi.fn() }));
vi.mock("../../urls/cards/selection.js", () => ({ deselectAllURLs: vi.fn() }));
vi.mock("../../utubs/utils.js", () => ({ getNumOfUTubs: vi.fn(() => 0) }));
vi.mock("../../utubs/deck.js", () => ({
  hideInputsAndUpdateUTubDeck: vi.fn(),
  resetUTubDeckIfNoUTubs: vi.fn(),
}));
vi.mock("../../init.js", () => ({ setUIWhenNoUTubSelected: vi.fn() }));
vi.mock("../../tags/sheet.js", () => ({
  isTagSheetOpen: vi.fn(() => false),
  closeTagSheet: vi.fn(),
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
vi.mock("../../utubs/row-counts.js", () => ({ applyRowCountDelta: vi.fn() }));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ members: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const LEAVE_UTUB_HTML = `
  <div id="confirmModal">
    <div id="confirmModalTitle"></div>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
  <div id="listUTubs">
    <div class="UTubSelector" utubid="42"></div>
  </div>
`;

function installJqueryOverrides(): void {
  ($.fn as unknown as Record<string, unknown>).modal = function (this: JQuery) {
    return this;
  };
  // Override fadeOut so the post-fade callback fires synchronously.
  ($.fn as unknown as Record<string, unknown>).fadeOut = function (
    this: JQuery,
    _duration: unknown,
    callback?: () => void,
  ) {
    if (typeof callback === "function") callback();
    return this;
  };
}

describe("leaveUTubSuccess — indirect via removeMemberShowModal + ajax success", () => {
  beforeEach(() => {
    document.body.innerHTML = LEAVE_UTUB_HTML;
    vi.clearAllMocks();
    installJqueryOverrides();
    vi.mocked(is429Handled).mockReturnValue(false);
    vi.mocked(getState).mockReturnValue({
      members: [],
    } as unknown as ReturnType<typeof getState>);
  });

  // Drives the full remove-member confirm flow for a non-creator (leave) with a
  // mocked ajax success, so leaveUTubSuccess fires as a side effect — mirroring
  // utubs/__tests__/delete.test.ts's indirect pattern.
  function triggerLeaveSubmit(utubID: number): void {
    const successXhr = createMockXhr({ status: 200 });
    const chainable = createMockJqXHRChainable({
      done: (cb: unknown) => {
        (
          cb as (
            _response: unknown,
            _textStatus: unknown,
            xhr: JQuery.jqXHR,
          ) => void
        )({}, "success", successXhr);
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable);

    // memberID irrelevant for the leave path; isCreator=false routes to leaveUTubSuccess.
    removeMemberShowModal(9, false, utubID);
    $("#modalSubmit").trigger("click");
  }

  it("calls resetUTubDeckIfNoUTubs and skips hideInputsAndUpdateUTubDeck when no UTubs remain", () => {
    vi.mocked(getNumOfUTubs).mockReturnValue(0);

    triggerLeaveSubmit(42);

    expect(vi.mocked(resetUTubDeckIfNoUTubs)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(hideInputsAndUpdateUTubDeck)).not.toHaveBeenCalled();
    expect(setState).toHaveBeenCalledWith({ activeUTubID: null });
  });

  it("calls hideInputsAndUpdateUTubDeck and skips resetUTubDeckIfNoUTubs when UTubs remain", () => {
    vi.mocked(getNumOfUTubs).mockReturnValue(2);

    triggerLeaveSubmit(42);

    expect(vi.mocked(hideInputsAndUpdateUTubDeck)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(resetUTubDeckIfNoUTubs)).not.toHaveBeenCalled();
  });

  it("closes an open tag sheet before the history push (DD-11)", () => {
    vi.mocked(isTagSheetOpen).mockReturnValue(true);

    triggerLeaveSubmit(42);

    expect(closeTagSheet).toHaveBeenCalledTimes(1);
    expect(closeTagSheet).toHaveBeenCalledWith({
      returnFocus: false,
      trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP,
    });
  });
});

describe("leaveUTubSuccess — direct call (DD-25): tag-sheet reconciliation + ordering", () => {
  beforeEach(() => {
    document.body.innerHTML = LEAVE_UTUB_HTML;
    vi.clearAllMocks();
    installJqueryOverrides();
    vi.mocked(getState).mockReturnValue({
      members: [],
    } as unknown as ReturnType<typeof getState>);
  });

  it("does not close the tag sheet when it is already closed (DD-11)", () => {
    vi.mocked(isTagSheetOpen).mockReturnValue(false);

    leaveUTubSuccess(42);

    expect(closeTagSheet).not.toHaveBeenCalled();
  });

  it("closes an open tag sheet with the default reconciliation (DD-11)", () => {
    vi.mocked(isTagSheetOpen).mockReturnValue(true);

    leaveUTubSuccess(42);

    expect(closeTagSheet).toHaveBeenCalledWith({
      returnFocus: false,
      trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP,
    });
  });

  it("consumes the sheet's entry via history.back() BEFORE the setTimeout push/replace pair (DD-29, real timers)", async () => {
    // Prior synchronous tests schedule setTimeout(0) push/replace callbacks that
    // never got flushed; drain them BEFORE installing the spies so they can't
    // pollute this real-timers ordering assertion.
    await new Promise((resolve) => setTimeout(resolve, 0));

    vi.mocked(isTagSheetOpen).mockReturnValue(true);
    // Faithful stand-in for closeTagSheet's default reconciliation, which calls
    // history.back() synchronously to consume the sheet's own entry.
    vi.mocked(closeTagSheet).mockImplementation(() => {
      window.history.back();
    });
    const historyBackSpy = vi
      .spyOn(window.history, "back")
      .mockImplementation(() => {});
    const pushStateSpy = vi
      .spyOn(window.history, "pushState")
      .mockImplementation(() => {});
    const replaceStateSpy = vi
      .spyOn(window.history, "replaceState")
      .mockImplementation(() => {});

    try {
      leaveUTubSuccess(42);
      // Let both macrotasks run: the history.back() traversal and the
      // pre-existing setTimeout(0) push/replace pair.
      await new Promise((resolve) => setTimeout(resolve, 0));

      expect(historyBackSpy).toHaveBeenCalledTimes(1);
      expect(pushStateSpy).toHaveBeenCalledTimes(1);
      expect(replaceStateSpy).toHaveBeenCalledTimes(1);
      expect(historyBackSpy.mock.invocationCallOrder[0]).toBeLessThan(
        pushStateSpy.mock.invocationCallOrder[0],
      );
      expect(historyBackSpy.mock.invocationCallOrder[0]).toBeLessThan(
        replaceStateSpy.mock.invocationCallOrder[0],
      );
    } finally {
      historyBackSpy.mockRestore();
      pushStateSpy.mockRestore();
      replaceStateSpy.mockRestore();
    }
  });
});

describe("removeMemberSuccess — creator-removes-member success branch", () => {
  beforeEach(() => {
    document.body.innerHTML = LEAVE_UTUB_HTML;
    vi.clearAllMocks();
    installJqueryOverrides();
    vi.mocked(is429Handled).mockReturnValue(false);
    vi.mocked(getState).mockReturnValue({
      members: [{ id: 9, username: "Bob", memberRole: "member" }],
      urls: [],
      activeUTubID: 42,
    } as unknown as ReturnType<typeof getState>);
  });

  it("subtracts one from the active UTub's row member count", () => {
    const successXhr = createMockXhr({ status: 200 });
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        done: (cb: unknown) => {
          (
            cb as (
              _response: unknown,
              _textStatus: unknown,
              xhr: JQuery.jqXHR,
            ) => void
          )({}, "success", successXhr);
        },
      }),
    );

    removeMemberShowModal(9, true, 42);
    $("#modalSubmit").trigger("click");

    expect(applyRowCountDelta).toHaveBeenCalledWith({
      utubID: 42,
      urlDelta: 0,
      memberDelta: -1,
    });
  });

  // Drives the full creator-removes-member confirm flow with a mocked ajax
  // success so removeMemberSuccess fires (isCreator=true routes there rather
  // than leaveUTubSuccess). Mirrors the leave-path indirect pattern above and
  // the URL_DECK_CHANGED precedent in
  // frontend/home/urls/cards/__tests__/create.test.ts:416.
  it("emits AppEvents.MEMBER_DECK_CHANGED after a creator successfully removes a member", async () => {
    const { emit, AppEvents } = await import("../../../lib/event-bus.js");
    const successXhr = createMockXhr({ status: 200 });
    const chainable = createMockJqXHRChainable({
      done: (cb: unknown) => {
        (
          cb as (
            _response: unknown,
            _textStatus: unknown,
            xhr: JQuery.jqXHR,
          ) => void
        )({}, "success", successXhr);
      },
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable);

    removeMemberShowModal(9, true, 42);
    $("#modalSubmit").trigger("click");

    expect(emit).toHaveBeenCalledWith(AppEvents.MEMBER_DECK_CHANGED);
  });

  it("re-renders only the removed member's stacked badges as 'Added by a former member'", async () => {
    document.body.innerHTML =
      LEAVE_UTUB_HTML +
      `<div id="listURLs">
        <div class="urlRow" utuburlid="1"><time class="urlDateAddedBadge urlDateAddedBadgeStacked">old-1</time></div>
        <div class="urlRow" utuburlid="2"><time class="urlDateAddedBadge urlDateAddedBadgeStacked">old-2</time></div>
      </div>`;
    // Mirror the post-setState store: the removed member (9) is gone.
    vi.mocked(getState).mockReturnValue({
      members: [{ id: 5, username: "carol", memberRole: "member" }],
      preferences: { dateFormat: "iso" },
      urls: [
        {
          utubUrlID: 1,
          addedByUserID: 9,
          addedAt: "2024-03-09T12:00:00+00:00",
        },
        {
          utubUrlID: 2,
          addedByUserID: 5,
          addedAt: "2024-03-10T12:00:00+00:00",
        },
      ],
    } as unknown as ReturnType<typeof getState>);
    const successXhr = createMockXhr({ status: 200 });
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        done: (cb: unknown) => {
          (
            cb as (
              _response: unknown,
              _textStatus: unknown,
              xhr: JQuery.jqXHR,
            ) => void
          )({}, "success", successXhr);
        },
      }),
    );

    removeMemberShowModal(9, true, 42);
    $("#modalSubmit").trigger("click");

    const removed = $('.urlRow[utuburlid="1"] .urlDateAddedBadgeStacked');
    expect(removed.length).toBe(1);
    expect(removed.text()).toBe(
      `${APP_CONFIG.strings.URL_ADDED_BY} ${APP_CONFIG.strings.URL_ADDED_BY_FORMER_MEMBER} · 2024-03-09`,
    );
    expect(removed.attr("aria-label")).toBe(
      `${APP_CONFIG.strings.URL_ADDED_BY} ${APP_CONFIG.strings.URL_ADDED_BY_FORMER_MEMBER} ${APP_CONFIG.strings.URL_ADDED_ON} 2024-03-09`,
    );
    // Another member's card is untouched.
    expect($('.urlRow[utuburlid="2"] .urlDateAddedBadgeStacked').text()).toBe(
      "old-2",
    );
  });

  it("does not throw and leaves the DOM unchanged when the removed member's URLs have no rendered card or the member has no URLs", () => {
    const deckHTML = `<div id="listURLs">
        <div class="urlRow" utuburlid="2"><time class="urlDateAddedBadge urlDateAddedBadgeStacked">old-2</time></div>
      </div>`;
    document.body.innerHTML = LEAVE_UTUB_HTML + deckHTML;
    // Removed member 9 owns URL 1 (in the store, no card rendered); member 5
    // (still present) owns URL 2; member 6 has no URLs at all.
    vi.mocked(getState).mockReturnValue({
      members: [{ id: 5, username: "carol", memberRole: "member" }],
      preferences: { dateFormat: "iso" },
      urls: [
        {
          utubUrlID: 1,
          addedByUserID: 9,
          addedAt: "2024-03-09T12:00:00+00:00",
        },
        {
          utubUrlID: 2,
          addedByUserID: 5,
          addedAt: "2024-03-10T12:00:00+00:00",
        },
      ],
    } as unknown as ReturnType<typeof getState>);
    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        done: (cb: unknown) => {
          (
            cb as (
              _response: unknown,
              _textStatus: unknown,
              xhr: JQuery.jqXHR,
            ) => void
          )({}, "success", createMockXhr({ status: 200 }));
        },
      }),
    );
    const before = $("#listURLs").html();

    expect(() => {
      removeMemberShowModal(9, true, 42);
      $("#modalSubmit").trigger("click");
    }).not.toThrow();
    expect($("#listURLs").html()).toBe(before);

    // A member with no URLs in the store is likewise a no-op.
    expect(() => {
      removeMemberShowModal(6, true, 42);
      $("#modalSubmit").trigger("click");
    }).not.toThrow();
    expect($("#listURLs").html()).toBe(before);
  });
});

describe("createLeaveUTubAsMemberIcon — hides the #memberSelfBtnDelete tooltip", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      ${LEAVE_UTUB_HTML}
      <button id="memberSelfBtnDelete" data-bs-toggle="tooltip"></button>
    `;
    vi.clearAllMocks();
    installJqueryOverrides();
  });

  it("hides the tooltip when the leave-UTub button is clicked", () => {
    createLeaveUTubAsMemberIcon(false, 9, 42);
    $("#memberSelfBtnDelete").trigger("click.removeMember");

    expect(tooltipInstance.hide).toHaveBeenCalled();
  });

  it("still opens the leave modal and does not throw when no tooltip instance exists", () => {
    // Touch devices never construct a Tooltip, so getInstance() returns null and
    // the `?.` guard must no-op without breaking the leave-modal flow.
    vi.mocked(bootstrap.Tooltip.getInstance).mockReturnValueOnce(null);
    createLeaveUTubAsMemberIcon(false, 9, 42);

    expect(() =>
      $("#memberSelfBtnDelete").trigger("click.removeMember"),
    ).not.toThrow();

    expect(tooltipInstance.hide).not.toHaveBeenCalled();
    expect($("#confirmModalTitle").text()).toBe(
      "Are you sure you want to leave this UTub?",
    );
  });
});
