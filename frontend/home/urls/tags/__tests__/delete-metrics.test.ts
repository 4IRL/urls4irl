import { createMockJqXHRChainable } from "../../../../__tests__/helpers/mock-jquery.js";
import { ajaxCall } from "../../../../lib/ajax.js";
import { deleteURLTag } from "../delete.js";

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

vi.mock("../tags.js", () => ({
  isTagInURL: vi.fn(() => true),
}));

vi.mock("../../cards/filtering.js", () => ({
  updateTagFilterCount: vi.fn(),
  TagCountOperation: { DECREMENT: "decrement" },
  updateTagFilteringOnURLOrURLTagDeletion: vi.fn(),
}));

vi.mock("../../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ urls: [], tags: [] })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const URL_CARD_HTML = `
  <div class="urlRow" utuburlid="1" data-utub-url-tag-ids="7">
    <span class="tagBadge" data-utub-tag-id="7"></span>
  </div>
`;

describe("urls/tags delete metrics — UI_TAG_REMOVE", () => {
  beforeEach(() => {
    document.body.innerHTML = URL_CARD_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_tag_remove when the AJAX success path runs deleteURLTagSuccess", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    const urlCard = $(".urlRow");
    const tagBadge = urlCard.find(".tagBadge");
    const response = {
      utubTag: { utubTagID: 7, tagString: "important" },
      utubUrlTagIDs: [],
      tagCountsInUtub: 0,
    };

    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        done: (callback: unknown) => {
          (callback as (...args: unknown[]) => unknown)(response, "success", {
            status: 200,
          });
        },
      }),
    );

    await deleteURLTag(7, tagBadge, urlCard, 1);

    expect(emit).toHaveBeenCalledWith("ui_tag_remove");
  });

  it("does not emit ui_tag_remove when the AJAX call fails", async () => {
    const { emit } = await import("../../../../lib/metrics-client.js");

    const urlCard = $(".urlRow");
    const tagBadge = urlCard.find(".tagBadge");

    vi.mocked(ajaxCall).mockReturnValue(
      createMockJqXHRChainable({
        fail: (callback: unknown) => {
          (callback as (xhr: unknown) => unknown)({ status: 500 });
        },
      }),
    );

    await deleteURLTag(7, tagBadge, urlCard, 1);

    expect(emit).not.toHaveBeenCalledWith("ui_tag_remove");
  });
});
