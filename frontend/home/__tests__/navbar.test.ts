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
import { openTagSheet } from "../tags/sheet.js";
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
}));
vi.mock("../tags/sheet.js", () => ({
  openTagSheet: vi.fn(),
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
    (
      isCrossUtubSearchActive as unknown as ReturnType<typeof vi.fn>
    ).mockReturnValue(false);
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

    it("clicking #toTags opens the tag sheet", () => {
      initNavbar();
      $("button#toTags").trigger("click");
      expect(openTagSheet).toHaveBeenCalled();
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
