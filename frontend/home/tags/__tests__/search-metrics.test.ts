import { UI_EVENTS } from "../../../types/metrics-events.js";
import {
  closeTagNameFilter,
  openTagNameFilter,
  resetTagFilter,
  setTagSelectorSearchEventListener,
} from "../search.js";
import {
  TAG_SEARCH_CLOSE_TARGET,
  TAG_SEARCH_OPEN_TARGET,
} from "../../../types/metrics-dim-values.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../logic/tag-search.js", () => ({
  filterTagsByName: vi.fn(() => []),
}));

const $ = window.jQuery;

const FILTER_HTML = `
  <div id="TagDeck">
    <button id="tagNameFilterBtn" aria-expanded="false"></button>
    <button id="tagNameFilterBtnClose" class="hidden"></button>
    <div id="SearchTagWrap">
      <input id="TagNameSearch" type="search" value="" />
    </div>
    <p id="TagSearchNoResults" class="hidden"></p>
    <span id="TagSearchAnnouncement"></span>
    <div id="listTags">
      <div class="tagFilter" data-utub-tag-id="1"><span>Alpha</span></div>
      <div class="tagFilter" data-utub-tag-id="2"><span>Beta</span></div>
    </div>
  </div>
`;

// Module-level _tagSearchOpen flag persists across tests; explicitly reset
// by triggering a blur on the input after attaching the listener.
function resetSearchModuleState(): void {
  setTagSelectorSearchEventListener();
  $("#TagNameSearch").trigger("blur.searchInputEsc");
}

describe("Tag search metrics — UI_TAG_SEARCH_OPEN / UI_TAG_SEARCH_CLOSE", () => {
  beforeEach(() => {
    document.body.innerHTML = FILTER_HTML;
    resetSearchModuleState();
    vi.clearAllMocks();
  });

  afterEach(() => {
    $("#TagNameSearch").trigger("blur.searchInputEsc");
    document.body.innerHTML = "";
  });

  it("emits ui_tag_search_open with target 'tags' when input gains focus", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#TagNameSearch").trigger("focus.searchInputEsc");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_TAG_SEARCH_OPEN,
      target: TAG_SEARCH_OPEN_TARGET.TAGS,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not double-emit when focus fires a second time without a blur between", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#TagNameSearch").trigger("focus.searchInputEsc");
    $("#TagNameSearch").trigger("focus.searchInputEsc");

    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("re-emits ui_tag_search_open after a blur resets the flag", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#TagNameSearch").trigger("focus.searchInputEsc");
    $("#TagNameSearch").trigger("blur.searchInputEsc");
    $("#TagNameSearch").trigger("focus.searchInputEsc");

    expect(emit).toHaveBeenCalledTimes(2);
    expect(emit).toHaveBeenNthCalledWith(1, {
      event: UI_EVENTS.UI_TAG_SEARCH_OPEN,
      target: TAG_SEARCH_OPEN_TARGET.TAGS,
    });
    expect(emit).toHaveBeenNthCalledWith(2, {
      event: UI_EVENTS.UI_TAG_SEARCH_OPEN,
      target: TAG_SEARCH_OPEN_TARGET.TAGS,
    });
  });

  it("emits ui_tag_search_close with target 'tags' when resetTagFilter runs while open", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    $("#TagNameSearch").trigger("focus.searchInputEsc");
    vi.mocked(emit).mockClear();

    resetTagFilter();

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_TAG_SEARCH_CLOSE,
      target: TAG_SEARCH_CLOSE_TARGET.TAGS,
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not emit ui_tag_search_close from resetTagFilter when never focused (init path)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    resetTagFilter();

    expect(emit).not.toHaveBeenCalled();
  });

  it("does not emit on listener setup alone (no init emit)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    // beforeEach already attached the listener and blurred to reset state.
    expect(emit).not.toHaveBeenCalled();
  });

  describe("funnel toggle show/hide", () => {
    it("emits ui_tag_search_open when the funnel is opened (focus is triggered)", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      openTagNameFilter();

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_TAG_SEARCH_OPEN,
        target: TAG_SEARCH_OPEN_TARGET.TAGS,
      });
      expect(emit).toHaveBeenCalledTimes(1);
    });

    it("emits ui_tag_search_close when the funnel is closed", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      openTagNameFilter();
      vi.mocked(emit).mockClear();

      closeTagNameFilter();

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_TAG_SEARCH_CLOSE,
        target: TAG_SEARCH_CLOSE_TARGET.TAGS,
      });
      expect(emit).toHaveBeenCalledTimes(1);
    });

    it("still emits ui_tag_search_close when the input blurred first (X-button race)", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      openTagNameFilter();
      // Clicking the X button blurs the input before the click handler runs,
      // clearing the focus flag — the DOM-state guard must still record the close.
      $("#TagNameSearch").trigger("blur.searchInputEsc");
      vi.mocked(emit).mockClear();

      closeTagNameFilter();

      expect(emit).toHaveBeenCalledWith({
        event: UI_EVENTS.UI_TAG_SEARCH_CLOSE,
        target: TAG_SEARCH_CLOSE_TARGET.TAGS,
      });
      expect(emit).toHaveBeenCalledTimes(1);
    });

    it("does not emit close when the funnel was not open", async () => {
      const { emit } = await import("../../../lib/metrics-client.js");

      closeTagNameFilter();

      expect(emit).not.toHaveBeenCalled();
    });
  });
});
