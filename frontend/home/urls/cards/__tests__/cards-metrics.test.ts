import { setFocusEventListenersOnURLCard } from "../cards.js";

vi.mock("../../../../lib/metrics-client.js", () => ({
  emit: vi.fn(),
  flush: vi.fn().mockResolvedValue(undefined),
  initMetricsClient: vi.fn(),
  resetMetricsClient: vi.fn(),
}));

vi.mock("../../url-context.js", () => ({
  isURLSearchActive: vi.fn(() => false),
  getActiveTagCount: vi.fn(() => 0),
}));

vi.mock("../selection.js", () => ({
  selectURLCard: vi.fn(),
  setURLCardSelectionEventListener: vi.fn(),
}));

const $ = window.jQuery;

describe("cards metrics — UI_URL_CARD_CLICK (Enter key branch)", () => {
  beforeEach(() => {
    document.body.innerHTML = `
      <div class="urlRow" utuburlid="7" urlSelected="false" tabindex="0"></div>
    `;
    vi.clearAllMocks();
  });

  afterEach(() => {
    $(document).off("keyup.focusURLCard7");
  });

  it("emits ui_url_card_click on Enter key when card is focused", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../url-context.js"
    );
    vi.mocked(isURLSearchActive).mockReturnValue(false);
    vi.mocked(getActiveTagCount).mockReturnValue(0);

    const urlCard = $(".urlRow");
    setFocusEventListenersOnURLCard(urlCard);
    urlCard.trigger("focus.focusURLCard7");

    const enterEvent = $.Event("keyup.focusURLCard7", { key: "Enter" });
    $(document).trigger(enterEvent);

    expect(emit).toHaveBeenCalledWith("ui_url_card_click", {
      search_active: "false",
      active_tag_count: 0,
    });
  });

  it("does NOT emit on non-Enter keyup", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    const urlCard = $(".urlRow");
    setFocusEventListenersOnURLCard(urlCard);
    urlCard.trigger("focus.focusURLCard7");

    const tabEvent = $.Event("keyup.focusURLCard7", { key: "Tab" });
    $(document).trigger(tabEvent);

    expect(emit).not.toHaveBeenCalled();
  });

  it("emits with dimensions read at keypress time", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../url-context.js"
    );

    const urlCard = $(".urlRow");
    setFocusEventListenersOnURLCard(urlCard);
    urlCard.trigger("focus.focusURLCard7");

    vi.mocked(isURLSearchActive).mockReturnValue(true);
    vi.mocked(getActiveTagCount).mockReturnValue(2);

    const enterEvent = $.Event("keyup.focusURLCard7", { key: "Enter" });
    $(document).trigger(enterEvent);

    expect(emit).toHaveBeenCalledWith("ui_url_card_click", {
      search_active: "true",
      active_tag_count: 2,
    });
  });
});
