import { toggleTagFilterSelected, buildTagFilterInDeck } from "../tags.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../delete.js", () => ({ deleteUTubTagShowModal: vi.fn() }));

vi.mock("../unselect-all.js", () => ({
  enableUnselectAllButtonAfterTagFilterApplied: vi.fn(),
  disableUnselectAllButtonAfterTagFilterRemoved: vi.fn(),
}));

vi.mock("../../urls/cards/filtering.js", () => ({
  updateURLsAndTagSubheaderWhenTagSelected: vi.fn(),
}));

vi.mock("../../../store/app-store.js", () => ({
  setState: vi.fn(),
}));

const $ = window.jQuery;

describe("tags metrics — UI_TAG_FILTER_TOGGLE", () => {
  beforeEach(() => {
    document.body.innerHTML = "";
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_tag_filter_toggle when called with an unselected filter", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    const filter = $('<div class="tagFilter unselected"></div>');
    document.body.append(filter[0]);

    toggleTagFilterSelected(filter);

    expect(emit).toHaveBeenCalledWith("ui_tag_filter_toggle");
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("emits ui_tag_filter_toggle when called with a selected filter", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    const filter = $(
      '<div class="tagFilter selected" data-utub-tag-id="1"></div>',
    );
    document.body.append(filter[0]);

    toggleTagFilterSelected(filter);

    expect(emit).toHaveBeenCalledWith("ui_tag_filter_toggle");
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("emits ui_tag_filter_toggle once per click via the bound click handler", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    const tag = buildTagFilterInDeck(1, 10, "my-tag");
    document.body.append(tag[0]);

    tag.trigger("click.tagFilterSelected");

    expect(emit).toHaveBeenCalledWith("ui_tag_filter_toggle");
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("emits exactly once when toggleTagFilterSelected is called multiple times across different filters", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    const firstFilter = $(
      '<div class="tagFilter unselected" data-utub-tag-id="1"></div>',
    );
    const secondFilter = $(
      '<div class="tagFilter unselected" data-utub-tag-id="2"></div>',
    );
    document.body.append(firstFilter[0]);
    document.body.append(secondFilter[0]);

    toggleTagFilterSelected(firstFilter);
    toggleTagFilterSelected(secondFilter);

    expect(emit).toHaveBeenCalledTimes(2);
    expect(emit).toHaveBeenNthCalledWith(1, "ui_tag_filter_toggle");
    expect(emit).toHaveBeenNthCalledWith(2, "ui_tag_filter_toggle");
  });
});
