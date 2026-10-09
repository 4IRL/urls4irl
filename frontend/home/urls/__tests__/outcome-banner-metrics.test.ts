import { createMockJqXHRChainable } from "../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../lib/ajax.js";
import {
  showTrimSavedBanner,
  showURLUpdatedBanner,
} from "../outcome-banner.js";
import { UI_EVENTS } from "../../../types/metrics-events.js";
import {
  URL_PARAMS_TRIMMED_ACTION,
  URL_PARAMS_TRIMMED_FORM,
} from "../../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());
vi.mock("../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));
vi.mock("../../utub-locked.js", () => ({
  isUtubLockedHandled: vi.fn(() => false),
}));
vi.mock("../deck.js", () => ({ showURLDeckBannerError: vi.fn() }));
vi.mock("../cards/get.js", () => ({ deleteURLOnStale: vi.fn() }));
vi.mock("../cards/apply-url-string.js", () => ({
  applyUpdatedURLString: vi.fn(),
}));

const $ = window.jQuery;

describe("outcome banner metrics — UI_URL_PARAMS_TRIMMED { action: undo }", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="URLDeck" tabindex="-1">
        <div id="URLDeckOutcomeBanner" class="urlOutcomeBanner hidden" role="status"></div>
        <div class="urlRow" utuburlid="42"><button class="urlStringBtnUpdate">edit</button></div>
      </div>`;
    vi.clearAllMocks();
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable({}));
  });

  it.each([
    [URL_PARAMS_TRIMMED_FORM.URL_CREATE],
    [URL_PARAMS_TRIMMED_FORM.URL_STRING_EDIT],
  ])("emits undo with form '%s' when Undo is clicked", async (form) => {
    const { emit } = await import("../../../lib/metrics-client.js");
    showTrimSavedBanner({
      trimSubmission: {
        originalUrlString: "https://example.com/p?a=1",
        droppedSegments: ["a=1"],
        droppedCount: 1,
      },
      utubID: 3,
      utubUrlID: 42,
      urlCard: $(".urlRow[utuburlid=42]"),
      form,
    });
    expect(emit).not.toHaveBeenCalled();

    $("#URLDeckOutcomeBanner").find(".urlOutcomeBannerAction").trigger("click");

    expect(emit).toHaveBeenCalledTimes(1);
    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_URL_PARAMS_TRIMMED,
      form,
      action: URL_PARAMS_TRIMMED_ACTION.UNDO,
    });
  });
});

describe("outcome banner metrics — UI_URL_EDIT_UNDONE", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div id="URLDeck" tabindex="-1">
        <div id="URLDeckOutcomeBanner" class="urlOutcomeBanner hidden" role="status"></div>
        <div class="urlRow" utuburlid="42"><button class="urlStringBtnUpdate">edit</button></div>
      </div>`;
    vi.clearAllMocks();
    vi.mocked(ajaxCall).mockReturnValue(createMockJqXHRChainable({}));
  });

  it("emits the dedicated event, not the trim one, when Undo is clicked after a plain edit", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");
    showURLUpdatedBanner({
      utubID: 3,
      utubUrlID: 42,
      urlCard: $(".urlRow[utuburlid=42]"),
      previousUrlString: "https://example.com/before",
    });
    expect(emit).not.toHaveBeenCalled();

    $("#URLDeckOutcomeBanner").find(".urlOutcomeBannerAction").trigger("click");

    expect(emit).toHaveBeenCalledTimes(1);
    expect(emit).toHaveBeenCalledWith({ event: UI_EVENTS.UI_URL_EDIT_UNDONE });
  });
});
