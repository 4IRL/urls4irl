import { UI_EVENTS } from "../../../../lib/metrics-events.js";
import { createMockJqXHRChainable } from "../../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../../lib/ajax.js";
import { updateURL, showUpdateURLStringForm } from "../update-string.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../../lib/globals.js", async () => {
  const jquery = (await import("jquery")).default;
  const tooltipInstance = {
    setContent: vi.fn(),
    show: vi.fn(),
    hide: vi.fn(),
    enable: vi.fn(),
    disable: vi.fn(),
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
    getInputValue: (input: string | JQuery) => {
      const element = typeof input === "string" ? jquery(input) : input;
      return element.val() as string;
    },
  };
});

vi.mock("../../url-context.js", () => ({
  isURLSearchActive: vi.fn(() => false),
  getActiveTagCount: vi.fn(() => 0),
}));

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../loading.js", () => ({
  setTimeoutAndShowURLCardLoadingIcon: vi.fn(() => 1),
  clearTimeoutIDAndHideLoadingIcon: vi.fn(),
}));

vi.mock("../get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
}));

vi.mock("../selection.js", () => ({
  disableClickOnSelectedURLCardToHide: vi.fn(),
  enableClickOnSelectedURLCardToHide: vi.fn(),
}));

vi.mock("../options/edit-string-btn.js", () => ({
  createEditURLIcon: vi.fn(() => window.jQuery("<i></i>")),
}));

vi.mock("../../tags/tags.js", () => ({
  disableTagRemovalInURLCard: vi.fn(),
  enableTagRemovalInURLCard: vi.fn(),
}));

vi.mock("../../../mobile.js", () => ({
  isMobile: vi.fn(() => false),
}));

vi.mock("../../../btns-forms.js", () => ({
  highlightInput: vi.fn(),
  emitValidationError: vi.fn(),
}));

vi.mock("../conflict-handler.js", () => ({
  checkForStaleDataOn409: vi.fn(),
}));

vi.mock("../access.js", () => ({
  accessLink: vi.fn(),
}));

vi.mock("../copy.js", () => ({
  copyURLString: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="false">
    <a class="urlString" href="https://old.example.com">https://old.example.com</a>
    <button class="urlBtnAccess"></button>
    <button class="goToUrlIcon"></button>
    <button class="urlBtnCopy"></button>
    <div class="updateUrlStringWrap hidden">
      <input class="urlStringUpdate" value="https://new.example.com" />
      <div class="urlStringUpdate-error"></div>
    </div>
  </div>
`;

describe("update-string metrics — UI_URL_STRING_EDIT_OPEN", () => {
  beforeEach(() => {
    document.body.innerHTML = URL_CARD_HTML;
    vi.clearAllMocks();
  });

  it("emits ui_url_string_edit_open at the top of showUpdateURLStringForm", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    const urlCard = $(".urlRow");
    const urlStringBtnUpdate = $(
      '<button class="urlStringBtnUpdate fourty-p-width"></button>',
    );
    urlCard.append(urlStringBtnUpdate);

    showUpdateURLStringForm(urlCard, urlStringBtnUpdate);

    expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_URL_STRING_EDIT_OPEN);
  });
});

describe("update-string metrics — UI_URL_ACCESS via updateURLSuccess rebinds", () => {
  beforeEach(() => {
    document.body.innerHTML = URL_CARD_HTML;
    vi.clearAllMocks();
  });

  async function triggerSuccessfulUpdate(): Promise<JQuery> {
    const urlCard = $(".urlRow");
    const urlStringInput = urlCard.find(".urlStringUpdate");

    const response = {
      URL: {
        utubUrlID: 1,
        urlString: "https://new.example.com",
        urlTitle: "New",
        urlTags: [],
      },
    };

    const chainable = createMockJqXHRChainable({
      done: (callback: unknown) =>
        (callback as (...args: unknown[]) => void)(response, "success", {
          status: 200,
        }),
    });
    vi.mocked(ajaxCall).mockReturnValue(chainable);

    await updateURL(urlStringInput, urlCard, 1);
    return urlCard;
  }

  it("rebound .urlBtnAccess click emits ui_url_access with trigger 'main_button'", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../url-context.js"
    );
    vi.mocked(isURLSearchActive).mockReturnValue(false);
    vi.mocked(getActiveTagCount).mockReturnValue(0);

    const urlCard = await triggerSuccessfulUpdate();
    vi.mocked(emit).mockClear();

    urlCard.find(".urlBtnAccess").trigger("click");

    expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_URL_ACCESS, {
      trigger: "main_button",
      search_active: "false",
      active_tag_count: 0,
    });
  });

  it("rebound .goToUrlIcon click emits ui_url_access with trigger 'corner_button'", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../url-context.js"
    );
    vi.mocked(isURLSearchActive).mockReturnValue(false);
    vi.mocked(getActiveTagCount).mockReturnValue(0);

    const urlCard = await triggerSuccessfulUpdate();
    vi.mocked(emit).mockClear();

    urlCard.find(".goToUrlIcon").trigger("click");

    expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_URL_ACCESS, {
      trigger: "corner_button",
      search_active: "false",
      active_tag_count: 0,
    });
  });

  it("rebound click dims are read AT CLICK TIME (not at updateURLSuccess time)", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const { isURLSearchActive, getActiveTagCount } = await import(
      "../../url-context.js"
    );

    // Dims at updateURLSuccess time are different from click time.
    vi.mocked(isURLSearchActive).mockReturnValue(false);
    vi.mocked(getActiveTagCount).mockReturnValue(0);

    const urlCard = await triggerSuccessfulUpdate();
    vi.mocked(emit).mockClear();

    // Change values BEFORE click.
    vi.mocked(isURLSearchActive).mockReturnValue(true);
    vi.mocked(getActiveTagCount).mockReturnValue(7);

    urlCard.find(".urlBtnAccess").trigger("click");

    expect(emit).toHaveBeenCalledWith(UI_EVENTS.UI_URL_ACCESS, {
      trigger: "main_button",
      search_active: "true",
      active_tag_count: 7,
    });
  });
});
