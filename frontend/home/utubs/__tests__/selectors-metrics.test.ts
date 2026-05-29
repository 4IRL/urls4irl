import { UI_EVENTS } from "../../../lib/metrics-events.js";
import { makeUTubSelectableAgainIfMobile, selectUTub } from "../selectors.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../deck.js", () => ({
  showUTubLoadingIconAndSetTimeout: vi.fn(() => 0),
  hideUTubLoadingIconAndClearTimeout: vi.fn(),
  setUTubDeckOnUTubSelected: vi.fn(),
}));

vi.mock("../../urls/update-description.js", () => ({
  removeEventListenersForShowCreateUTubDescIfEmptyDesc: vi.fn(),
  showCreateDescriptionButtonAlways: vi.fn(),
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

const $ = window.jQuery;

const SELECTORS_HTML = `
  <input id="UTubNameSearch" value="" />
  <div id="listUTubs">
    <span class="UTubSelector" utubid="1" position="1"></span>
    <span class="UTubSelector" utubid="2" position="2"></span>
  </div>
`;

describe("selectors metrics — UI_UTUB_SELECT", () => {
  beforeEach(() => {
    document.body.innerHTML = SELECTORS_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  describe("selectUTub", () => {
    it("emits ui_utub_select with search_active 'false' when search input is empty", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");
      $("#UTubNameSearch").val("");

      const utubSelector = $(".UTubSelector[utubid='1']");
      selectUTub(1, utubSelector);

      expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_UTUB_SELECT, {
        search_active: "false",
      });
    });

    it("emits ui_utub_select with search_active 'true' when search input has content", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");
      $("#UTubNameSearch").val("foo");

      const utubSelector = $(".UTubSelector[utubid='1']");
      selectUTub(1, utubSelector);

      expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_UTUB_SELECT, {
        search_active: "true",
      });
    });

    it("does not emit when re-selecting the currently active UTub", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");
      const utubSelector = $(".UTubSelector[utubid='1']");
      utubSelector.addClass("active");

      selectUTub(1, utubSelector);

      expect(emit).not.toHaveBeenCalled();
    });
  });

  describe("makeUTubSelectableAgainIfMobile", () => {
    it("emits ui_utub_select with search_active 'false' on first click", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");
      $("#UTubNameSearch").val("");
      const utubElement = $(".UTubSelector[utubid='1']");

      makeUTubSelectableAgainIfMobile(utubElement);
      utubElement.trigger("click.selectUTubMobile");

      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_UTUB_SELECT, {
        search_active: "false",
      });
    });

    it("emits ui_utub_select with search_active 'true' when search input is active", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");
      $("#UTubNameSearch").val("alpha");
      const utubElement = $(".UTubSelector[utubid='1']");

      makeUTubSelectableAgainIfMobile(utubElement);
      utubElement.trigger("click.selectUTubMobile");

      expect(emit).toHaveBeenCalledTimes(1);
      expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_UTUB_SELECT, {
        search_active: "true",
      });
    });

    it("does not emit on a second click after first click self-removes the listener", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");
      const utubElement = $(".UTubSelector[utubid='1']");

      makeUTubSelectableAgainIfMobile(utubElement);
      utubElement.trigger("click.selectUTubMobile");
      utubElement.trigger("click.selectUTubMobile");

      expect(emit).toHaveBeenCalledTimes(1);
    });
  });
});
