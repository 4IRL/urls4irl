import { UI_EVENTS } from "../../types/metrics-events.js";
import {
  initNavbar,
  onMobileNavbarOpened,
  onMobileNavbarClosed,
} from "../navbar.js";
import { MOBILE_NAV_TARGET } from "../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../lib/metrics-client.js", () => mockMetricsClient());

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
  setMobileUIWhenTagDeckSelected: vi.fn(),
}));
// navbar.ts imports the cross-search module; mock it so the real module (and its
// heavy transitive imports) don't load into this metrics-focused suite.
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
`;

describe("navbar metrics emitters", () => {
  beforeEach(() => {
    document.body.innerHTML = NAVBAR_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  describe("UI_NAVBAR_DROPDOWN_OPEN", () => {
    it("emits ui_navbar_dropdown_open when the navbar opens", async () => {
      const { emit } = await import("../../lib/metrics-client.js");

      onMobileNavbarOpened();

      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_NAVBAR_DROPDOWN_OPEN,
      });
    });
  });

  describe("UI_NAVBAR_DROPDOWN_CLOSE", () => {
    it("emits ui_navbar_dropdown_close on normal close (no suppression)", async () => {
      const { emit } = await import("../../lib/metrics-client.js");

      onMobileNavbarClosed();

      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_NAVBAR_DROPDOWN_CLOSE,
      });
    });

    it("suppresses the next close emit when a section button was clicked first", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initNavbar();

      $("button#toMembers").trigger("click");
      (emit as ReturnType<typeof vi.fn>).mockClear();

      onMobileNavbarClosed();

      expect(emit).not.toHaveBeenCalled();
    });

    it("resets the suppression flag after one suppressed close", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initNavbar();

      $("button#toMembers").trigger("click");
      onMobileNavbarClosed();
      (emit as ReturnType<typeof vi.fn>).mockClear();

      onMobileNavbarClosed();

      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_NAVBAR_DROPDOWN_CLOSE,
      });
    });
  });

  describe("UI_MOBILE_NAV", () => {
    it("emits ui_mobile_nav with target=members on #toMembers click", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initNavbar();

      $("button#toMembers").trigger("click");

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MOBILE_NAV,
        target: MOBILE_NAV_TARGET.MEMBERS,
      });
    });

    it("emits ui_mobile_nav with target=urls on #toURLs click", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initNavbar();

      $("button#toURLs").trigger("click");

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MOBILE_NAV,
        target: MOBILE_NAV_TARGET.URLS,
      });
    });

    it("emits ui_mobile_nav with target=utubs on #toUTubs click", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initNavbar();

      $("button#toUTubs").trigger("click");

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MOBILE_NAV,
        target: MOBILE_NAV_TARGET.UTUBS,
      });
    });

    it("emits ui_mobile_nav with target=tags on #toTags click", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initNavbar();

      $("button#toTags").trigger("click");

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_MOBILE_NAV,
        target: MOBILE_NAV_TARGET.TAGS,
      });
    });

    it("a section button click emits ui_mobile_nav once and the subsequent navbar-hide does NOT emit ui_navbar_dropdown_close", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initNavbar();

      $("button#toTags").trigger("click");
      onMobileNavbarClosed();

      const calls = (emit as ReturnType<typeof vi.fn>).mock.calls;
      const mobileNavCalls = calls.filter(
        (call) =>
          (call[0] as { event?: string }).event === UI_EVENTS.UI_MOBILE_NAV,
      );
      const closeCalls = calls.filter(
        (call) =>
          (call[0] as { event?: string }).event ===
          UI_EVENTS.UI_NAVBAR_DROPDOWN_CLOSE,
      );
      expect(mobileNavCalls).toHaveLength(1);
      expect(mobileNavCalls[0]).toEqual([
        { event: UI_EVENTS.UI_MOBILE_NAV, target: MOBILE_NAV_TARGET.TAGS },
      ]);
      expect(closeCalls).toHaveLength(0);
    });
  });
});
