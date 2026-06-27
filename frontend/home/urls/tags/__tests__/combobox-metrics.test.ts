import { createTagComboboxBlock, showTagCombobox } from "../combobox.js";
import { UI_EVENTS } from "../../../../types/metrics-events.js";
import {
  FORM_CANCEL_TRIGGER,
  FORM_SUBMIT_TRIGGER,
  HOME_FORM,
  TAG_SCOPE,
} from "../../../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(() => ({
    done: vi.fn().mockReturnThis(),
    fail: vi.fn().mockReturnThis(),
    always: vi.fn().mockReturnThis(),
  })),
  is429Handled: vi.fn(() => false),
}));

vi.mock("../../cards/selection.js", () => ({
  disableClickOnSelectedURLCardToHide: vi.fn(),
  enableClickOnSelectedURLCardToHide: vi.fn(),
}));

vi.mock("../../cards/utils.js", () => ({
  disableEditingURLString: vi.fn(),
  disableEditingURLTitle: vi.fn(),
  enableEditingURLString: vi.fn(),
  enableEditingURLTitle: vi.fn(),
}));

vi.mock("../../cards/loading.js", () => ({
  setTimeoutAndShowURLCardLoadingIcon: vi.fn(() => 1),
  clearTimeoutIDAndHideLoadingIcon: vi.fn(),
}));

vi.mock("../../cards/get.js", () => ({
  getUpdatedURL: vi.fn(() => Promise.resolve()),
  handleRejectFromGetURL: vi.fn(),
}));

vi.mock("../../cards/options/tag-btn.js", () => ({
  createAddTagIcon: vi.fn(() => window.jQuery("<i></i>")),
}));

vi.mock("../../mobile.js", () => ({ isMobile: vi.fn(() => false) }));

vi.mock("../../../tags/utils.js", () => ({
  isTagInUTubTagDeck: vi.fn(() => false),
}));

vi.mock("../../../tags/tags.js", () => ({
  buildTagFilterInDeck: vi.fn(() => window.jQuery("<div></div>")),
}));

vi.mock("../tags.js", () => ({
  createTagBadgeInURL: vi.fn(() => window.jQuery("<span></span>")),
  createTagDeleteIcon: vi.fn(() => window.jQuery("<svg></svg>")),
  disableTagRemovalInURLCard: vi.fn(),
  enableTagRemovalInURLCard: vi.fn(),
}));

vi.mock("../../cards/filtering.js", () => ({
  updateTagFilterCount: vi.fn(),
  TagCountOperation: { INCREMENT: "increment" },
}));

vi.mock("../../../../lib/jquery-plugins.js", () => ({
  enableTabbableChildElements: vi.fn(),
  disableTabbableChildElements: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({
    urls: [{ utubUrlID: 1, utubUrlTagIDs: [] }],
    tags: [{ id: 1, tagString: "python", tagApplied: 5 }],
  })),
  setState: vi.fn(),
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
  <div class="urlRow" utuburlid="1" urlSelected="true" data-utub-url-tag-ids="">
    <button class="urlTagBtnCreate fourty-p-width"></button>
    <div class="urlBtnAccess"></div>
    <div class="urlStringBtnUpdate"></div>
    <div class="urlBtnDelete"></div>
    <div class="urlBtnCopy"></div>
    <div class="tagBadge"></div>
    <div class="urlTagsContainer"></div>
    <div class="tagsAndTagCreateWrap"></div>
  </div>
`;

function mountCombobox(): JQuery {
  document.body.innerHTML = URL_CARD_HTML;
  const urlCard = $(".urlRow");
  const block = createTagComboboxBlock({
    mode: "url",
    urlCard,
    utubID: 1,
    utubUrlID: 1,
  });
  urlCard.find(".tagsAndTagCreateWrap").append(block);
  urlCard.find(".urlTagComboboxWrap").removeClass("hidden");
  return urlCard;
}

function stageChip(urlCard: JQuery, value: string): void {
  const input = urlCard.find(".urlTagComboboxInput");
  input.val(value).trigger("input");
  vi.runAllTimers();
  input.trigger($.Event("keydown", { key: "Enter" }));
}

beforeEach(() => {
  vi.clearAllMocks();
  vi.useFakeTimers();
});

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("combobox metrics — UI_TAG_CREATE_OPEN", () => {
  it("emits ui_tag_create_open with scope:url when showTagCombobox runs", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const urlCard = mountCombobox();
    const urlTagBtnCreate = urlCard.find(".urlTagBtnCreate");

    showTagCombobox({ urlCard, urlTagBtnCreate });

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_TAG_CREATE_OPEN,
      scope: TAG_SCOPE.URL,
    });
  });
});

describe("combobox metrics — UI_FORM_SUBMIT", () => {
  it("emits ui_form_submit with BUTTON_CLICK when the submit button is clicked", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const urlCard = mountCombobox();
    stageChip(urlCard, "newtag");

    urlCard.find(".urlTagComboboxSubmitBtn").trigger("click");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_FORM_SUBMIT,
      form: HOME_FORM.TAG_CREATE,
      trigger: FORM_SUBMIT_TRIGGER.BUTTON_CLICK,
    });
  });

  it("emits ui_form_submit with ENTER_KEY on the empty-query Enter submit branch", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const urlCard = mountCombobox();
    stageChip(urlCard, "newtag");

    const input = urlCard.find(".urlTagComboboxInput");
    // Empty query + a staged chip + no active option → submit branch.
    input.val("");
    input.trigger($.Event("keydown", { key: "Enter" }));

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_FORM_SUBMIT,
      form: HOME_FORM.TAG_CREATE,
      trigger: FORM_SUBMIT_TRIGGER.ENTER_KEY,
    });
  });
});

describe("combobox metrics — UI_FORM_CANCEL", () => {
  it("emits ui_form_cancel with CANCEL_BUTTON when the big cancel button is clicked", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const urlCard = mountCombobox();
    const urlTagBtnCreate = urlCard.find(".urlTagBtnCreate");

    showTagCombobox({ urlCard, urlTagBtnCreate });
    urlCard.find(".urlTagCancelBigBtnCreate").trigger("click");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_FORM_CANCEL,
      form: HOME_FORM.TAG_CREATE,
      trigger: FORM_CANCEL_TRIGGER.CANCEL_BUTTON,
    });
  });
});
