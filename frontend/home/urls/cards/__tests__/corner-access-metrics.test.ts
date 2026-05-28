import { createGoToURLIcon } from "../corner-access.js";

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

describe("corner-access metrics — UI_URL_ACCESS { trigger: corner_button }", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    vi.clearAllMocks();
  });

  it("emits ui_url_access with trigger 'corner_button' on click", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../url-context.js"
    );
    vi.mocked(isURLSearchActive).mockReturnValue(false);
    vi.mocked(getActiveTagCount).mockReturnValue(0);

    const btn = createGoToURLIcon("https://example.com");
    $(document.body).append(btn);
    btn.trigger("click");

    expect(emit).toHaveBeenCalledWith("ui_url_access", {
      trigger: "corner_button",
      search_active: "false",
      active_tag_count: 0,
    });
  });

  it("emits search_active 'true' when URL search panel is open", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../url-context.js"
    );
    vi.mocked(isURLSearchActive).mockReturnValue(true);
    vi.mocked(getActiveTagCount).mockReturnValue(2);

    const btn = createGoToURLIcon("https://example.com");
    $(document.body).append(btn);
    btn.trigger("click");

    expect(emit).toHaveBeenCalledWith("ui_url_access", {
      trigger: "corner_button",
      search_active: "true",
      active_tag_count: 2,
    });
  });

  it("calls accessLink with the URL string after emitting", async () => {
    const { accessLink } = await import("../access.js");

    const btn = createGoToURLIcon("https://example.com");
    $(document.body).append(btn);
    btn.trigger("click");

    expect(accessLink).toHaveBeenCalledWith("https://example.com");
  });
});
