import { createMockJqXHRChainable } from "../../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../../lib/ajax.js";
import { createURLTag, showCreateURLTagForm } from "../create.js";

vi.mock("../../../../lib/metrics-client.js", () => ({
  emit: vi.fn(),
  flush: vi.fn().mockResolvedValue(undefined),
  initMetricsClient: vi.fn(),
  resetMetricsClient: vi.fn(),
}));

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../cards/loading.js", () => ({
  setTimeoutAndShowURLCardLoadingIcon: vi.fn(() => 1),
  clearTimeoutIDAndHideLoadingIcon: vi.fn(),
}));

vi.mock("../../cards/get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
}));

vi.mock("../../cards/selection.js", () => ({
  disableClickOnSelectedURLCardToHide: vi.fn(),
  enableClickOnSelectedURLCardToHide: vi.fn(),
}));

vi.mock("../../cards/utils.js", () => ({
  disableEditingURLTitle: vi.fn(),
  enableEditingURLTitle: vi.fn(),
}));

vi.mock("../../mobile.js", () => ({ isMobile: vi.fn(() => false) }));

vi.mock("../../tags/utils.js", () => ({
  isTagInUTubTagDeck: vi.fn(() => false),
}));

vi.mock("../../tags/tags.js", () => ({
  buildTagFilterInDeck: vi.fn(() => window.jQuery("<div></div>")),
}));

vi.mock("../tags.js", () => ({
  setFocusEventListenersOnCreateURLTagInput: vi.fn(),
  createTagBadgeInURL: vi.fn(() => window.jQuery("<span></span>")),
  disableTagRemovalInURLCard: vi.fn(),
  enableTagRemovalInURLCard: vi.fn(),
}));

vi.mock("../../cards/options/tag-btn.js", () => ({
  createAddTagIcon: vi.fn(() => window.jQuery("<i></i>")),
}));

vi.mock("../../cards/filtering.js", () => ({
  updateTagFilterCount: vi.fn(),
  TagCountOperation: { INCREMENT: "increment" },
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [], tags: [] })),
  setState: vi.fn(),
}));

vi.mock("../../../../lib/jquery-plugins.js", () => ({
  enableTabbableChildElements: vi.fn(),
  disableTabbableChildElements: vi.fn(),
}));

vi.mock("../../../../lib/globals.js", async () => {
  const actual = await vi.importActual<
    typeof import("../../../../lib/globals.js")
  >("../../../../lib/globals.js");
  return {
    ...actual,
    bootstrap: {
      Tooltip: { getInstance: vi.fn(() => null) },
    } as unknown as typeof window.bootstrap,
  };
});

const $ = window.jQuery;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="false">
    <div class="createUrlTagWrap hidden"></div>
    <button class="urlTagBtnCreate fourty-p-width"></button>
    <div class="urlBtnAccess"></div>
    <div class="urlStringBtnUpdate"></div>
    <div class="urlBtnDelete"></div>
    <div class="urlBtnCopy"></div>
    <div class="urlTagsContainer"></div>
    <div class="tagBadge"></div>
  </div>
  <div id="unselectAllTagFilters"></div>
  <div id="listTags"></div>
  <div id="utubTagBtnUpdateAllOpen"></div>
`;

describe("urls/tags create metrics — UI_TAG_CREATE_OPEN + UI_TAG_APPLY", () => {
  beforeEach(() => {
    document.body.innerHTML = URL_CARD_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_tag_create_open with scope:url when showCreateURLTagForm runs", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    const urlCard = $(".urlRow");
    const urlTagBtnCreate = urlCard.find(".urlTagBtnCreate");

    showCreateURLTagForm(urlCard, urlTagBtnCreate);

    expect(emit).toHaveBeenCalledWith("ui_tag_create_open", { scope: "url" });
  });

  it("emits ui_tag_apply when the AJAX success path runs createURLTagSuccess", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    const urlCard = $(".urlRow");
    const utubUrlTagResponse = {
      utubTag: { utubTagID: 7, tagString: "important" },
      utubUrlTagIDs: [7],
      tagCountsInUtub: 1,
    };

    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        done: (callback: unknown) => {
          (callback as (...args: unknown[]) => unknown)(
            utubUrlTagResponse,
            "success",
            { status: 200 },
          );
        },
      }),
    );

    const fakeInput = $('<input type="text" />').val("important");
    await createURLTag(fakeInput, urlCard, 1);

    expect(emit).toHaveBeenCalledWith("ui_tag_apply");
  });

  it("does not emit ui_tag_apply when the AJAX call fails", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    const urlCard = $(".urlRow");

    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        fail: (callback: unknown) => {
          (callback as (xhr: unknown) => unknown)({
            status: 400,
            responseJSON: { errors: { tagString: ["bad"] } },
          });
        },
      }),
    );

    const fakeInput = $('<input type="text" />').val("bad-tag");
    await createURLTag(fakeInput, urlCard, 1);

    expect(emit).not.toHaveBeenCalledWith("ui_tag_apply");
  });
});
