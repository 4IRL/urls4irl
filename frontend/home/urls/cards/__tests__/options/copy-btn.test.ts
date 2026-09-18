import type { UtubUrlItem } from "../../../../../types/url.js";

import { APP_CONFIG } from "../../../../../lib/config.js";
import { createCopyURLBtn } from "../../options/copy-btn.js";
import { copyURLString } from "../../copy.js";

// Shared Tooltip spy instance, copied from access-btn-metrics.test.ts. The
// ambient test-setup Bootstrap mock returns null from getInstance(), which would
// make the instance assertion below untestable.
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

vi.mock("../../copy.js", () => ({
  copyURLString: vi.fn(),
}));

const $ = window.jQuery;

const URL_ITEM = {
  utubUrlID: 1,
  urlString: "https://example.com",
  urlTitle: "Example",
  utubUrlTagIDs: [],
} as unknown as UtubUrlItem;

describe("createCopyURLBtn", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    vi.clearAllMocks();
  });

  it("renders an accessible name and tooltip title from the same COPY_URL_TOOLTIP string", () => {
    const btn = createCopyURLBtn(URL_ITEM);

    expect(btn.hasClass("urlBtnCopy")).toBe(true);
    expect(btn.attr("aria-label")).toBe(APP_CONFIG.strings.COPY_URL_TOOLTIP);
    expect(btn.attr("data-bs-title")).toBe(APP_CONFIG.strings.COPY_URL_TOOLTIP);
    expect(btn.attr("data-bs-custom-class")).toBe("urlBtnCopy-tooltip");
  });

  it("leaves data-bs-trigger unset so Bootstrap's default hover+focus trigger stays intact", () => {
    // test_copy_url_btn_key asserts a FOCUS-triggered tooltip on this button, so
    // an explicit trigger="hover" here would silently break that Playwright test.
    const btn = createCopyURLBtn(URL_ITEM);

    expect(btn.attr("data-bs-trigger")).toBeUndefined();
  });

  it("copies the URL string when clicked", () => {
    const btn = createCopyURLBtn(URL_ITEM);
    $(document.body).append(btn);

    btn.trigger("click");

    expect(vi.mocked(copyURLString)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(copyURLString)).toHaveBeenCalledWith(
      URL_ITEM.urlString,
      btn[0],
    );
  });
});
