import { UI_EVENTS } from "../../../../../types/metrics-events.js";
import type { UtubUrlItem } from "../../../../../types/url.js";

import { createAccessLinkBtn } from "../../options/access-btn.js";
import {
  SEARCH_ACTIVE,
  URL_ACCESS_TRIGGER,
} from "../../../../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../../../lib/globals.js", async () => {
  const jquery = (await import("jquery")).default;
  const tooltipInstance = {
    setContent: vi.fn(),
    show: vi.fn(),
    hide: vi.fn(),
  };
  return {
    $: jquery,
    jQuery: jquery,
    bootstrap: {
      Tooltip: {
        getInstance: vi.fn(() => tooltipInstance),
        getOrCreateInstance: vi.fn(() => tooltipInstance),
      },
    },
  };
});

vi.mock("../../access.js", () => ({
  accessLink: vi.fn(),
}));

vi.mock("../../../url-context.js", () => ({
  isURLSearchActive: vi.fn(() => false),
  getActiveTagCount: vi.fn(() => 0),
}));

const $ = window.jQuery;

function buildUrl(): UtubUrlItem {
  return {
    utubUrlID: 1,
    urlString: "https://example.com",
    urlTitle: "Example",
    utubUrlTagIDs: [],
    canDelete: true,
  };
}

describe("access-btn metrics — UI_URL_ACCESS { trigger: main_button }", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    vi.clearAllMocks();
  });

  it("emits ui_url_access with trigger 'main_button' on click", async () => {
    const { emit } = await import("../../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../../url-context.js"
    );
    vi.mocked(isURLSearchActive).mockReturnValue(false);
    vi.mocked(getActiveTagCount).mockReturnValue(0);

    const btn = createAccessLinkBtn(buildUrl());
    $(document.body).append(btn);
    btn.trigger("click");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_URL_ACCESS,
      trigger: URL_ACCESS_TRIGGER.MAIN_BUTTON,
      search_active: SEARCH_ACTIVE.FALSE,
      active_tag_count: 0,
    });
  });

  it("emits with search_active 'true' and active_tag_count from helpers", async () => {
    const { emit } = await import("../../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../../url-context.js"
    );
    vi.mocked(isURLSearchActive).mockReturnValue(true);
    vi.mocked(getActiveTagCount).mockReturnValue(5);

    const btn = createAccessLinkBtn(buildUrl());
    $(document.body).append(btn);
    btn.trigger("click");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_URL_ACCESS,
      trigger: URL_ACCESS_TRIGGER.MAIN_BUTTON,
      search_active: SEARCH_ACTIVE.TRUE,
      active_tag_count: 5,
    });
  });

  it("calls accessLink with the URL after emitting", async () => {
    const { accessLink } = await import("../../access.js");

    const btn = createAccessLinkBtn(buildUrl());
    $(document.body).append(btn);
    btn.trigger("click");

    expect(accessLink).toHaveBeenCalledWith("https://example.com");
  });
});
