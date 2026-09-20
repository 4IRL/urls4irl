import {
  createURLTagSuccess,
  hideAndResetCreateURLTagForm,
} from "../create.js";
import { enableClickOnSelectedURLCardToHide } from "../../cards/selection.js";
import { buildTagFilterInDeck } from "../../../tags/tags.js";
import { isTagInUTubTagDeck } from "../../../tags/utils.js";
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
    // vi.clearAllMocks() clears calls but not implementations, so re-assert the
    // default here rather than letting a per-test override leak forward.
    vi.mocked(isTagInUTubTagDeck).mockReturnValue(false);
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

  it("refreshes #TagDeckCount when the tag is new to the UTub deck", () => {
    // Tagging a URL with a tag the UTub has never seen grows the Tag deck's
    // total, so the inline "(n)" beside the Tags title has to follow it.
    document.body.innerHTML =
      URL_CARD_HTML +
      '<span id="TagDeckCount"></span>' +
      '<div id="listTags"><div class="tagFilter" data-utub-tag-id="1"></div></div>';
    vi.mocked(buildTagFilterInDeck).mockReturnValue(
      $(
        '<div class="tagFilter" data-utub-tag-id="99"></div>',
      ) as JQuery<HTMLDivElement>,
    );

    createURLTagSuccess(response, $(".urlRow"), 1);

    expect($("#listTags > .tagFilter").length).toBe(2);
    expect($("#TagDeckCount").text()).toBe("(2)");
  });

  it("leaves #TagDeckCount untouched when the tag is already in the UTub deck", () => {
    // Gating case for the bullet above: an already-in-deck tag only bumps that
    // row's applied count, so the UTub's total is unchanged and the title count
    // must not be rewritten. Without this, dropping the `if` gate around the
    // refresh would go undetected (the file's mock defaults isTagInUTubTagDeck
    // to false, so nothing else here exercises the else branch).
    document.body.innerHTML =
      URL_CARD_HTML +
      '<span id="TagDeckCount">(4)</span>' +
      '<div id="listTags"><div class="tagFilter" data-utub-tag-id="1"></div></div>';
    // Not mockReturnValueOnce: createURLTagSuccess reads isTagInUTubTagDeck
    // twice per call (once inside its log(...) payload, once for the branch), so
    // a single queued value would be consumed by the log and leave the branch on
    // the default. The describe's beforeEach resets this to false.
    vi.mocked(isTagInUTubTagDeck).mockReturnValue(true);

    createURLTagSuccess(response, $(".urlRow"), 1);

    expect(buildTagFilterInDeck).not.toHaveBeenCalled();
    expect($("#TagDeckCount").text()).toBe("(4)");
  });
});
