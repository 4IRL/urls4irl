import {
  CROSS_UTUB_SEARCH_CLOSE_TRIGGER,
  MOBILE_NAV_TRIGGER,
  TAG_SHEET_TOGGLE_TRIGGER,
} from "../../types/metrics-dim-values.js";
import { UI_EVENTS } from "../../types/metrics-events.js";
import { initWindowEvents } from "../window-events.js";

const mockResetHomePageToInitialState = vi.fn();
const mockSetUIWhenNoUTubSelected = vi.fn();
const mockSetMobileUIWhenUTubSelectedOrURLNavSelected = vi.fn();
const mockSetMobileUIWhenUTubDeckSelected = vi.fn();
const mockSetMobileUIWhenMemberDeckSelected = vi.fn();
const mockSetCurrentMobilePanel = vi.fn();
const mockSetUTubEventListenersOnInitialPageLoad = vi.fn();
const mockSetCreateUTubEventListeners = vi.fn();
const mockGetUTubInfo = vi.fn();
const mockBuildSelectedUTub = vi.fn();
const mockIsValidUTubID = vi.fn();
const mockIsUtubIdValidOnPageLoad = vi.fn();
const mockIsUtubIdValidFromStateAccess = vi.fn();
const mockSetMemberDeckWhenNoUTubSelected = vi.fn();
const mockSetTagDeckSubheaderWhenNoUTubSelected = vi.fn();
const mockExitCrossUtubSearchMode = vi.fn();
const mockIsCrossUtubSearchActive = vi.fn(() => false);
const mockRestoreCrossUtubSearchFromHistory = vi.fn();
const mockEmit = vi.fn();
const mockOpenTagSheet = vi.fn();
const mockCloseTagSheet = vi.fn();
const mockIsTagSheetOpen = vi.fn(() => false);
const mockGetTagSheetOriginPanel = vi.fn<() => string | null>(() => null);
const mockBeginPopstateClose = vi.fn();
const mockEndPopstateClose = vi.fn();
const mockConsumeTagSheetSelfBackClose = vi.fn(() => false);

vi.mock("../../lib/config.js", () => ({
  APP_CONFIG: {
    debugEnabled: true,
    routes: { errorPage: "/error" },
    strings: {
      UTUB_QUERY_PARAM: "UTubID",
      MOBILE_PANEL_QUERY_PARAM: "panel",
      MOBILE_PANEL_ANNOUNCEMENT_UTUBS: "Now showing UTub list",
      MOBILE_PANEL_ANNOUNCEMENT_URLS: "Now showing URLs",
      MOBILE_PANEL_ANNOUNCEMENT_MEMBERS: "Now showing Members",
    },
  },
}));
vi.mock("../../lib/constants.js", () => ({
  TABLET_WIDTH: 992,
}));
vi.mock("../../lib/metrics-client.js", () => ({
  emit: (...args: unknown[]) => mockEmit(...args),
}));
vi.mock("../mobile.js", () => ({
  setMobileUIWhenUTubSelectedOrURLNavSelected: (...args: unknown[]) =>
    mockSetMobileUIWhenUTubSelectedOrURLNavSelected(...args),
  setMobileUIWhenUTubDeckSelected: (...args: unknown[]) =>
    mockSetMobileUIWhenUTubDeckSelected(...args),
  setMobileUIWhenMemberDeckSelected: (...args: unknown[]) =>
    mockSetMobileUIWhenMemberDeckSelected(...args),
  setCurrentMobilePanel: (...args: unknown[]) =>
    mockSetCurrentMobilePanel(...args),
}));
vi.mock("../init.js", () => ({
  resetHomePageToInitialState: (...args: unknown[]) =>
    mockResetHomePageToInitialState(...args),
  setUIWhenNoUTubSelected: (...args: unknown[]) =>
    mockSetUIWhenNoUTubSelected(...args),
}));
vi.mock("../utubs/deck.js", () => ({
  setUTubEventListenersOnInitialPageLoad: (...args: unknown[]) =>
    mockSetUTubEventListenersOnInitialPageLoad(...args),
}));
vi.mock("../utubs/create.js", () => ({
  setCreateUTubEventListeners: (...args: unknown[]) =>
    mockSetCreateUTubEventListeners(...args),
}));
vi.mock("../utubs/selectors.js", () => ({
  getUTubInfo: (...args: unknown[]) => mockGetUTubInfo(...args),
  buildSelectedUTub: (...args: unknown[]) => mockBuildSelectedUTub(...args),
}));
vi.mock("../utubs/utils.js", () => ({
  isValidUTubID: (...args: unknown[]) => mockIsValidUTubID(...args),
  isUtubIdValidOnPageLoad: (...args: unknown[]) =>
    mockIsUtubIdValidOnPageLoad(...args),
  isUtubIdValidFromStateAccess: (...args: unknown[]) =>
    mockIsUtubIdValidFromStateAccess(...args),
}));
vi.mock("../members/deck.js", () => ({
  setMemberDeckWhenNoUTubSelected: (...args: unknown[]) =>
    mockSetMemberDeckWhenNoUTubSelected(...args),
}));
vi.mock("../tags/deck.js", () => ({
  setTagDeckSubheaderWhenNoUTubSelected: (...args: unknown[]) =>
    mockSetTagDeckSubheaderWhenNoUTubSelected(...args),
}));
vi.mock("../search/cross-utub-search.js", () => ({
  exitCrossUtubSearchMode: (...args: unknown[]) =>
    mockExitCrossUtubSearchMode(...args),
  isCrossUtubSearchActive: () => mockIsCrossUtubSearchActive(),
  restoreCrossUtubSearchFromHistory: (...args: unknown[]) =>
    mockRestoreCrossUtubSearchFromHistory(...args),
}));
vi.mock("../tags/sheet.js", () => ({
  openTagSheet: (...args: unknown[]) => mockOpenTagSheet(...args),
  closeTagSheet: (...args: unknown[]) => mockCloseTagSheet(...args),
  isTagSheetOpen: () => mockIsTagSheetOpen(),
  getTagSheetOriginPanel: () => mockGetTagSheetOriginPanel(),
  beginPopstateClose: (...args: unknown[]) => mockBeginPopstateClose(...args),
  endPopstateClose: (...args: unknown[]) => mockEndPopstateClose(...args),
  consumeTagSheetSelfBackClose: () => mockConsumeTagSheetSelfBackClose(),
}));

const $ = window.jQuery;

describe("window-events", () => {
  let addEventListenerSpy: ReturnType<typeof vi.spyOn>;
  let popstateHandler: ((event: PopStateEvent) => void) | undefined;
  let pageshowHandler: ((event: PageTransitionEvent) => void) | undefined;

  beforeEach(() => {
    vi.clearAllMocks();
    // clearAllMocks does not reset implementations set via vi.fn(impl), but it
    // also does not reset a later .mockReturnValue — pin the default each test.
    mockIsCrossUtubSearchActive.mockReturnValue(false);
    mockIsTagSheetOpen.mockReturnValue(false);
    mockGetTagSheetOriginPanel.mockReturnValue(null);
    mockConsumeTagSheetSelfBackClose.mockReturnValue(false);
    popstateHandler = undefined;
    pageshowHandler = undefined;

    addEventListenerSpy = vi
      .spyOn(window, "addEventListener")
      .mockImplementation((type: string, listener: unknown) => {
        if (type === "popstate") {
          popstateHandler = listener as (event: PopStateEvent) => void;
        }
        if (type === "pageshow") {
          pageshowHandler = listener as (event: PageTransitionEvent) => void;
        }
      });
  });

  afterEach(() => {
    addEventListenerSpy.mockRestore();
  });

  describe("initWindowEvents", () => {
    it("registers popstate and pageshow event listeners", () => {
      initWindowEvents();

      expect(addEventListenerSpy).toHaveBeenCalledWith(
        "popstate",
        expect.any(Function),
      );
      expect(addEventListenerSpy).toHaveBeenCalledWith(
        "pageshow",
        expect.any(Function),
      );
    });
  });

  describe("handlePopState", () => {
    beforeEach(() => {
      document.body.innerHTML = '<span id="MobilePanelAnnouncement"></span>';
      initWindowEvents();
    });

    it("resets to initial state when state is null", () => {
      const event = new PopStateEvent("popstate", { state: null });
      popstateHandler!(event);

      expect(mockResetHomePageToInitialState).toHaveBeenCalled();
    });

    it("swallows the self-initiated tag-sheet back-close popstate without rebuilding", () => {
      // The tap-close's own history.back() arms the self-close flag; the
      // resulting popstate must be a no-op — no UTub rebuild (which would reset
      // selectedTagIDs and wipe the active tag filter), no bracket, no reset.
      mockConsumeTagSheetSelfBackClose.mockReturnValue(true);
      mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
      mockGetUTubInfo.mockResolvedValue({ id: 5, name: "Filtered UTub" });

      const event = new PopStateEvent("popstate", {
        state: { UTubID: 5, mobilePanel: "urls" },
      });
      popstateHandler!(event);

      expect(mockBuildSelectedUTub).not.toHaveBeenCalled();
      expect(mockGetUTubInfo).not.toHaveBeenCalled();
      expect(mockBeginPopstateClose).not.toHaveBeenCalled();
      expect(mockResetHomePageToInitialState).not.toHaveBeenCalled();
    });

    it("fetches and builds UTub when state has a valid UTubID", async () => {
      const fakeUTub = { id: 5, name: "Test UTub" };
      mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
      mockGetUTubInfo.mockResolvedValue(fakeUTub);

      const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(1200);

      const event = new PopStateEvent("popstate", {
        state: { UTubID: 5 },
      });
      popstateHandler!(event);

      expect(mockIsUtubIdValidFromStateAccess).toHaveBeenCalledWith(5);

      await vi.waitFor(() => {
        expect(mockBuildSelectedUTub).toHaveBeenCalledWith(fakeUTub);
      });

      expect(
        mockSetMobileUIWhenUTubSelectedOrURLNavSelected,
      ).not.toHaveBeenCalled();

      widthSpy.mockRestore();
    });

    it("replaces state and resets when UTubID is invalid (deleted UTub)", () => {
      mockIsUtubIdValidFromStateAccess.mockReturnValue(false);

      const replaceStateSpy = vi.spyOn(window.history, "replaceState");

      const event = new PopStateEvent("popstate", {
        state: { UTubID: 999 },
      });
      popstateHandler!(event);

      expect(replaceStateSpy).toHaveBeenCalledWith(null, "", "/home");
      expect(mockResetHomePageToInitialState).toHaveBeenCalled();

      replaceStateSpy.mockRestore();
    });

    it("restores cross-UTub search when state carries a crossSearch payload", () => {
      const crossSearch = { query: "cats", fields: ["url", "title", "tag"] };
      const event = new PopStateEvent("popstate", { state: { crossSearch } });
      popstateHandler!(event);

      expect(mockRestoreCrossUtubSearchFromHistory).toHaveBeenCalledWith(
        crossSearch,
      );
      // The crossSearch branch returns early — no UTub rebuild or home reset.
      expect(mockResetHomePageToInitialState).not.toHaveBeenCalled();
      expect(mockIsUtubIdValidFromStateAccess).not.toHaveBeenCalled();
    });

    it("exits search mode when popping to a UTub entry while search is open", async () => {
      mockIsCrossUtubSearchActive.mockReturnValue(true);
      mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
      mockGetUTubInfo.mockResolvedValue({ id: 5, name: "Test UTub" });
      const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(1200);

      const event = new PopStateEvent("popstate", { state: { UTubID: 5 } });
      popstateHandler!(event);

      expect(mockExitCrossUtubSearchMode).toHaveBeenCalledWith({
        trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.HISTORY_NAV,
      });
      await vi.waitFor(() => {
        expect(mockBuildSelectedUTub).toHaveBeenCalled();
      });

      widthSpy.mockRestore();
    });

    it("does not exit search mode when popping to a UTub entry and search is closed", () => {
      mockIsCrossUtubSearchActive.mockReturnValue(false);
      mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
      mockGetUTubInfo.mockResolvedValue({ id: 5, name: "Test UTub" });

      const event = new PopStateEvent("popstate", { state: { UTubID: 5 } });
      popstateHandler!(event);

      expect(mockExitCrossUtubSearchMode).not.toHaveBeenCalled();
    });

    it("resets to initial state when state has no UTubID property (non-UTub state)", () => {
      const event = new PopStateEvent("popstate", {
        state: { someOtherProp: "value" },
      });
      popstateHandler!(event);

      expect(mockResetHomePageToInitialState).toHaveBeenCalled();
      expect(mockIsUtubIdValidFromStateAccess).not.toHaveBeenCalled();
    });

    it("triggers mobile UI when on mobile viewport after valid UTub navigation", async () => {
      const fakeUTub = { id: 3, name: "Mobile UTub" };
      mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
      mockGetUTubInfo.mockResolvedValue(fakeUTub);

      const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(500);

      const event = new PopStateEvent("popstate", {
        state: { UTubID: 3 },
      });
      popstateHandler!(event);

      await vi.waitFor(() => {
        expect(mockBuildSelectedUTub).toHaveBeenCalledWith(fakeUTub);
      });

      expect(
        mockSetMobileUIWhenUTubSelectedOrURLNavSelected,
      ).toHaveBeenCalled();

      widthSpy.mockRestore();
    });

    it("resets when getUTubInfo rejects (error fetching UTub)", async () => {
      mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
      mockGetUTubInfo.mockRejectedValue(new Error("fetch failed"));

      const event = new PopStateEvent("popstate", {
        state: { UTubID: 7 },
      });
      popstateHandler!(event);

      await vi.waitFor(() => {
        expect(mockResetHomePageToInitialState).toHaveBeenCalled();
      });
    });

    describe("{ UTubID, mobilePanel } branch", () => {
      it("routes to the UTub deck and announces on a `utubs` panel popstate (mobile)", async () => {
        const fakeUTub = { id: 5, name: "Panel UTub" };
        mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
        mockGetUTubInfo.mockResolvedValue(fakeUTub);
        const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(500);

        const event = new PopStateEvent("popstate", {
          state: { UTubID: 5, mobilePanel: "utubs" },
        });
        popstateHandler!(event);

        await vi.waitFor(() => {
          expect(mockBuildSelectedUTub).toHaveBeenCalledWith(fakeUTub);
        });
        expect(mockSetMobileUIWhenUTubDeckSelected).toHaveBeenCalled();
        expect(mockSetCurrentMobilePanel).toHaveBeenCalledWith({
          mobilePanel: "utubs",
        });
        expect($("#MobilePanelAnnouncement").text()).toBe(
          "Now showing UTub list",
        );
        expect(mockEmit).toHaveBeenCalledWith({
          event: UI_EVENTS.UI_MOBILE_NAV,
          target: "utubs",
          trigger: MOBILE_NAV_TRIGGER.HISTORY_NAV,
        });

        widthSpy.mockRestore();
      });

      it("routes to the URL deck and announces on a `urls` panel popstate (mobile)", async () => {
        const fakeUTub = { id: 6, name: "Panel UTub" };
        mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
        mockGetUTubInfo.mockResolvedValue(fakeUTub);
        const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(500);

        const event = new PopStateEvent("popstate", {
          state: { UTubID: 6, mobilePanel: "urls" },
        });
        popstateHandler!(event);

        await vi.waitFor(() => {
          expect(mockBuildSelectedUTub).toHaveBeenCalledWith(fakeUTub);
        });
        expect(
          mockSetMobileUIWhenUTubSelectedOrURLNavSelected,
        ).toHaveBeenCalled();
        expect($("#MobilePanelAnnouncement").text()).toBe("Now showing URLs");
        expect(mockEmit).toHaveBeenCalledWith({
          event: UI_EVENTS.UI_MOBILE_NAV,
          target: "urls",
          trigger: MOBILE_NAV_TRIGGER.HISTORY_NAV,
        });

        widthSpy.mockRestore();
      });

      it("routes to the Member deck and announces on a `members` panel popstate (mobile)", async () => {
        const fakeUTub = { id: 7, name: "Panel UTub" };
        mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
        mockGetUTubInfo.mockResolvedValue(fakeUTub);
        const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(500);

        const event = new PopStateEvent("popstate", {
          state: { UTubID: 7, mobilePanel: "members" },
        });
        popstateHandler!(event);

        await vi.waitFor(() => {
          expect(mockBuildSelectedUTub).toHaveBeenCalledWith(fakeUTub);
        });
        expect(mockSetMobileUIWhenMemberDeckSelected).toHaveBeenCalled();
        expect($("#MobilePanelAnnouncement").text()).toBe(
          "Now showing Members",
        );
        expect(mockEmit).toHaveBeenCalledWith({
          event: UI_EVENTS.UI_MOBILE_NAV,
          target: "members",
          trigger: MOBILE_NAV_TRIGGER.HISTORY_NAV,
        });

        widthSpy.mockRestore();
      });

      it("replaces state and resets when the panel entry's UTubID is invalid", () => {
        mockIsUtubIdValidFromStateAccess.mockReturnValue(false);
        const replaceStateSpy = vi.spyOn(window.history, "replaceState");

        const event = new PopStateEvent("popstate", {
          state: { UTubID: 999, mobilePanel: "urls" },
        });
        popstateHandler!(event);

        expect(replaceStateSpy).toHaveBeenCalledWith(null, "", "/home");
        expect(mockResetHomePageToInitialState).toHaveBeenCalled();

        replaceStateSpy.mockRestore();
      });

      it("rebuilds the UTub but does not route/announce on desktop", async () => {
        const fakeUTub = { id: 8, name: "Panel UTub" };
        mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
        mockGetUTubInfo.mockResolvedValue(fakeUTub);
        const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(1200);

        const event = new PopStateEvent("popstate", {
          state: { UTubID: 8, mobilePanel: "members" },
        });
        popstateHandler!(event);

        await vi.waitFor(() => {
          expect(mockBuildSelectedUTub).toHaveBeenCalledWith(fakeUTub);
        });
        expect(mockSetMobileUIWhenMemberDeckSelected).not.toHaveBeenCalled();
        expect(mockEmit).not.toHaveBeenCalled();
        expect($("#MobilePanelAnnouncement").text()).toBe("");

        widthSpy.mockRestore();
      });

      it("stale-guard: an out-of-order older popstate resolution does not apply", async () => {
        mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
        const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(500);

        const olderUTub = { id: 5, name: "Older" };
        const newerUTub = { id: 6, name: "Newer" };
        let resolveOlder!: (value: unknown) => void;
        let resolveNewer!: (value: unknown) => void;
        const olderPromise = new Promise((resolve) => {
          resolveOlder = resolve;
        });
        const newerPromise = new Promise((resolve) => {
          resolveNewer = resolve;
        });
        mockGetUTubInfo
          .mockReturnValueOnce(olderPromise)
          .mockReturnValueOnce(newerPromise);

        // Fire two overlapping popstates (older then newer), both still pending.
        popstateHandler!(
          new PopStateEvent("popstate", {
            state: { UTubID: 5, mobilePanel: "utubs" },
          }),
        );
        popstateHandler!(
          new PopStateEvent("popstate", {
            state: { UTubID: 6, mobilePanel: "members" },
          }),
        );

        // Resolve the newer one first, then the (superseded) older one.
        resolveNewer(newerUTub);
        await vi.waitFor(() => {
          expect(mockBuildSelectedUTub).toHaveBeenCalledWith(newerUTub);
        });
        resolveOlder(olderUTub);
        await Promise.resolve();
        await Promise.resolve();

        // Only the newer popstate's effects applied — the older is stale-gated.
        expect(mockBuildSelectedUTub).not.toHaveBeenCalledWith(olderUTub);
        expect(mockSetMobileUIWhenMemberDeckSelected).toHaveBeenCalled();
        expect(mockSetMobileUIWhenUTubDeckSelected).not.toHaveBeenCalled();

        widthSpy.mockRestore();
      });
    });

    describe("{ tagSheetOpen } restore branch", () => {
      it("restores the sheet directly (mobile): openTagSheet with HISTORY_NAV, no deck-switch routers", async () => {
        const fakeUTub = { id: 5, name: "Sheet UTub" };
        mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
        mockGetUTubInfo.mockResolvedValue(fakeUTub);
        const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(500);

        const event = new PopStateEvent("popstate", {
          state: { UTubID: 5, mobilePanel: "urls", tagSheetOpen: true },
        });
        popstateHandler!(event);

        expect(mockBeginPopstateClose).toHaveBeenCalledTimes(1);
        await vi.waitFor(() => {
          expect(mockBuildSelectedUTub).toHaveBeenCalledWith(fakeUTub);
        });
        expect(mockSetCurrentMobilePanel).toHaveBeenCalledWith({
          mobilePanel: "urls",
        });
        expect(mockOpenTagSheet).toHaveBeenCalledWith({
          trigger: TAG_SHEET_TOGGLE_TRIGGER.HISTORY_NAV,
        });
        // Restore bypasses the deck-switch routers (would auto-close the sheet).
        expect(mockSetMobileUIWhenUTubDeckSelected).not.toHaveBeenCalled();
        expect(mockSetMobileUIWhenMemberDeckSelected).not.toHaveBeenCalled();
        expect(mockEndPopstateClose).toHaveBeenCalled();

        widthSpy.mockRestore();
      });

      it("rebuilds the UTub but does not reopen the sheet on desktop", async () => {
        const fakeUTub = { id: 5, name: "Sheet UTub" };
        mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
        mockGetUTubInfo.mockResolvedValue(fakeUTub);
        const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(1200);

        const event = new PopStateEvent("popstate", {
          state: { UTubID: 5, mobilePanel: "urls", tagSheetOpen: true },
        });
        popstateHandler!(event);

        await vi.waitFor(() => {
          expect(mockBuildSelectedUTub).toHaveBeenCalledWith(fakeUTub);
        });
        expect(mockOpenTagSheet).not.toHaveBeenCalled();

        widthSpy.mockRestore();
      });

      it("replaces state and resets when the sheet entry's UTubID is invalid", () => {
        mockIsUtubIdValidFromStateAccess.mockReturnValue(false);
        const replaceStateSpy = vi.spyOn(window.history, "replaceState");

        const event = new PopStateEvent("popstate", {
          state: { UTubID: 999, mobilePanel: "urls", tagSheetOpen: true },
        });
        popstateHandler!(event);

        expect(replaceStateSpy).toHaveBeenCalledWith(null, "", "/home");
        expect(mockResetHomePageToInitialState).toHaveBeenCalled();
        expect(mockEndPopstateClose).toHaveBeenCalled();

        replaceStateSpy.mockRestore();
      });
    });

    describe("Back FROM an open sheet TO a non-sheet entry (DD-31/DD-32)", () => {
      it("same-panel close: returnFocus true, focusLandmark false, suppressAnnouncement true", () => {
        mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
        mockGetUTubInfo.mockResolvedValue({ id: 5, name: "UTub" });
        mockIsTagSheetOpen.mockReturnValue(true);
        mockGetTagSheetOriginPanel.mockReturnValue("urls");
        const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(500);

        popstateHandler!(
          new PopStateEvent("popstate", {
            state: { UTubID: 5, mobilePanel: "urls" },
          }),
        );

        expect(mockCloseTagSheet).toHaveBeenCalledWith({
          returnFocus: true,
          focusLandmark: false,
          suppressAnnouncement: true,
          trigger: TAG_SHEET_TOGGLE_TRIGGER.HISTORY_NAV,
        });

        widthSpy.mockRestore();
      });

      it("cross-panel close: returnFocus false, focusLandmark true, suppressAnnouncement true", () => {
        mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
        mockGetUTubInfo.mockResolvedValue({ id: 5, name: "UTub" });
        mockIsTagSheetOpen.mockReturnValue(true);
        mockGetTagSheetOriginPanel.mockReturnValue("urls");
        const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(500);

        popstateHandler!(
          new PopStateEvent("popstate", {
            state: { UTubID: 5, mobilePanel: "members" },
          }),
        );

        expect(mockCloseTagSheet).toHaveBeenCalledWith({
          returnFocus: false,
          focusLandmark: true,
          suppressAnnouncement: true,
          trigger: TAG_SHEET_TOGGLE_TRIGGER.HISTORY_NAV,
        });

        widthSpy.mockRestore();
      });

      it("legacy bare-UTubID destination close: suppressAnnouncement false (no competing panel announcement)", () => {
        mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
        mockGetUTubInfo.mockResolvedValue({ id: 5, name: "UTub" });
        mockIsTagSheetOpen.mockReturnValue(true);
        mockGetTagSheetOriginPanel.mockReturnValue("urls");
        const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(500);

        popstateHandler!(
          new PopStateEvent("popstate", { state: { UTubID: 5 } }),
        );

        expect(mockCloseTagSheet).toHaveBeenCalledWith({
          returnFocus: true,
          focusLandmark: false,
          suppressAnnouncement: false,
          trigger: TAG_SHEET_TOGGLE_TRIGGER.HISTORY_NAV,
        });

        widthSpy.mockRestore();
      });

      it("does not close the sheet when it is not open", () => {
        mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
        mockGetUTubInfo.mockResolvedValue({ id: 5, name: "UTub" });
        mockIsTagSheetOpen.mockReturnValue(false);
        const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(500);

        popstateHandler!(
          new PopStateEvent("popstate", {
            state: { UTubID: 5, mobilePanel: "members" },
          }),
        );

        expect(mockCloseTagSheet).not.toHaveBeenCalled();

        widthSpy.mockRestore();
      });
    });

    describe("bare { UTubID } branch stale-guard (sibling fix)", () => {
      it("an out-of-order older bare-UTubID resolution does not apply", async () => {
        mockIsUtubIdValidFromStateAccess.mockReturnValue(true);
        const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(500);

        const olderUTub = { id: 5, name: "Older" };
        const newerUTub = { id: 6, name: "Newer" };
        let resolveOlder!: (value: unknown) => void;
        let resolveNewer!: (value: unknown) => void;
        const olderPromise = new Promise((resolve) => {
          resolveOlder = resolve;
        });
        const newerPromise = new Promise((resolve) => {
          resolveNewer = resolve;
        });
        mockGetUTubInfo
          .mockReturnValueOnce(olderPromise)
          .mockReturnValueOnce(newerPromise);

        popstateHandler!(
          new PopStateEvent("popstate", { state: { UTubID: 5 } }),
        );
        popstateHandler!(
          new PopStateEvent("popstate", { state: { UTubID: 6 } }),
        );

        resolveNewer(newerUTub);
        await vi.waitFor(() => {
          expect(mockBuildSelectedUTub).toHaveBeenCalledWith(newerUTub);
        });
        resolveOlder(olderUTub);
        await Promise.resolve();
        await Promise.resolve();

        expect(mockBuildSelectedUTub).not.toHaveBeenCalledWith(olderUTub);
        // Only one mobile-UI application (from the newer popstate).
        expect(
          mockSetMobileUIWhenUTubSelectedOrURLNavSelected,
        ).toHaveBeenCalledTimes(1);

        widthSpy.mockRestore();
      });
    });
  });

  describe("handlePageShow", () => {
    beforeEach(() => {
      initWindowEvents();
      // Default: no history state, no search params
      Object.defineProperty(window, "location", {
        value: { search: "", assign: vi.fn() },
        writable: true,
        configurable: true,
      });
      vi.spyOn(window.history, "replaceState").mockImplementation(vi.fn());
    });

    afterEach(() => {
      vi.restoreAllMocks();
    });

    it("sets initial listeners and UI when no history state and no search params", () => {
      // history.state is null by default
      Object.defineProperty(history, "state", {
        value: null,
        writable: true,
        configurable: true,
      });
      Object.defineProperty(window, "location", {
        value: { search: "", assign: vi.fn() },
        writable: true,
        configurable: true,
      });

      const event = new Event("pageshow") as PageTransitionEvent;
      pageshowHandler!(event);

      expect(mockSetUTubEventListenersOnInitialPageLoad).toHaveBeenCalled();
      expect(mockSetCreateUTubEventListeners).toHaveBeenCalled();
      expect(mockSetUIWhenNoUTubSelected).toHaveBeenCalled();
      expect(mockSetMemberDeckWhenNoUTubSelected).toHaveBeenCalled();
      expect(mockSetTagDeckSubheaderWhenNoUTubSelected).toHaveBeenCalled();
    });

    it("fetches UTub info when history.state has UTubID", async () => {
      const fakeUTub = { id: 2, name: "Restored UTub" };
      Object.defineProperty(history, "state", {
        value: { UTubID: 2 },
        writable: true,
        configurable: true,
      });
      mockGetUTubInfo.mockResolvedValue(fakeUTub);

      const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(1200);

      const event = new Event("pageshow") as PageTransitionEvent;
      pageshowHandler!(event);

      expect(mockSetUTubEventListenersOnInitialPageLoad).toHaveBeenCalled();
      expect(mockGetUTubInfo).toHaveBeenCalledWith(2);

      await vi.waitFor(() => {
        expect(mockBuildSelectedUTub).toHaveBeenCalledWith(fakeUTub);
      });

      widthSpy.mockRestore();
    });

    it("redirects to error page when search params are invalid (multiple params)", () => {
      Object.defineProperty(history, "state", {
        value: null,
        writable: true,
        configurable: true,
      });
      const assignMock = vi.fn();
      Object.defineProperty(window, "location", {
        value: { search: "?UTubID=1&extra=2", assign: assignMock },
        writable: true,
        configurable: true,
      });

      const event = new Event("pageshow") as PageTransitionEvent;
      pageshowHandler!(event);

      expect(assignMock).toHaveBeenCalledWith("/error");
    });

    it("redirects to error page when UTubID fails isValidUTubID check", () => {
      Object.defineProperty(history, "state", {
        value: null,
        writable: true,
        configurable: true,
      });
      const assignMock = vi.fn();
      Object.defineProperty(window, "location", {
        value: { search: "?UTubID=abc", assign: assignMock },
        writable: true,
        configurable: true,
      });
      mockIsValidUTubID.mockReturnValue(false);

      const event = new Event("pageshow") as PageTransitionEvent;
      pageshowHandler!(event);

      expect(mockIsValidUTubID).toHaveBeenCalledWith("abc");
      expect(assignMock).toHaveBeenCalledWith("/error");
    });

    it("redirects to error page when UTubID fails isUtubIdValidOnPageLoad check", () => {
      Object.defineProperty(history, "state", {
        value: null,
        writable: true,
        configurable: true,
      });
      const assignMock = vi.fn();
      Object.defineProperty(window, "location", {
        value: { search: "?UTubID=42", assign: assignMock },
        writable: true,
        configurable: true,
      });
      mockIsValidUTubID.mockReturnValue(true);
      mockIsUtubIdValidOnPageLoad.mockReturnValue(false);

      const event = new Event("pageshow") as PageTransitionEvent;
      pageshowHandler!(event);

      expect(mockIsUtubIdValidOnPageLoad).toHaveBeenCalledWith("42");
      expect(window.history.replaceState).toHaveBeenCalledWith(
        null,
        "",
        "/home",
      );
      expect(assignMock).toHaveBeenCalledWith("/error");
    });

    it("fetches and builds UTub when search param UTubID is valid", async () => {
      Object.defineProperty(history, "state", {
        value: null,
        writable: true,
        configurable: true,
      });
      Object.defineProperty(window, "location", {
        value: { search: "?UTubID=10", assign: vi.fn() },
        writable: true,
        configurable: true,
      });
      mockIsValidUTubID.mockReturnValue(true);
      mockIsUtubIdValidOnPageLoad.mockReturnValue(true);

      const fakeUTub = { id: 10, name: "URL UTub" };
      mockGetUTubInfo.mockResolvedValue(fakeUTub);

      const widthSpy = vi.spyOn($.fn, "width").mockReturnValue(1200);

      const event = new Event("pageshow") as PageTransitionEvent;
      pageshowHandler!(event);

      await vi.waitFor(() => {
        expect(mockGetUTubInfo).toHaveBeenCalledWith(10);
        expect(mockBuildSelectedUTub).toHaveBeenCalledWith(fakeUTub);
      });

      widthSpy.mockRestore();
    });

    it("no longer rejects ?UTubID=<id>&panel=<x> (both recognized params)", async () => {
      Object.defineProperty(history, "state", {
        value: null,
        writable: true,
        configurable: true,
      });
      const assignMock = vi.fn();
      Object.defineProperty(window, "location", {
        value: { search: "?UTubID=10&panel=urls", assign: assignMock },
        writable: true,
        configurable: true,
      });
      mockIsValidUTubID.mockReturnValue(true);
      mockIsUtubIdValidOnPageLoad.mockReturnValue(true);
      const fakeUTub = { id: 10, name: "URL UTub" };
      mockGetUTubInfo.mockResolvedValue(fakeUTub);

      const event = new Event("pageshow") as PageTransitionEvent;
      pageshowHandler!(event);

      await vi.waitFor(() => {
        expect(mockGetUTubInfo).toHaveBeenCalledWith(10);
        expect(mockBuildSelectedUTub).toHaveBeenCalledWith(fakeUTub);
      });
      // The recognized `panel` param must not trip the malformed-params redirect.
      expect(assignMock).not.toHaveBeenCalledWith("/error");
    });

    it("does not build UTub when getUTubInfo resolves with null/undefined", async () => {
      Object.defineProperty(history, "state", {
        value: { UTubID: 2 },
        writable: true,
        configurable: true,
      });
      mockGetUTubInfo.mockResolvedValue(null);

      const event = new Event("pageshow") as PageTransitionEvent;
      pageshowHandler!(event);

      await vi.waitFor(() => {
        expect(mockGetUTubInfo).toHaveBeenCalledWith(2);
      });

      expect(mockBuildSelectedUTub).not.toHaveBeenCalled();
    });
  });
});
