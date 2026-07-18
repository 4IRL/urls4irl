import {
  initNavbar,
  onMobileNavbarOpened,
  onMobileNavbarClosed,
  NAVBAR_TOGGLER,
} from "../navbar.js";
import {
  exitCrossUtubSearchMode,
  isCrossUtubSearchActive,
} from "../search/cross-utub-search.js";
import { openTagSheetFromUserAction } from "../tags/sheet.js";
import {
  setMobileUIWhenUTubSelectedOrURLNavSelected,
  pushMobilePanelHistoryState,
  setCurrentMobilePanel,
} from "../mobile.js";
import { getState } from "../../store/app-store.js";
import { CROSS_UTUB_SEARCH_CLOSE_TRIGGER } from "../../types/metrics-dim-values.js";

vi.mock("../../lib/globals.js", () => ({
  $: window.jQuery,
  bootstrap: window.bootstrap,
}));
vi.mock("../../lib/navbar-shared.js", () => ({
  initNavbarRouting: vi.fn(),
}));
vi.mock("../mobile.js", () => ({
  setMobileUIWhenMemberDeckSelected: vi.fn(),
  setMobileUIWhenUTubSelectedOrURLNavSelected: vi.fn(),
  setMobileUIWhenUTubDeckSelected: vi.fn(),
  pushMobilePanelHistoryState: vi.fn(),
  setCurrentMobilePanel: vi.fn(),
}));
vi.mock("../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ activeUTubID: 5 })),
}));
vi.mock("../tags/sheet.js", () => ({
  openTagSheetFromUserAction: vi.fn(),
}));
// navbar.ts imports the cross-search module to close search on deck-nav and the
// Return Home item; mock it so the real (heavy) module doesn't load here.
vi.mock("../search/cross-utub-search.js", () => ({
  isCrossUtubSearchActive: vi.fn(() => false),
  exitCrossUtubSearchMode: vi.fn(),
}));

const $ = window.jQuery;

const NAVBAR_HTML = `
  <nav id="mainNavbar">
    <a class="navbar-brand" href="#">Brand</a>
    <button class="navbar-toggler"></button>
    <div id="NavbarNavDropdown"></div>
    <span id="MobilePanelAnnouncement"></span>
  </nav>
  <button id="toMembers"></button>
  <button id="toURLs"></button>
  <button id="toUTubs"></button>
  <button id="toTags"></button>
  <button id="navReturnHome" class="hidden"></button>
`;

describe("navbar", () => {
  beforeEach(() => {
    document.body.innerHTML = NAVBAR_HTML;
    vi.clearAllMocks();
    window.history.replaceState(null, "", "/");
    (
      isCrossUtubSearchActive as unknown as ReturnType<typeof vi.fn>
    ).mockReturnValue(false);
    (getState as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
      activeUTubID: 5,
    });
  });

  describe("initNavbar", () => {
    it("initializes NAVBAR_TOGGLER and binds click handlers on nav buttons", () => {
      initNavbar();

      expect(NAVBAR_TOGGLER.toggler).toBeDefined();
      expect(NAVBAR_TOGGLER.toggler).not.toBeNull();
    });

    it("clicking Return Home closes cross-UTub search and hides the dropdown", () => {
      initNavbar();
      const hideSpy = vi.spyOn(NAVBAR_TOGGLER.toggler!, "hide");

      $("button#navReturnHome").trigger("click");

      expect(exitCrossUtubSearchMode).toHaveBeenCalledWith({
        trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.RETURN_HOME,
      });
      expect(hideSpy).toHaveBeenCalledTimes(1);
    });

    it("a deck-switcher closes cross-UTub search only when it is open", () => {
      initNavbar();

      // Not open: deck-switcher click does not close search.
      $("button#toUTubs").trigger("click");
      expect(exitCrossUtubSearchMode).not.toHaveBeenCalled();

      // Open: deck-switcher click closes search with the deck_switch trigger.
      (
        isCrossUtubSearchActive as unknown as ReturnType<typeof vi.fn>
      ).mockReturnValue(true);
      $("button#toTags").trigger("click");
      expect(exitCrossUtubSearchMode).toHaveBeenCalledWith({
        trigger: CROSS_UTUB_SEARCH_CLOSE_TRIGGER.DECK_SWITCH,
      });
    });

    it("clicking #toTags switches to the URL deck, then opens the tag sheet over it", () => {
      initNavbar();

      $("button#toTags").trigger("click");

      // The sheet overlays the URL deck, so the deck switch must run first
      // (it also collapses the hamburger), then the sheet opens.
      expect(setMobileUIWhenUTubSelectedOrURLNavSelected).toHaveBeenCalled();
      expect(openTagSheetFromUserAction).toHaveBeenCalled();
      const switchOrder = (
        setMobileUIWhenUTubSelectedOrURLNavSelected as unknown as ReturnType<
          typeof vi.fn
        >
      ).mock.invocationCallOrder[0];
      const openOrder = (
        openTagSheetFromUserAction as unknown as ReturnType<typeof vi.fn>
      ).mock.invocationCallOrder[0];
      expect(switchOrder).toBeLessThan(openOrder);
    });

    it("pushes the matching { UTubID, mobilePanel } entry for each deck-switch tap", () => {
      initNavbar();

      $("button#toUTubs").trigger("click");
      expect(pushMobilePanelHistoryState).toHaveBeenCalledWith({
        mobilePanel: "utubs",
        UTubID: 5,
      });
      expect(setCurrentMobilePanel).toHaveBeenCalledWith({
        mobilePanel: "utubs",
      });

      $("button#toURLs").trigger("click");
      expect(pushMobilePanelHistoryState).toHaveBeenCalledWith({
        mobilePanel: "urls",
        UTubID: 5,
      });

      $("button#toMembers").trigger("click");
      expect(pushMobilePanelHistoryState).toHaveBeenCalledWith({
        mobilePanel: "members",
        UTubID: 5,
      });

      // Tap-driven switches are visually obvious — they never touch the
      // screen-reader announcement region (that is history-nav only).
      expect($("#MobilePanelAnnouncement").text()).toBe("");
    });

    it("does not push a panel entry when no UTub is active", () => {
      (getState as unknown as ReturnType<typeof vi.fn>).mockReturnValue({
        activeUTubID: null,
      });
      initNavbar();

      $("button#toMembers").trigger("click");

      expect(pushMobilePanelHistoryState).not.toHaveBeenCalled();
      expect(setCurrentMobilePanel).not.toHaveBeenCalled();
    });

    it("dedup guard suppresses a push when the current entry already matches", () => {
      window.history.replaceState({ UTubID: 5, mobilePanel: "utubs" }, "", "/");
      initNavbar();

      $("button#toUTubs").trigger("click");

      // Redundant re-tap of the already-current panel — no duplicate entry.
      expect(pushMobilePanelHistoryState).not.toHaveBeenCalled();
      // The tracked panel is still (re)set even when the push is deduped.
      expect(setCurrentMobilePanel).toHaveBeenCalledWith({
        mobilePanel: "utubs",
      });
    });

    it("registers collapse event listeners on NavbarNavDropdown", () => {
      const onSpy = vi.spyOn($.fn, "on");

      initNavbar();

      const showCall = onSpy.mock.calls.find(
        (call) => (call[0] as unknown as string) === "show.bs.collapse",
      );
      const hideCall = onSpy.mock.calls.find(
        (call) => (call[0] as unknown as string) === "hide.bs.collapse",
      );
      expect(showCall).toBeDefined();
      expect(hideCall).toBeDefined();

      onSpy.mockRestore();
    });
  });

  describe("onMobileNavbarOpened", () => {
    it("adds backdrop element and z9999 classes", () => {
      onMobileNavbarOpened();

      expect($(".navbar-backdrop").length).toBe(1);
      expect($(".navbar-brand").hasClass("z9999")).toBe(true);
      expect($(".navbar-toggler").hasClass("z9999")).toBe(true);
      expect($("#NavbarNavDropdown").hasClass("z9999")).toBe(true);
    });

    it("appends backdrop to mainNavbar", () => {
      onMobileNavbarOpened();

      const backdrop = $("#mainNavbar .navbar-backdrop");
      expect(backdrop.length).toBe(1);
    });
  });

  describe("onMobileNavbarClosed", () => {
    it("adds fade class to backdrop and removes z9999 classes", () => {
      // First open to create backdrop
      onMobileNavbarOpened();
      expect($(".navbar-backdrop").length).toBe(1);

      onMobileNavbarClosed();

      expect($(".navbar-backdrop").hasClass("navbar-backdrop-fade")).toBe(true);
      expect($(".navbar-brand").hasClass("z9999")).toBe(false);
      expect($(".navbar-toggler").hasClass("z9999")).toBe(false);
      expect($("#NavbarNavDropdown").hasClass("z9999")).toBe(false);
    });

    it("is a no-op when no backdrop exists", () => {
      onMobileNavbarClosed();

      expect($(".navbar-brand").hasClass("z9999")).toBe(false);
    });
  });
});
