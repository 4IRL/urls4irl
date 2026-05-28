import {
  initNavbar,
  onMobileNavbarOpened,
  onMobileNavbarClosed,
} from "../navbar.js";

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

  describe("UI_NAVBAR_MOBILE_MENU_OPEN", () => {
    it("emits ui_navbar_mobile_menu_open when the navbar opens", async () => {
      const { emit } = await import("../../lib/metrics-client.js");

      onMobileNavbarOpened();

      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith("ui_navbar_mobile_menu_open");
    });
  });

  describe("UI_NAVBAR_MOBILE_MENU_CLOSE", () => {
    it("emits ui_navbar_mobile_menu_close on normal close (no suppression)", async () => {
      const { emit } = await import("../../lib/metrics-client.js");

      onMobileNavbarClosed();

      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith("ui_navbar_mobile_menu_close");
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
      expect(emit).toHaveBeenCalledWith("ui_navbar_mobile_menu_close");
    });
  });

  describe("UI_MOBILE_NAV", () => {
    it("emits ui_mobile_nav with target=members on #toMembers click", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initNavbar();

      $("button#toMembers").trigger("click");

      expect(emit).toHaveBeenCalledWith("ui_mobile_nav", { target: "members" });
    });

    it("emits ui_mobile_nav with target=urls on #toURLs click", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initNavbar();

      $("button#toURLs").trigger("click");

      expect(emit).toHaveBeenCalledWith("ui_mobile_nav", { target: "urls" });
    });

    it("emits ui_mobile_nav with target=utubs on #toUTubs click", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initNavbar();

      $("button#toUTubs").trigger("click");

      expect(emit).toHaveBeenCalledWith("ui_mobile_nav", { target: "utubs" });
    });

    it("emits ui_mobile_nav with target=tags on #toTags click", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initNavbar();

      $("button#toTags").trigger("click");

      expect(emit).toHaveBeenCalledWith("ui_mobile_nav", { target: "tags" });
    });

    it("a section button click emits ui_mobile_nav once and the subsequent navbar-hide does NOT emit ui_navbar_mobile_menu_close", async () => {
      const { emit } = await import("../../lib/metrics-client.js");
      initNavbar();

      $("button#toTags").trigger("click");
      onMobileNavbarClosed();

      const calls = (emit as ReturnType<typeof vi.fn>).mock.calls;
      const mobileNavCalls = calls.filter(
        (call) => call[0] === "ui_mobile_nav",
      );
      const closeCalls = calls.filter(
        (call) => call[0] === "ui_navbar_mobile_menu_close",
      );
      expect(mobileNavCalls).toHaveLength(1);
      expect(mobileNavCalls[0]).toEqual(["ui_mobile_nav", { target: "tags" }]);
      expect(closeCalls).toHaveLength(0);
    });
  });
});
