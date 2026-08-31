import {
  createMockJqXHRChainable,
  createMockXhr,
} from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall, is429Handled } from "../../../lib/ajax.js";
import {
  hideInputsAndUpdateUTubDeck,
  resetUTubDeckIfNoUTubs,
} from "../deck.js";
import { getNumOfUTubs } from "../utils.js";
import { getState, setState } from "../../../store/app-store.js";
import { applyAlternatingUTubSelectorBackground } from "../search.js";
import { closeTagSheet, isTagSheetOpen } from "../../tags/sheet.js";
import { TAG_SHEET_TOGGLE_TRIGGER } from "../../../types/metrics-dim-values.js";
import { emit, AppEvents } from "../../../lib/event-bus.js";
import { emit as recordUIEvent } from "../../../lib/metrics-client.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import { setDeleteEventListeners } from "../delete.js";

vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));
vi.mock("../deck.js", () => ({
  resetUTubDeckIfNoUTubs: vi.fn(),
  hideInputsAndUpdateUTubDeck: vi.fn(),
}));
vi.mock("../utils.js", () => ({
  getNumOfUTubs: vi.fn(() => 0),
  updateUTubDeckCount: vi.fn(),
}));
vi.mock("../search.js", () => ({
  applyAlternatingUTubSelectorBackground: vi.fn(),
  resetUTubSearch: vi.fn(),
}));
vi.mock("../../btns-forms.js", () => ({ hideInputs: vi.fn() }));
vi.mock("../../init.js", () => ({ setUIWhenNoUTubSelected: vi.fn() }));
vi.mock("../../tags/sheet.js", () => ({
  isTagSheetOpen: vi.fn(() => false),
  closeTagSheet: vi.fn(),
}));
vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  setMobileUIWhenUTubNotSelectedOrUTubDeleted: vi.fn(),
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
vi.mock("../../../lib/metrics-client.js", () => ({ emit: vi.fn() }));
vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({
    utubs: [],
    members: [],
    utubOwnerID: null,
    isCurrentUserOwner: false,
  })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const DELETE_UTUB_HTML = `
  <div id="confirmModal">
    <div id="confirmModalTitle"></div>
    <div id="confirmModalBody"></div>
    <button id="modalDismiss"></button>
    <button id="modalSubmit"></button>
    <div id="modalRedirect"></div>
  </div>
  <button id="utubBtnDelete"></button>
  <button id="utubTagBtnCreate"></button>
  <div id="listUTubs">
    <div class="UTubSelector" utubid="42"></div>
  </div>
`;

describe("deleteUTubSuccess - last-delete UTub deck dispatch", () => {
  beforeEach(() => {
    document.body.innerHTML = DELETE_UTUB_HTML;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
    // Override fadeOut so the post-fade callback fires synchronously
    ($.fn as unknown as Record<string, unknown>).fadeOut = function (
      this: JQuery,
      _duration: unknown,
      callback?: () => void,
    ) {
      if (typeof callback === "function") callback();
      return this;
    };
    vi.mocked(is429Handled).mockReturnValue(false);
    vi.mocked(getState).mockReturnValue({
      utubs: [{ id: 42 }],
      members: [],
      utubOwnerID: null,
      isCurrentUserOwner: false,
    } as unknown as ReturnType<typeof getState>);
  });

  function triggerDeleteSubmit(utubID: number): void {
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

    setDeleteEventListeners(utubID);
    $("#utubBtnDelete").trigger("click.deleteUTub");
    $("#modalSubmit").trigger("click");
  }

  it("calls resetUTubDeckIfNoUTubs and skips hideInputsAndUpdateUTubDeck when no UTubs remain", () => {
    vi.mocked(getNumOfUTubs).mockReturnValue(0);

    triggerDeleteSubmit(42);

    expect(vi.mocked(resetUTubDeckIfNoUTubs)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(hideInputsAndUpdateUTubDeck)).not.toHaveBeenCalled();
    expect(setState).toHaveBeenCalled();
    // The delete clears the multi-select fields defense-in-depth.
    expect(setState).toHaveBeenCalledWith(
      expect.objectContaining({
        multiSelectMode: false,
        selectedURLCardIDs: [],
      }),
    );
  });

  it("calls hideInputsAndUpdateUTubDeck and skips resetUTubDeckIfNoUTubs when UTubs remain", () => {
    vi.mocked(getNumOfUTubs).mockReturnValue(2);

    triggerDeleteSubmit(42);

    expect(vi.mocked(hideInputsAndUpdateUTubDeck)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(resetUTubDeckIfNoUTubs)).not.toHaveBeenCalled();
    expect(
      vi.mocked(applyAlternatingUTubSelectorBackground),
    ).toHaveBeenCalled();
    // The delete clears the multi-select fields defense-in-depth in both branches.
    expect(setState).toHaveBeenCalledWith(
      expect.objectContaining({
        multiSelectMode: false,
        selectedURLCardIDs: [],
      }),
    );
  });

  it("closes an open tag sheet (default reconciliation) before the history push (DD-11)", () => {
    vi.mocked(isTagSheetOpen).mockReturnValue(true);

    triggerDeleteSubmit(42);

    expect(closeTagSheet).toHaveBeenCalledTimes(1);
    expect(closeTagSheet).toHaveBeenCalledWith({
      returnFocus: false,
      trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP,
    });
  });

  it("does not close the tag sheet when it is already closed (DD-11)", () => {
    vi.mocked(isTagSheetOpen).mockReturnValue(false);

    triggerDeleteSubmit(42);

    expect(closeTagSheet).not.toHaveBeenCalled();
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
      triggerDeleteSubmit(42);
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

describe("deleteUTubShowModal - #modalRedirect 'Transfer instead' entry point", () => {
  function setOwnerState({
    isCurrentUserOwner,
    members,
    utubOwnerID,
  }: {
    isCurrentUserOwner: boolean;
    members: Array<{ id: number }>;
    utubOwnerID: number;
  }): void {
    vi.mocked(getState).mockReturnValue({
      utubs: [{ id: 42 }],
      isCurrentUserOwner,
      members,
      utubOwnerID,
    } as unknown as ReturnType<typeof getState>);
  }

  beforeEach(() => {
    document.body.innerHTML = DELETE_UTUB_HTML;
    vi.clearAllMocks();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
    ) {
      return this;
    };
    vi.mocked(is429Handled).mockReturnValue(false);
    // Owner of a UTub with one other member (id 7); owner is id 1.
    setOwnerState({
      isCurrentUserOwner: true,
      members: [{ id: 1 }, { id: 7 }],
      utubOwnerID: 1,
    });
  });

  function showDeleteModal(utubID: number): void {
    setDeleteEventListeners(utubID);
    $("#utubBtnDelete").trigger("click.deleteUTub");
  }

  it("shows #modalRedirect labeled 'Transfer instead' when owner has >=1 other member", () => {
    showDeleteModal(42);

    const redirect = $("#modalRedirect");
    expect(redirect.css("display")).not.toBe("none");
    expect(redirect.text()).toBe("Transfer instead");
    expect(redirect.hasClass("btn-primary")).toBe(true);
  });

  it("keeps #modalRedirect hidden for a sole-owner UTub (no other members)", () => {
    setOwnerState({
      isCurrentUserOwner: true,
      members: [{ id: 1 }],
      utubOwnerID: 1,
    });

    showDeleteModal(42);

    const redirect = $("#modalRedirect");
    expect(redirect.css("display")).toBe("none");
    expect(redirect.hasClass("btn-primary")).toBe(false);
  });

  it("keeps #modalRedirect hidden when the current user is not the owner", () => {
    setOwnerState({
      isCurrentUserOwner: false,
      members: [{ id: 1 }, { id: 7 }],
      utubOwnerID: 1,
    });

    showDeleteModal(42);

    expect($("#modalRedirect").css("display")).toBe("none");
  });

  it("clicking 'Transfer instead' hides the modal, emits TRANSFER_PICKER_REQUESTED, and does not delete", () => {
    showDeleteModal(42);
    $("#modalRedirect").trigger("click");

    expect(vi.mocked(emit)).toHaveBeenCalledWith(
      AppEvents.TRANSFER_PICKER_REQUESTED,
      { opener: "#utubBtnDelete" },
    );
    // Never issues the delete PATCH/DELETE — this is a redirect, not a delete.
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
  });

  it("does NOT emit UI_UTUB_DELETE_CANCEL after a 'Transfer instead' redirect (false-cancel guard)", () => {
    showDeleteModal(42);
    $("#modalRedirect").trigger("click");
    // Bootstrap fires this once the modal finishes hiding; the jsdom stub does not.
    $("#confirmModal").trigger("hidden.bs.modal");

    expect(vi.mocked(recordUIEvent)).not.toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_DELETE_CANCEL,
    });
  });

  it("still emits UI_UTUB_DELETE_CANCEL on a plain cancel (no transfer redirect)", () => {
    showDeleteModal(42);
    $("#modalDismiss").trigger("click");
    $("#confirmModal").trigger("hidden.bs.modal");

    expect(vi.mocked(recordUIEvent)).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_UTUB_DELETE_CANCEL,
    });
  });
});
