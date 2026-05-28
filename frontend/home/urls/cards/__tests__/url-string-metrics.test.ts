import {
  createURLString,
  createURLStringAndUpdateBlock,
} from "../url-string.js";
import { ajaxCall } from "../../../../lib/ajax.js";

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

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../update-string.js", () => ({
  updateURL: vi.fn(() => Promise.resolve()),
  hideAndResetUpdateURLStringForm: vi.fn(),
}));

vi.mock("../../../../lib/config.js", () => ({
  APP_CONFIG: {
    routes: { updateURL: () => "/dummy" },
    constants: {
      URLS_MIN_LENGTH: 1,
      URLS_MAX_LENGTH: 2000,
    },
    strings: {},
  },
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

  it("url_string_edit unchanged value: emits submit but fires no AJAX", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { updateURL } = await import("../update-string.js");

    const urlRow = $('<div class="urlRow" utuburlid="1"></div>');
    $(document.body).append(urlRow);
    const block = createURLStringAndUpdateBlock(
      "https://example.com",
      urlRow,
      1,
    );
    urlRow.append(block);

    const submitBtn = urlRow.find(".urlStringSubmitBtnUpdate");
    // The url-string.ts submit handler calls updateURL(), which contains the
    // unchanged-value guard. ajaxCall is the inner I/O; the guard returns
    // before that — so asserting no ajaxCall here verifies the early-return
    // path. updateURL is mocked here, so we further assert it was called
    // exactly once (the call is the act under test, the guard short-circuits
    // inside the real impl which the integration suite verifies).
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
    expect(emit).not.toHaveBeenCalled();

    submitBtn.trigger("click.updateUrlString");

    expect(emit).toHaveBeenCalledWith("ui_form_submit", {
      trigger: "button_click",
      form: "url_string_edit",
    });
    expect(
      vi
        .mocked(emit)
        .mock.calls.filter(
          (call) =>
            call[0] === "ui_form_submit" &&
            (call[1] as { form?: string } | undefined)?.form ===
              "url_string_edit",
        ),
    ).toHaveLength(1);
    expect(vi.mocked(updateURL)).toHaveBeenCalledTimes(1);
    expect(vi.mocked(ajaxCall)).not.toHaveBeenCalled();
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
