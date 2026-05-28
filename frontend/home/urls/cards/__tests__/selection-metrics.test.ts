import { setURLCardSelectionEventListener } from "../selection.js";

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

vi.mock("../update-title.js", () => ({
  hideAndResetUpdateURLTitleForm: vi.fn(),
}));
vi.mock("../update-string.js", () => ({
  hideAndResetUpdateURLStringForm: vi.fn(),
}));
vi.mock("../../tags/create.js", () => ({
  hideAndResetCreateURLTagForm: vi.fn(),
}));
vi.mock("../cards.js", () => ({
  setFocusEventListenersOnURLCard: vi.fn(),
}));
vi.mock("../utils.js", () => ({
  enableTabbingOnURLCardElements: vi.fn(),
  disableTabbingOnURLCardElements: vi.fn(),
}));

const $ = window.jQuery;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="42" urlSelected="false" filterable="true">
    <a class="urlString" href="https://example.com">example.com</a>
  </div>
`;

describe("selection metrics — UI_URL_CARD_CLICK", () => {
  beforeEach(() => {
    document.body.innerHTML = URL_CARD_HTML;
    vi.clearAllMocks();
  });

  it("emits ui_url_card_click when an unselected card is clicked", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../url-context.js"
    );
    vi.mocked(isURLSearchActive).mockReturnValue(false);
    vi.mocked(getActiveTagCount).mockReturnValue(0);

    const urlCard = $(".urlRow");
    setURLCardSelectionEventListener(urlCard);
    urlCard.trigger("click");

    expect(emit).toHaveBeenCalledWith("ui_url_card_click", {
      search_active: "false",
      active_tag_count: 0,
    });
  });

  it("does NOT emit when an already-selected card is clicked", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    const urlCard = $(".urlRow");
    urlCard.attr("urlSelected", "true");
    setURLCardSelectionEventListener(urlCard);
    urlCard.trigger("click");

    expect(emit).not.toHaveBeenCalled();
  });

  it("emits with dimensions read at click time (not at listener-bind time)", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../url-context.js"
    );
    vi.mocked(isURLSearchActive).mockReturnValue(false);
    vi.mocked(getActiveTagCount).mockReturnValue(0);

    const urlCard = $(".urlRow");
    setURLCardSelectionEventListener(urlCard);

    // Change the helper return values AFTER listener bind, before click.
    vi.mocked(isURLSearchActive).mockReturnValue(true);
    vi.mocked(getActiveTagCount).mockReturnValue(4);

    urlCard.trigger("click");

    expect(emit).toHaveBeenCalledWith("ui_url_card_click", {
      search_active: "true",
      active_tag_count: 4,
    });
  });
});
