import { submitStagedTagsSuccess, submitStagedTagsFail } from "../combobox.js";
import { UI_EVENTS } from "../../../../types/metrics-events.js";
import { is429Handled } from "../../../../lib/ajax.js";

const { mockMetricsClient } = await vi.hoisted(
  async () =>
    await import("../../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../../lib/ajax.js", () => ({
  ajaxCall: vi.fn(),
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
  createTagBadgeInURL: vi.fn(() =>
    window.jQuery('<span class="tagBadge"></span>'),
  ),
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

const storeState: {
  urls: { utubUrlID: number; utubUrlTagIDs: number[] }[];
  tags: { id: number; tagString: string; tagApplied: number }[];
} = { urls: [], tags: [] };

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => storeState),
  setState: vi.fn((partial: Partial<typeof storeState>) => {
    Object.assign(storeState, partial);
  }),
}));

const $ = window.jQuery;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" urlSelected="true" data-utub-url-tag-ids="">
    <button class="urlTagBtnCreate fourty-p-width"></button>
    <div class="urlBtnAccess"></div>
    <div class="urlStringBtnUpdate"></div>
    <div class="urlBtnDelete"></div>
    <div class="urlBtnCopy"></div>
    <div class="urlTagsContainer"></div>
    <div class="urlTagComboboxWrap">
      <div class="urlTagCombobox"></div>
      <div class="urlTagListbox"></div>
      <div class="urlTagComboboxMsg"></div>
    </div>
  </div>
  <div id="unselectAllTagFilters"></div>
  <div id="listTags"></div>
  <div id="utubTagBtnUpdateAllOpen"></div>
`;

beforeEach(() => {
  document.body.innerHTML = URL_CARD_HTML;
  storeState.urls = [{ utubUrlID: 1, utubUrlTagIDs: [] }];
  storeState.tags = [];
  vi.clearAllMocks();
});

afterEach(() => {
  document.body.innerHTML = "";
});

describe("submitStagedTagsSuccess — happy path", () => {
  const response = {
    status: "Success" as const,
    utubUrlTagIDs: [7, 8],
    appliedTags: [
      { id: 7, tagString: "python", tagApplied: 3 },
      { id: 8, tagString: "backend", tagApplied: 1 },
    ],
  };

  it("merges applied tags into the store, appends badges, and emits UI_TAG_APPLY", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const urlCard = $(".urlRow");

    submitStagedTagsSuccess({ response, urlCard, utubID: 1 });

    expect(emit).toHaveBeenCalledWith({ event: UI_EVENTS.UI_TAG_APPLY });
    expect(storeState.tags).toEqual(response.appliedTags);
    expect(storeState.urls[0].utubUrlTagIDs).toEqual([7, 8]);
    expect(urlCard.find(".urlTagsContainer .tagBadge").length).toBe(2);
    expect(urlCard.attr("data-utub-url-tag-ids")).toBe("7,8");
  });

  it("does NOT emit UI_TAG_APPLY when appliedTags is empty (no-op batch)", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const urlCard = $(".urlRow");

    submitStagedTagsSuccess({
      response: {
        status: "Success" as const,
        utubUrlTagIDs: [],
        appliedTags: [],
      },
      urlCard,
      utubID: 1,
    });

    expect(emit).not.toHaveBeenCalledWith({ event: UI_EVENTS.UI_TAG_APPLY });
    expect(urlCard.find(".urlTagsContainer .tagBadge").length).toBe(0);
  });
});

describe("submitStagedTagsFail — sad paths", () => {
  it("renders an inline error and does NOT emit UI_TAG_APPLY on 400", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");
    const urlCard = $(".urlRow");

    submitStagedTagsFail({
      xhr: {
        status: 400,
        responseJSON: { errors: { tagStrings: ["Too many tags"] } },
      } as unknown as JQuery.jqXHR,
      urlCard,
    });

    expect(urlCard.find(".urlTagComboboxMsg").text()).toBe("Too many tags");
    expect(urlCard.find(".urlTagComboboxMsg").hasClass("warn")).toBe(true);
    expect(emit).not.toHaveBeenCalledWith({ event: UI_EVENTS.UI_TAG_APPLY });
  });

  it("short-circuits when is429Handled returns true", () => {
    vi.mocked(is429Handled).mockReturnValueOnce(true);
    const urlCard = $(".urlRow");

    submitStagedTagsFail({
      xhr: { status: 429 } as unknown as JQuery.jqXHR,
      urlCard,
    });

    expect(urlCard.find(".urlTagComboboxMsg").text()).toBe("");
  });
});
