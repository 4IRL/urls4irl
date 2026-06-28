import { UI_EVENTS } from "../../types/metrics-events.js";
import { LHS_COLLAPSE_SOURCE } from "../../types/metrics-dim-values.js";
import {
  initLeftPanelToggle,
  setUserCollapsedLHS,
  setSearchModeActive,
} from "../left-panel-toggle.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../mobile.js", () => ({ isMobile: vi.fn(() => false) }));
vi.mock("../utubs/search.js", () => ({ closeUTubNameFilter: vi.fn() }));
vi.mock("../tags/search.js", () => ({ closeTagNameFilter: vi.fn() }));

const $ = window.jQuery;

const PANEL_HTML = `
  <main id="mainPanel">
    <div id="leftPanel" class="panel"></div>
    <button id="lhsToggleSeam" aria-expanded="true" aria-controls="leftPanel">
      <svg class="bi"></svg>
    </button>
    <div id="centerPanel" class="panel"></div>
    <button id="lhsToggleHeader" aria-expanded="true" aria-controls="leftPanel"></button>
  </main>
`;

describe("Left Panel Toggle", () => {
  beforeEach(async () => {
    document.body.innerHTML = PANEL_HTML;
    const { isMobile } = await import("../mobile.js");
    (isMobile as ReturnType<typeof vi.fn>).mockReturnValue(false);
    // Reset module-scoped intent state between tests, then clear the metric
    // calls those resets produced.
    setUserCollapsedLHS({ collapsed: false, source: LHS_COLLAPSE_SOURCE.SEAM });
    setSearchModeActive({ active: false });
    vi.clearAllMocks();
    initLeftPanelToggle();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  describe("seam toggle", () => {
    it("clicking #lhsToggleSeam collapses the LHS and sets aria-expanded=false on both buttons", () => {
      $("#lhsToggleSeam").trigger("click");

      expect($("#mainPanel").hasClass("lhs-collapsed")).toBe(true);
      expect($("#lhsToggleSeam").attr("aria-expanded")).toBe("false");
      expect($("#lhsToggleHeader").attr("aria-expanded")).toBe("false");
    });

    it("clicking #lhsToggleSeam again expands the LHS and sets aria-expanded=true", () => {
      $("#lhsToggleSeam").trigger("click");
      $("#lhsToggleSeam").trigger("click");

      expect($("#mainPanel").hasClass("lhs-collapsed")).toBe(false);
      expect($("#lhsToggleSeam").attr("aria-expanded")).toBe("true");
      expect($("#lhsToggleHeader").attr("aria-expanded")).toBe("true");
    });

    it("rotates the seam chevron via .lhs-chevron--closed in lockstep with collapse", () => {
      $("#lhsToggleSeam").trigger("click");
      expect($("#lhsToggleSeam .bi").hasClass("lhs-chevron--closed")).toBe(
        true,
      );
      $("#lhsToggleSeam").trigger("click");
      expect($("#lhsToggleSeam .bi").hasClass("lhs-chevron--closed")).toBe(
        false,
      );
    });
  });

  describe("header toggle", () => {
    it("clicking #lhsToggleHeader toggles identically via the shared resolver", () => {
      $("#lhsToggleHeader").trigger("click");
      expect($("#mainPanel").hasClass("lhs-collapsed")).toBe(true);
      expect($("#lhsToggleSeam").attr("aria-expanded")).toBe("false");
      expect($("#lhsToggleHeader").attr("aria-expanded")).toBe("false");

      $("#lhsToggleHeader").trigger("click");
      expect($("#mainPanel").hasClass("lhs-collapsed")).toBe(false);
    });
  });

  describe("resolver honoring", () => {
    it("manual collapse survives a search-mode open/close cycle", () => {
      setUserCollapsedLHS({
        collapsed: true,
        source: LHS_COLLAPSE_SOURCE.SEAM,
      });
      expect($("#mainPanel").hasClass("lhs-collapsed")).toBe(true);

      setSearchModeActive({ active: true });
      setSearchModeActive({ active: false });

      expect($("#mainPanel").hasClass("lhs-collapsed")).toBe(true);
    });

    it("expanded state survives a search-mode open/close cycle", () => {
      setUserCollapsedLHS({
        collapsed: false,
        source: LHS_COLLAPSE_SOURCE.SEAM,
      });
      expect($("#mainPanel").hasClass("lhs-collapsed")).toBe(false);

      setSearchModeActive({ active: true });
      setSearchModeActive({ active: false });

      expect($("#mainPanel").hasClass("lhs-collapsed")).toBe(false);
    });

    it("setSearchModeActive emits no metric — search mode owns its own metric", async () => {
      const { emit } = await import("../../lib/metrics-client.js");

      setSearchModeActive({ active: true });
      setSearchModeActive({ active: false });

      expect(emit).not.toHaveBeenCalled();
    });
  });

  describe("filter close on collapse", () => {
    it("collapsing the LHS closes the UTub name filter", async () => {
      const { closeUTubNameFilter } = await import("../utubs/search.js");

      setUserCollapsedLHS({
        collapsed: true,
        source: LHS_COLLAPSE_SOURCE.SEAM,
      });

      expect(closeUTubNameFilter).toHaveBeenCalledTimes(1);
    });

    it("collapsing the LHS closes the tag name filter", async () => {
      const { closeTagNameFilter } = await import("../tags/search.js");

      setUserCollapsedLHS({
        collapsed: true,
        source: LHS_COLLAPSE_SOURCE.SEAM,
      });

      expect(closeTagNameFilter).toHaveBeenCalledTimes(1);
    });

    it("expanding the LHS does not close the tag name filter", async () => {
      const { closeTagNameFilter } = await import("../tags/search.js");

      setUserCollapsedLHS({
        collapsed: false,
        source: LHS_COLLAPSE_SOURCE.SEAM,
      });

      expect(closeTagNameFilter).not.toHaveBeenCalled();
    });
  });

  describe("mobile guard", () => {
    it("clicking the toggle is a no-op on mobile (no class change)", async () => {
      const { isMobile } = await import("../mobile.js");
      (isMobile as ReturnType<typeof vi.fn>).mockReturnValue(true);

      $("#lhsToggleSeam").trigger("click");

      expect($("#mainPanel").hasClass("lhs-collapsed")).toBe(false);
    });
  });

  describe("setSearchModeActive viewport branching", () => {
    it("on mobile, activating search adds .hidden to #leftPanel and deactivating removes it", async () => {
      const { isMobile } = await import("../mobile.js");
      (isMobile as ReturnType<typeof vi.fn>).mockReturnValue(true);

      setSearchModeActive({ active: true });
      expect($("#leftPanel").hasClass("hidden")).toBe(true);

      setSearchModeActive({ active: false });
      expect($("#leftPanel").hasClass("hidden")).toBe(false);
    });

    it("on desktop, activating search does not add .hidden to #leftPanel", async () => {
      const { isMobile } = await import("../mobile.js");
      (isMobile as ReturnType<typeof vi.fn>).mockReturnValue(false);

      setSearchModeActive({ active: true });
      expect($("#leftPanel").hasClass("hidden")).toBe(false);
    });
  });

  describe("metrics emission", () => {
    it("seam collapse emits UI_LHS_COLLAPSE with source=seam; expand emits UI_LHS_EXPAND", async () => {
      const { emit } = await import("../../lib/metrics-client.js");

      $("#lhsToggleSeam").trigger("click");
      expect(emit).toHaveBeenNthCalledWith(1, {
        event: UI_EVENTS.UI_LHS_COLLAPSE,
        source: LHS_COLLAPSE_SOURCE.SEAM,
      });

      $("#lhsToggleSeam").trigger("click");
      expect(emit).toHaveBeenNthCalledWith(2, {
        event: UI_EVENTS.UI_LHS_EXPAND,
        source: LHS_COLLAPSE_SOURCE.SEAM,
      });
    });

    it("header collapse emits UI_LHS_COLLAPSE with source=url_header", async () => {
      const { emit } = await import("../../lib/metrics-client.js");

      $("#lhsToggleHeader").trigger("click");

      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_LHS_COLLAPSE,
        source: LHS_COLLAPSE_SOURCE.URL_HEADER,
      });
    });
  });
});
