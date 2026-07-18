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
import { closeTagSheet, isTagSheetOpen } from "../../tags/sheet.js";
import { TAG_SHEET_TOGGLE_TRIGGER } from "../../../types/metrics-dim-values.js";
import { leaveUTubSuccess, removeMemberShowModal } from "../delete.js";

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
