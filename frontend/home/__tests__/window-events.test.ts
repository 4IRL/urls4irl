import {
  CROSS_UTUB_SEARCH_CLOSE_TRIGGER,
  MOBILE_NAV_TRIGGER,
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
