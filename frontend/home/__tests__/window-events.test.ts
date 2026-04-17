import { initWindowEvents } from "../window-events.js";

const mockResetHomePageToInitialState = vi.fn();
const mockSetUIWhenNoUTubSelected = vi.fn();
const mockSetMobileUIWhenUTubSelectedOrURLNavSelected = vi.fn();
const mockSetUTubEventListenersOnInitialPageLoad = vi.fn();
const mockSetCreateUTubEventListeners = vi.fn();
const mockGetUTubInfo = vi.fn();
const mockBuildSelectedUTub = vi.fn();
const mockIsValidUTubID = vi.fn();
const mockIsUtubIdValidOnPageLoad = vi.fn();
const mockIsUtubIdValidFromStateAccess = vi.fn();
const mockSetMemberDeckWhenNoUTubSelected = vi.fn();
const mockSetTagDeckSubheaderWhenNoUTubSelected = vi.fn();

vi.mock("../../lib/config.js", () => ({
  APP_CONFIG: {
    routes: { errorPage: "/error" },
    strings: { UTUB_QUERY_PARAM: "UTubID" },
  },
}));
vi.mock("../../lib/constants.js", () => ({
  TABLET_WIDTH: 992,
}));
vi.mock("../mobile.js", () => ({
  setMobileUIWhenUTubSelectedOrURLNavSelected: (...args: unknown[]) =>
    mockSetMobileUIWhenUTubSelectedOrURLNavSelected(...args),
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

const $ = window.jQuery;

describe("window-events", () => {
  let addEventListenerSpy: ReturnType<typeof vi.spyOn>;
  let popstateHandler: ((event: PopStateEvent) => void) | undefined;
  let pageshowHandler: ((event: PageTransitionEvent) => void) | undefined;

  beforeEach(() => {
    vi.clearAllMocks();
    popstateHandler = undefined;
    pageshowHandler = undefined;

    addEventListenerSpy = vi
      .spyOn(window, "addEventListener")
      .mockImplementation((type: string, listener: EventListener) => {
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
