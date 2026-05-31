import { UI_EVENTS } from "../../../types/metrics-events.js";
import {
  initUnselectAllTags,
  enableUnselectAllButtonAfterTagFilterApplied,
} from "../unselect-all.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../tags.js", () => ({
  toggleTagFilterSelected: vi.fn(),
}));

vi.mock("../../urls/cards/filtering.js", () => ({
  updateURLsAndTagSubheaderWhenTagSelected: vi.fn(),
}));

vi.mock("../../../store/app-store.js", () => ({
  setState: vi.fn(),
}));

const $ = window.jQuery;

const UNSELECT_HTML = `
  <button id="unselectAllTagFilters"></button>
  <div id="TagDeckSubheader"></div>
  <div class="tagFilter" data-utub-tag-id="1"></div>
  <div class="tagFilter" data-utub-tag-id="2"></div>
  <div class="tagFilter" data-utub-tag-id="3"></div>
`;

describe("unselect-all metrics — UI_TAG_FILTER_TOGGLE", () => {
  beforeEach(() => {
    document.body.innerHTML = UNSELECT_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_tag_filter_toggle exactly once when unselect-all is clicked (not once per filter)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    initUnselectAllTags();
    $("#unselectAllTagFilters").trigger("click.unselectAllTags");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_TAG_FILTER_TOGGLE,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("emits ui_tag_filter_toggle once when the unselect path runs via enableUnselectAllButtonAfterTagFilterApplied", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    enableUnselectAllButtonAfterTagFilterApplied();
    $("#unselectAllTagFilters").trigger("click.unselectAllTags");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_TAG_FILTER_TOGGLE,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });
});
