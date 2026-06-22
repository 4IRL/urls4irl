import {
  createURLTagSuccess,
  hideAndResetCreateURLTagForm,
} from "../create.js";
import { enableClickOnSelectedURLCardToHide } from "../../cards/selection.js";
import { buildTagFilterInDeck } from "../../../tags/tags.js";
import { APP_CONFIG } from "../../../../lib/config.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../cards/selection.js", () => ({
  disableClickOnSelectedURLCardToHide: vi.fn(),
  enableClickOnSelectedURLCardToHide: vi.fn(),
}));

vi.mock("../../cards/loading.js", () => ({
  setTimeoutAndShowURLCardLoadingIcon: vi.fn(() => 1),
  clearTimeoutIDAndHideLoadingIcon: vi.fn(),
}));

vi.mock("../../cards/get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
}));

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [], tags: [] })),
  setState: vi.fn(),
}));

vi.mock("../../../tags/utils.js", () => ({
  isTagInUTubTagDeck: vi.fn(() => false),
}));

vi.mock("../../../tags/tags.js", () => ({
  buildTagFilterInDeck: vi.fn(),
}));

vi.mock("../tags.js", () => ({
  setFocusEventListenersOnCreateURLTagInput: vi.fn(),
  createTagBadgeInURL: vi.fn(),
  disableTagRemovalInURLCard: vi.fn(),
  enableTagRemovalInURLCard: vi.fn(),
}));

vi.mock("../../cards/utils.js", () => ({
  disableEditingURLString: vi.fn(),
  disableEditingURLTitle: vi.fn(),
  enableEditingURLString: vi.fn(),
  enableEditingURLTitle: vi.fn(),
}));

vi.mock("../../../btns-forms.js", () => ({
  makeTextInput: vi.fn(() =>
    window.jQuery("<div><label></label><input /></div>"),
  ),
  makeSubmitButton: vi.fn(() => window.jQuery("<button></button>")),
  makeCancelButton: vi.fn(() => window.jQuery("<button></button>")),
}));

vi.mock("../../cards/options/tag-btn.js", () => ({
  createAddTagIcon: vi.fn(() => window.jQuery("<i></i>")),
}));

vi.mock("../../cards/filtering.js", () => ({
  updateTagFilterCount: vi.fn(),
  TagCountOperation: { INCREMENT: "increment" },
}));

const $ = window.jQuery;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="false">
    <div class="createUrlTagWrap hidden"></div>
    <button class="urlTagBtnCreate fourty-p-width"></button>
    <div class="urlBtnAccess"></div>
    <div class="urlStringBtnUpdate"></div>
    <div class="urlBtnDelete"></div>
    <div class="urlBtnCopy"></div>
    <div class="tagBadge"></div>
  </div>
`;

describe("hideAndResetCreateURLTagForm - selection guard", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does NOT call enableClickOnSelectedURLCardToHide when card is NOT selected", () => {
    document.body.innerHTML = URL_CARD_HTML;
    const urlCard = $(".urlRow");
    urlCard.attr("urlSelected", "false");

    hideAndResetCreateURLTagForm(urlCard);

    expect(enableClickOnSelectedURLCardToHide).not.toHaveBeenCalled();
  });

  it("DOES call enableClickOnSelectedURLCardToHide when card IS selected", () => {
    document.body.innerHTML = URL_CARD_HTML;
    const urlCard = $(".urlRow");
    urlCard.attr("urlSelected", "true");

    hideAndResetCreateURLTagForm(urlCard);

    expect(enableClickOnSelectedURLCardToHide).toHaveBeenCalledWith(urlCard);
  });
});

describe("createURLTagSuccess — at-cap branch", () => {
  const response = {
    status: "Success" as const,
    utubTag: { utubTagID: 99, tagString: "test" },
    utubUrlTagIDs: [99],
    tagCountsInUtub: 1,
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("does NOT disable the newly-built tag filter when below the cap", () => {
    document.body.innerHTML = URL_CARD_HTML;
    const newTag = $("<button class='tagFilter'></button>");
    vi.mocked(buildTagFilterInDeck).mockReturnValue(
      newTag as JQuery<HTMLDivElement>,
    );

    createURLTagSuccess(response, $(".urlRow"), 1);

    expect(newTag.hasClass("disabled")).toBe(false);
  });

  it("disables the newly-built tag filter when the cap is reached", () => {
    document.body.innerHTML = URL_CARD_HTML;
    $(".urlRow").append(
      Array(APP_CONFIG.constants.TAGS_MAX_ON_URLS)
        .fill("<span class='tagFilter selected'></span>")
        .join(""),
    );
    const capTag = $("<button class='tagFilter'></button>");
    vi.mocked(buildTagFilterInDeck).mockReturnValue(
      capTag as JQuery<HTMLDivElement>,
    );

    createURLTagSuccess(response, $(".urlRow"), 1);

    expect(capTag.hasClass("disabled")).toBe(true);
  });
});
