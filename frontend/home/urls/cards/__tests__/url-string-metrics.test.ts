import { createURLString } from "../url-string.js";

vi.mock("../../../../lib/metrics-client.js", () => ({
  emit: vi.fn(),
  flush: vi.fn().mockResolvedValue(undefined),
  initMetricsClient: vi.fn(),
  resetMetricsClient: vi.fn(),
}));

vi.mock("../access.js", () => ({
  accessLink: vi.fn(),
}));

vi.mock("../../url-context.js", () => ({
  isURLSearchActive: vi.fn(() => false),
  getActiveTagCount: vi.fn(() => 0),
}));

const $ = window.jQuery;

describe("url-string metrics — UI_URL_ACCESS { trigger: url_text }", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    vi.clearAllMocks();
  });

  it("emits ui_url_access when the URL anchor is clicked on a selected card", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../url-context.js"
    );
    vi.mocked(isURLSearchActive).mockReturnValue(false);
    vi.mocked(getActiveTagCount).mockReturnValue(0);

    const urlAnchor = createURLString("https://example.com");
    const urlRow = $('<div class="urlRow" urlSelected="true"></div>').append(
      urlAnchor,
    );
    $(document.body).append(urlRow);

    urlAnchor.trigger("click.defaultlinkbehavior");

    expect(emit).toHaveBeenCalledWith("ui_url_access", {
      trigger: "url_text",
      search_active: "false",
      active_tag_count: 0,
    });
  });

  it("does NOT emit when the URL anchor is clicked on a NOT selected card", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    const urlAnchor = createURLString("https://example.com");
    const urlRow = $('<div class="urlRow" urlSelected="false"></div>').append(
      urlAnchor,
    );
    $(document.body).append(urlRow);

    urlAnchor.trigger("click.defaultlinkbehavior");

    expect(emit).not.toHaveBeenCalled();
  });

  it("passes search_active 'true' and active_tag_count from helpers on click", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../url-context.js"
    );
    vi.mocked(isURLSearchActive).mockReturnValue(true);
    vi.mocked(getActiveTagCount).mockReturnValue(3);

    const urlAnchor = createURLString("https://example.com");
    const urlRow = $('<div class="urlRow" urlSelected="true"></div>').append(
      urlAnchor,
    );
    $(document.body).append(urlRow);

    urlAnchor.trigger("click.defaultlinkbehavior");

    expect(emit).toHaveBeenCalledWith("ui_url_access", {
      trigger: "url_text",
      search_active: "true",
      active_tag_count: 3,
    });
  });
});
