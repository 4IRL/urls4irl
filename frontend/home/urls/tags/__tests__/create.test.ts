import { hideAndResetCreateURLTagForm } from "../create.js";
import { enableClickOnSelectedURLCardToHide } from "../../cards/selection.js";

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

vi.mock("../../tags/utils.js", () => ({
  isTagInUTubTagDeck: vi.fn(() => false),
}));

vi.mock("../../tags/tags.js", () => ({
  buildTagFilterInDeck: vi.fn(),
}));

vi.mock("../tags.js", () => ({
  setFocusEventListenersOnCreateURLTagInput: vi.fn(),
  createTagBadgeInURL: vi.fn(),
  disableTagRemovalInURLCard: vi.fn(),
  enableTagRemovalInURLCard: vi.fn(),
}));

vi.mock("../../cards/utils.js", () => ({
  disableEditingURLTitle: vi.fn(),
  enableEditingURLTitle: vi.fn(),
}));

vi.mock("../../btns-forms.js", () => ({
  makeTextInput: vi.fn(() =>
    window.jQuery("<div><label></label><input /></div>"),
  ),
  makeSubmitButton: vi.fn(() => window.jQuery("<button></button>")),
  makeCancelButton: vi.fn(() => window.jQuery("<button></button>")),
}));

vi.mock("../../cards/options/tag-btn.js", () => ({
  createAddTagIcon: vi.fn(() => window.jQuery("<i></i>")),
}));

vi.mock("../cards/filtering.js", () => ({
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
