import type { Mock } from "vitest";

import { hideInputs } from "../../btns-forms.js";
import {
  hideInputsAndUpdateUTubDeck,
  resetUTubDeckIfNoUTubs,
} from "../deck.js";
import { getNumOfUTubs, updateUTubDeckCount } from "../utils.js";
import { getState, setState } from "../../../store/app-store.js";
import { applyAlternatingUTubSelectorBackground } from "../search.js";
import { closeTagSheet, isTagSheetOpen } from "../../tags/sheet.js";
import { TAG_SHEET_TOGGLE_TRIGGER } from "../../../types/metrics-dim-values.js";
import { emit, AppEvents } from "../../../lib/event-bus.js";
import { setUIWhenNoUTubSelected } from "../../init.js";
import {
  isMobile,
  setCurrentMobilePanel,
  setMobileUIWhenUTubNotSelectedOrUTubDeleted,
} from "../../mobile.js";
import { clearOpenForm } from "../../../lib/modal-tracking.js";
import { showURLDeckBannerError } from "../../urls/deck.js";
import { refreshTrashCount } from "../../trash/count.js";
import { removeUTubLocally } from "../remove-local.js";

vi.mock("../../trash/count.js", () => ({ refreshTrashCount: vi.fn() }));
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
}));
vi.mock("../../btns-forms.js", () => ({ hideInputs: vi.fn() }));
vi.mock("../../init.js", () => ({ setUIWhenNoUTubSelected: vi.fn() }));
vi.mock("../../../lib/modal-tracking.js", () => ({ clearOpenForm: vi.fn() }));
vi.mock("../../urls/deck.js", () => ({ showURLDeckBannerError: vi.fn() }));
vi.mock("../../tags/sheet.js", () => ({
  isTagSheetOpen: vi.fn(() => false),
  closeTagSheet: vi.fn(),
}));
vi.mock("../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
  setMobileUIWhenUTubNotSelectedOrUTubDeleted: vi.fn(),
  setCurrentMobilePanel: vi.fn(),
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
vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ utubs: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const REMOVE_LOCAL_HTML = `
  <div id="confirmModal"></div>
  <span id="URLDeckLockIcon"></span>
  <div id="listUTubs">
    <div class="UTubSelector" utubid="42"></div>
    <div class="UTubSelector" utubid="43"></div>
  </div>
`;

function drainTimers(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 0));
}

describe("removeUTubLocally", () => {
  let pushStateSpy: ReturnType<typeof vi.spyOn>;
  let replaceStateSpy: ReturnType<typeof vi.spyOn>;
  let assignSpy: ReturnType<typeof vi.spyOn>;
  let modalHide: Mock<() => void>;

  beforeEach(async () => {
    // Flush setTimeout(0) callbacks left over from a prior case before spying.
    await drainTimers();
    document.body.innerHTML = REMOVE_LOCAL_HTML;
    vi.clearAllMocks();
    modalHide = vi.fn<() => void>();
    ($.fn as unknown as Record<string, unknown>).modal = function (
      this: JQuery,
      action: string,
    ) {
      if (action === "hide") modalHide();
      return this;
    };
    // Fire the post-fade callback synchronously
    ($.fn as unknown as Record<string, unknown>).fadeOut = function (
      this: JQuery,
      _duration: unknown,
      callback?: () => void,
    ) {
      if (typeof callback === "function") callback();
      return this;
    };
    vi.mocked(getState).mockReturnValue({
      utubs: [{ id: 42 }, { id: 43 }],
    } as unknown as ReturnType<typeof getState>);
    vi.mocked(isTagSheetOpen).mockReturnValue(false);
    vi.mocked(isMobile).mockReturnValue(false);
    pushStateSpy = vi
      .spyOn(window.history, "pushState")
      .mockImplementation(() => {});
    replaceStateSpy = vi
      .spyOn(window.history, "replaceState")
      .mockImplementation(() => {});
    assignSpy = vi
      .spyOn(window.location, "assign")
      .mockImplementation(() => {});
  });

  afterEach(() => {
    pushStateSpy.mockRestore();
    replaceStateSpy.mockRestore();
    assignSpy.mockRestore();
    document.body.className = "";
  });

  it("removes the selector, filters the store and resets the active UTub fields", () => {
    removeUTubLocally({ utubID: 42 });

    expect($(".UTubSelector[utubid=42]")).toHaveLength(0);
    expect($(".UTubSelector[utubid=43]")).toHaveLength(1);
    expect(updateUTubDeckCount).toHaveBeenCalledTimes(1);
    expect(applyAlternatingUTubSelectorBackground).toHaveBeenCalledTimes(1);
    expect(hideInputs).toHaveBeenCalledTimes(1);
    expect(modalHide).toHaveBeenCalled();
    expect(clearOpenForm).toHaveBeenCalledTimes(1);
    expect(setState).toHaveBeenCalledWith({
      utubs: [{ id: 43 }],
      activeUTubID: null,
      activeUTubName: null,
      activeUTubDescription: null,
      isCurrentUserOwner: false,
      isCoCreator: false,
      isCurrentUTubLocked: false,
      utubOwnerID: null,
      urls: [],
      tags: [],
      members: [],
      selectedTagIDs: [],
      selectedURLCardID: null,
      multiSelectMode: false,
      selectedURLCardIDs: [],
    });
    expect(setUIWhenNoUTubSelected).toHaveBeenCalledTimes(1);
    expect(emit).toHaveBeenCalledWith(AppEvents.UTUB_DELETED, { utubID: 42 });
    expect(refreshTrashCount).toHaveBeenCalledTimes(1);
  });

  it("still purges the store when the UTub selector is already absent", () => {
    // Real jQuery skips a fadeOut callback on an empty set.
    ($.fn as unknown as Record<string, unknown>).fadeOut = function (
      this: JQuery,
    ) {
      return this;
    };

    removeUTubLocally({ utubID: 999 });

    expect(setState).toHaveBeenCalledWith(
      expect.objectContaining({ activeUTubID: null }),
    );
    expect(emit).toHaveBeenCalledWith(AppEvents.UTUB_DELETED, { utubID: 999 });
  });

  it("resets the lock state when removing a locked UTub", () => {
    document.body.classList.add("utub-locked");
    $("#URLDeckLockIcon").removeClass("hidden");

    removeUTubLocally({ utubID: 42 });

    expect(document.body.classList.contains("utub-locked")).toBe(false);
    expect($("#URLDeckLockIcon").hasClass("hidden")).toBe(true);
  });

  it("resets the UTub deck when no UTubs remain", () => {
    vi.mocked(getNumOfUTubs).mockReturnValue(0);

    removeUTubLocally({ utubID: 42 });

    expect(resetUTubDeckIfNoUTubs).toHaveBeenCalledTimes(1);
    expect(hideInputsAndUpdateUTubDeck).not.toHaveBeenCalled();
  });

  it("updates the UTub deck when UTubs remain", () => {
    vi.mocked(getNumOfUTubs).mockReturnValue(1);

    removeUTubLocally({ utubID: 42 });

    expect(hideInputsAndUpdateUTubDeck).toHaveBeenCalledTimes(1);
    expect(resetUTubDeckIfNoUTubs).not.toHaveBeenCalled();
  });

  it("closes an open tag sheet synchronously before the history write", async () => {
    vi.mocked(isTagSheetOpen).mockReturnValue(true);
    // Faithful stand-in for closeTagSheet's default reconciliation.
    vi.mocked(closeTagSheet).mockImplementation(() => {
      window.history.back();
    });
    const historyBackSpy = vi
      .spyOn(window.history, "back")
      .mockImplementation(() => {});

    try {
      removeUTubLocally({ utubID: 42 });

      expect(closeTagSheet).toHaveBeenCalledTimes(1);
      expect(closeTagSheet).toHaveBeenCalledWith({
        returnFocus: false,
        trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP,
      });
      await drainTimers();

      expect(historyBackSpy).toHaveBeenCalledTimes(1);
      expect(historyBackSpy.mock.invocationCallOrder[0]).toBeLessThan(
        replaceStateSpy.mock.invocationCallOrder[0],
      );
    } finally {
      historyBackSpy.mockRestore();
    }
  });

  it("does not close the tag sheet when it is closed", () => {
    removeUTubLocally({ utubID: 42 });

    expect(closeTagSheet).not.toHaveBeenCalled();
  });

  it("replaces history with /home exactly once and never pushes by default", async () => {
    removeUTubLocally({ utubID: 42 });
    await drainTimers();

    expect(replaceStateSpy).toHaveBeenCalledTimes(1);
    expect(replaceStateSpy).toHaveBeenCalledWith(null, "", "/home");
    expect(pushStateSpy).not.toHaveBeenCalled();
  });

  it("pushes then replaces history when pushHistoryEntry is true", async () => {
    removeUTubLocally({ utubID: 42, pushHistoryEntry: true });
    await drainTimers();

    expect(pushStateSpy).toHaveBeenCalledTimes(1);
    expect(pushStateSpy).toHaveBeenCalledWith(null, "", "/home");
    expect(replaceStateSpy).toHaveBeenCalledTimes(1);
    expect(replaceStateSpy).toHaveBeenCalledWith(null, "", "/home");
    expect(pushStateSpy.mock.invocationCallOrder[0]).toBeLessThan(
      replaceStateSpy.mock.invocationCallOrder[0],
    );
  });

  it.each([
    { label: "default", pushHistoryEntry: false },
    { label: "delete path", pushHistoryEntry: true },
  ])(
    "resets the mobile UI and tracked panel on mobile ($label)",
    ({ pushHistoryEntry }) => {
      vi.mocked(isMobile).mockReturnValue(true);

      removeUTubLocally({ utubID: 42, pushHistoryEntry });

      expect(setMobileUIWhenUTubNotSelectedOrUTubDeleted).toHaveBeenCalledTimes(
        1,
      );
      expect(setCurrentMobilePanel).toHaveBeenCalledWith({
        mobilePanel: "utubs",
      });
    },
  );

  it("does not touch the mobile UI on desktop", () => {
    removeUTubLocally({ utubID: 42 });

    expect(setMobileUIWhenUTubNotSelectedOrUTubDeleted).not.toHaveBeenCalled();
    expect(setCurrentMobilePanel).not.toHaveBeenCalled();
  });

  it("never shows the deck banner and never navigates", async () => {
    removeUTubLocally({ utubID: 42 });
    await drainTimers();

    expect(showURLDeckBannerError).not.toHaveBeenCalled();
    expect(assignSpy).not.toHaveBeenCalled();
  });
});
