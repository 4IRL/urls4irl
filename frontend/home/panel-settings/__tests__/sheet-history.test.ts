// History and stacking contracts: the real shell, the real settings sheet, the
// real Tag sheet and the real handlePopState, over the shared history stub
// (whose back() dispatches popstate synchronously). Only the window-events
// collaborators that rebuild the UTub are mocked.
import { getState, resetStore, setState } from "../../../store/app-store.js";
import {
  _resetTagSheetGestureForTests,
  closeTagSheet,
  consumeTagSheetSelfBackClose,
  isTagSheetOpen,
  openTagSheetFromUserAction,
} from "../../tags/sheet.js";
import { TAG_SHEET_TOGGLE_TRIGGER } from "../../../types/metrics-dim-values.js";
import { initWindowEvents } from "../../window-events.js";
import { AppEvents, emit } from "../../../lib/event-bus.js";
import { initPopover, resetPopover } from "../popover.js";
import { _resetRegistryForTests } from "../registry.js";
import { isSettingsSheetOpen } from "../sheet.js";
import { setPanelSettingsPendingSaveCount } from "../state.js";
import {
  FIXTURE,
  el,
  gear,
  installHistoryStub,
  mockBreakpoint,
  openGear,
  pressKey,
  registerControlled,
  selectUTub,
} from "./helpers.js";
import type { HistoryStub } from "./helpers.js";

const mockResetHomePageToInitialState = vi.fn();
const mockGetUTubInfo = vi.fn();
const mockBuildSelectedUTub = vi.fn();
const mockIsUtubIdValidFromStateAccess = vi.fn(() => true);

vi.mock("../announce.js", () => ({
  announceSettingsStatus: vi.fn(),
}));
vi.mock("../client.js", () => ({
  handleActiveUTubGone: vi.fn(),
  resyncSettings: vi.fn(async () => true),
}));
vi.mock("../../utubs/stale-data.js", () => ({
  updateUTubOnFindingStaleData: vi.fn(async () => {}),
}));
vi.mock("../../onboarding/nudges.js", () => ({
  dismissActiveTip: vi.fn(),
  maybeShowNextTip: vi.fn(),
}));
vi.mock("../../members/row-menu.js", () => ({
  closeAllMemberRowMenus: vi.fn(),
}));
vi.mock("../../utubs/header-fit.js", () => ({
  fitUTubHeaderAndSubheader: vi.fn(),
}));
vi.mock("../../../lib/tooltips.js", () => ({
  hideTooltip: vi.fn(),
  disposeTooltipsWithin: vi.fn(),
}));
// window-events collaborators (the tags/sheet.js and panel-settings modules stay real).
vi.mock("../../mobile.js", () => ({
  isMobile: () => true,
  setMobileUIWhenUTubSelectedOrURLNavSelected: vi.fn(),
  setMobileUIWhenUTubDeckSelected: vi.fn(),
  setMobileUIWhenMemberDeckSelected: vi.fn(),
  setMobileUIWhenTrashSelected: vi.fn(),
  setCurrentMobilePanel: vi.fn(),
}));
vi.mock("../../init.js", () => ({
  resetHomePageToInitialState: (...args: unknown[]) =>
    mockResetHomePageToInitialState(...args),
  setUIWhenNoUTubSelected: vi.fn(),
}));
vi.mock("../../utubs/deck.js", () => ({
  setUTubEventListenersOnInitialPageLoad: vi.fn(),
}));
vi.mock("../../utubs/create.js", () => ({
  setCreateUTubEventListeners: vi.fn(),
}));
vi.mock("../../utubs/selectors.js", () => ({
  getUTubInfo: (...args: unknown[]) => mockGetUTubInfo(...args),
  buildSelectedUTub: (...args: unknown[]) => mockBuildSelectedUTub(...args),
  captureSettingsVersions: () => ({
    settingsVersion: 0,
    memberSettingsVersion: 0,
    policyLearnedVersion: 0,
  }),
  shouldKeepSettings: () => ({
    keepSettings: false,
    keepMemberSettings: false,
    forceShortLinksOff: false,
  }),
}));
vi.mock("../../utubs/utils.js", () => ({
  isValidUTubID: vi.fn(),
  isUtubIdValidOnPageLoad: vi.fn(),
  isUtubIdValidFromStateAccess: () => mockIsUtubIdValidFromStateAccess(),
}));
vi.mock("../../members/deck.js", () => ({
  setMemberDeckWhenNoUTubSelected: vi.fn(),
}));
vi.mock("../../tags/deck.js", () => ({
  setTagDeckSubheaderWhenNoUTubSelected: vi.fn(),
}));
vi.mock("../../urls/deck.js", () => ({
  showURLDeckBannerError: vi.fn(),
}));
vi.mock("../../search/cross-utub-search.js", () => ({
  exitCrossUtubSearchMode: vi.fn(),
  isCrossUtubSearchActive: () => false,
  restoreCrossUtubSearchFromHistory: vi.fn(),
}));
vi.mock("../../trash/panel.js", () => ({
  openTrash: vi.fn(),
  closeTrash: vi.fn(),
  isTrashOpen: () => false,
}));

const PAGE_MARKUP = `
  <main id="mainPanel">
    <div id="mainChild"></div>
    <div id="tagSheetViewport">
      <div id="tagDeckSheet" class="hidden">
        <button id="tagSheetHandle" type="button">handle</button>
        <div id="tagSheetBody" inert></div>
      </div>
    </div>
    <div id="tagSheetBackdrop"></div>
  </main>
  <footer id="pageFooter"></footer>
`;

const UTUB = 7;
const BASE = { UTubID: UTUB, mobilePanel: "urls" };
const TAG_STATE = { ...BASE, tagSheetOpen: true };
const SHEET_HEIGHT = 400;

function pointer({
  type,
  target,
  clientY,
}: {
  type: string;
  target: HTMLElement;
  clientY: number;
}): void {
  target.dispatchEvent(
    new PointerEvent(type, {
      pointerId: 1,
      pointerType: "touch",
      clientY,
      bubbles: true,
      cancelable: true,
    }),
  );
}

function isInert(element: HTMLElement): boolean {
  return element.closest("[inert]") !== null;
}

describe("panel settings sheet history and stacking", () => {
  const originalMatchMedia = window.matchMedia;
  let historyStub: HistoryStub;
  let popstateHandler: EventListener;
  let widthSpy: ReturnType<typeof vi.spyOn>;

  function setCurrentEntry({ state }: { state: unknown }): void {
    historyStub.entries()[historyStub.index()] = state;
  }

  // The shell is initialised once per test and before any Tag sheet opens, so
  // its Escape handler is bound first (as in the real init order).
  function initShell({ panel = "urls" }: { panel?: string } = {}): void {
    initPopover();
    registerControlled({ panel: panel as never });
    selectUTub({ utubID: UTUB });
  }

  function setupSheet({
    panel = "urls",
    base = BASE as unknown,
  }: { panel?: string; base?: unknown } = {}): void {
    setCurrentEntry({ state: base });
    initShell({ panel });
    openGear(panel);
  }

  function openTagSheetOverBase(): void {
    setCurrentEntry({ state: BASE });
    openTagSheetFromUserAction();
  }

  // Tag sheet open over BASE (history [BASE, TAG]) with the Tags gear's
  // settings sheet stacked on top.
  function openStacked(): void {
    initShell({ panel: "tags" });
    openTagSheetOverBase();
    setState({ selectedTagIDs: [3, 4] });
    openGear("tags");
  }

  function stubSheetHeight(): void {
    vi.spyOn(el("panelSettingsSheet"), "getBoundingClientRect").mockReturnValue(
      {
        height: SHEET_HEIGHT,
        width: 390,
        top: 0,
        left: 0,
        right: 390,
        bottom: SHEET_HEIGHT,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      } as DOMRect,
    );
  }

  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
    mockGetUTubInfo.mockResolvedValue({ id: UTUB, name: "UTub" });
    document.body.innerHTML = FIXTURE + PAGE_MARKUP;
    resetStore();
    setPanelSettingsPendingSaveCount({ count: 0 });
    historyStub = installHistoryStub();
    mockBreakpoint({ matches: true });
    widthSpy = vi.spyOn(window.jQuery.fn, "width").mockReturnValue(500);

    const addSpy = vi.spyOn(window, "addEventListener");
    initWindowEvents();
    const call = addSpy.mock.calls.find(([type]) => type === "popstate");
    popstateHandler = call?.[1] as EventListener;
    addSpy.mockRestore();
  });

  afterEach(() => {
    window.removeEventListener("popstate", popstateHandler);
    resetPopover();
    _resetRegistryForTests();
    if (isTagSheetOpen()) {
      closeTagSheet({
        trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP,
        returnFocus: false,
      });
    }
    // The Tag sheet's module-level self-back flag outlives the test.
    consumeTagSheetSelfBackClose();
    _resetTagSheetGestureForTests();
    historyStub.restore();
    widthSpy.mockRestore();
    window.matchMedia = originalMatchMedia;
    vi.useRealTimers();
  });

  it("uses the real Tag sheet module", () => {
    selectUTub({ utubID: UTUB });
    openTagSheetOverBase();

    expect(isTagSheetOpen()).toBe(true);
  });

  describe("Back closes", () => {
    it("closes the sheet without rebuilding the UTub", () => {
      setupSheet();
      history.back();

      expect(isSettingsSheetOpen()).toBe(false);
      expect(mockGetUTubInfo).not.toHaveBeenCalled();
      expect(mockBuildSelectedUTub).not.toHaveBeenCalled();
      expect(mockResetHomePageToInitialState).not.toHaveBeenCalled();
      expect(getState().activeUTubID).toBe(UTUB);
    });

    it("does not bump the popstate generation (an earlier rebuild still applies)", async () => {
      let resolveEarlier!: (value: unknown) => void;
      mockGetUTubInfo.mockReturnValueOnce(
        new Promise((resolve) => {
          resolveEarlier = resolve;
        }),
      );
      // An earlier rebuild popstate is still in flight.
      window.dispatchEvent(
        new PopStateEvent("popstate", {
          state: { UTubID: 9, mobilePanel: "urls" },
        }),
      );
      expect(mockGetUTubInfo).toHaveBeenCalledTimes(1);

      setupSheet();
      history.back();
      resolveEarlier({ id: 9, name: "Nine" });
      await vi.advanceTimersByTimeAsync(0);

      expect(mockBuildSelectedUTub).toHaveBeenCalledTimes(1);
    });

    it("matches a non-null base carrying tagSheetOpen without rebuilding", () => {
      openStacked();
      const pushes = historyStub.pushState.mock.calls;
      expect(pushes[pushes.length - 1][0]).toEqual({
        ...TAG_STATE,
        panelSettingsSheetOpen: true,
      });

      history.back();

      expect(isSettingsSheetOpen()).toBe(false);
      expect(mockGetUTubInfo).not.toHaveBeenCalled();
    });
  });

  describe("stacked over the Tag sheet", () => {
    it("closes only the settings sheet on the first Back, then the Tag sheet", () => {
      openStacked();
      expect(isSettingsSheetOpen()).toBe(true);
      expect(isInert(el("tagSheetHandle"))).toBe(true);

      history.back();

      expect(isSettingsSheetOpen()).toBe(false);
      expect(isTagSheetOpen()).toBe(true);
      expect(getState().selectedTagIDs).toEqual([3, 4]);
      expect(document.activeElement).toBe(gear("tags"));
      expect(isInert(el("tagSheetHandle"))).toBe(false);
      expect(mockGetUTubInfo).not.toHaveBeenCalled();

      history.back();

      expect(isTagSheetOpen()).toBe(false);
    });

    it("closes only the settings sheet on Escape", () => {
      openStacked();
      pressKey({ key: "Escape" });

      expect(isSettingsSheetOpen()).toBe(false);
      expect(isTagSheetOpen()).toBe(true);
      expect(getState().selectedTagIDs).toEqual([3, 4]);
    });

    it("leaves the Tag sheet untouched by a committed or snapped-back drag", () => {
      openStacked();
      stubSheetHeight();
      const tagSheet = el("tagDeckSheet");
      const header = el("panelSettingsSheetHeader");

      // Snap-back: a short slow drag.
      pointer({ type: "pointerdown", target: header, clientY: 100 });
      pointer({ type: "pointermove", target: header, clientY: 130 });
      pointer({ type: "pointerup", target: header, clientY: 130 });
      expect(isSettingsSheetOpen()).toBe(true);
      expect(isInert(el("tagSheetHandle"))).toBe(true);
      expect(tagSheet.style.transform).toBe("");
      expect(tagSheet.classList.contains("tag-sheet-dragging")).toBe(false);

      // Commit: past the distance threshold.
      pointer({ type: "pointerdown", target: header, clientY: 100 });
      pointer({ type: "pointermove", target: header, clientY: 400 });
      expect(isInert(el("tagSheetHandle"))).toBe(true);
      pointer({ type: "pointerup", target: header, clientY: 400 });

      expect(isSettingsSheetOpen()).toBe(false);
      expect(isTagSheetOpen()).toBe(true);
      expect(tagSheet.style.transform).toBe("");
      expect(tagSheet.classList.contains("tag-sheet-dragging")).toBe(false);
      // The settings flag (not the Tag flag) consumed the drag's popstate.
      expect(consumeTagSheetSelfBackClose()).toBe(false);
      expect(getState().selectedTagIDs).toEqual([3, 4]);
      expect(mockGetUTubInfo).not.toHaveBeenCalled();
    });
  });

  describe("real Tag sheet back in flight", () => {
    function closeTagWithBackPending(): () => void {
      const realBack = historyStub.back.getMockImplementation() as () => void;
      historyStub.back.mockImplementationOnce(() => {});
      closeTagSheet({
        trigger: TAG_SHEET_TOGGLE_TRIGGER.TAP,
        returnFocus: false,
      });
      return realBack;
    }

    it("drops a gear tap until the Tag popstate lands, then opens", () => {
      initShell({ panel: "tags" });
      openTagSheetOverBase();
      const deliverTagBack = closeTagWithBackPending();
      const pushesBefore = historyStub.pushState.mock.calls.length;

      expect(isTagSheetOpen()).toBe(false);
      openGear("tags");
      expect(historyStub.pushState.mock.calls.length).toBe(pushesBefore);
      expect(isSettingsSheetOpen()).toBe(false);

      deliverTagBack();
      openGear("tags");
      expect(isSettingsSheetOpen()).toBe(true);
    });

    it("drops the next in-flight gear tap too, after an earlier back() landed", () => {
      initShell({ panel: "tags" });
      openTagSheetOverBase();
      const deliverTagBack = closeTagWithBackPending();
      openGear("tags");
      deliverTagBack();
      vi.advanceTimersByTime(10_000);

      openTagSheetOverBase();
      closeTagWithBackPending();
      const pushesBefore = historyStub.pushState.mock.calls.length;
      openGear("tags");

      expect(historyStub.pushState.mock.calls.length).toBe(pushesBefore);
      expect(isSettingsSheetOpen()).toBe(false);
    });

    it("opens on a tagSheetOpen entry when the Tag sheet is closed and no back() is pending", () => {
      initShell({ panel: "tags" });
      // Reload with the Tag sheet's entry current: nothing is in flight.
      setCurrentEntry({ state: TAG_STATE });
      expect(isTagSheetOpen()).toBe(false);

      openGear("tags");

      expect(isSettingsSheetOpen()).toBe(true);
    });
  });

  describe("user close removes the entry", () => {
    it("handles the next Back exactly as before the sheet opened", () => {
      openStacked();
      el("panelSettingsSheetClose").click();

      expect(isSettingsSheetOpen()).toBe(false);
      expect(isTagSheetOpen()).toBe(true);
      expect(history.state).toEqual(TAG_STATE);

      history.back();

      expect(isTagSheetOpen()).toBe(false);
    });
  });

  describe("forced close then Back", () => {
    it("strips the key; the next Back is the existing base-entry handling", () => {
      setupSheet();
      emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "member-deck" });

      expect(history.state).toEqual(BASE);
      history.back();

      expect(isSettingsSheetOpen()).toBe(false);
      expect(mockGetUTubInfo).toHaveBeenCalledTimes(1);
    });

    it("strips the key under the Tag sheet; the duplicate entry takes the existing Tag path", () => {
      openStacked();
      emit(AppEvents.MOBILE_DECK_SWITCHED, { target: "member-deck" });

      expect(history.state).toEqual(TAG_STATE);
      // Accepted: the leftover duplicate behaves like any tagSheetOpen entry.
      history.back();
      expect(mockGetUTubInfo).toHaveBeenCalledTimes(1);

      history.back();
      expect(historyStub.index()).toBe(0);
    });

    it("strips the key on a stacked UTUB_SELECTED and leaves the Tag entry", () => {
      openStacked();
      historyStub.replaceState.mockClear();
      emit(AppEvents.UTUB_SELECTED, {
        utubID: UTUB,
        utubName: "UTub",
        urls: [],
        tags: [],
        members: [],
        utubOwnerID: 1,
        isCurrentUserOwner: true,
        currentUserID: 1,
      });

      expect(isSettingsSheetOpen()).toBe(false);
      expect(historyStub.replaceState).toHaveBeenCalledTimes(1);
      expect(history.state).toEqual(TAG_STATE);
    });
  });

  describe("Forward and reload", () => {
    it("handles a keyed entry reached while closed as its base entry", () => {
      initPopover();
      window.dispatchEvent(
        new PopStateEvent("popstate", {
          state: { ...BASE, panelSettingsSheetOpen: true },
        }),
      );

      expect(isSettingsSheetOpen()).toBe(false);
      expect(mockGetUTubInfo).toHaveBeenCalledTimes(1);
    });

    it("captures a keyed reload state as the base and closes without a rebuild", () => {
      const keyed = { ...BASE, panelSettingsSheetOpen: true };
      setupSheet({ base: keyed });

      expect(history.state).toEqual(keyed);
      expect(historyStub.pushState.mock.calls[0][0]).toEqual(keyed);
      history.back();

      expect(isSettingsSheetOpen()).toBe(false);
      expect(mockGetUTubInfo).not.toHaveBeenCalled();
    });

    it("never reopens the sheet when initialised on a keyed entry", () => {
      setCurrentEntry({ state: { ...BASE, panelSettingsSheetOpen: true } });
      initPopover();
      selectUTub({ utubID: UTUB });

      expect(isSettingsSheetOpen()).toBe(false);
    });
  });

  describe("no UTub", () => {
    it("pushes only the marker and closes on the null base without a reset", () => {
      setCurrentEntry({ state: null });
      initPopover();
      registerControlled({
        id: "utubs-sec",
        panel: "utubs",
        scope: "user",
        userKind: "global",
      });
      openGear("utubs");

      expect(historyStub.pushState.mock.calls[0][0]).toEqual({
        panelSettingsSheetOpen: true,
      });
      history.back();

      expect(isSettingsSheetOpen()).toBe(false);
      expect(mockResetHomePageToInitialState).not.toHaveBeenCalled();
    });
  });
});
