import { UI_EVENTS } from "../../../lib/metrics-events.js";
import {
  closeURLSearchAndEraseInput,
  disableURLSearch,
  setURLSearchEventListener,
} from "../search.js";

const { mockMetricsClient } = await vi.hoisted(
  async () => await import("../../../__tests__/helpers/mock-metrics-client.js"),
);

vi.mock("../../../lib/metrics-client.js", () => mockMetricsClient());

vi.mock("../../../logic/url-search.js", () => ({
  filterURLsBySearchTerm: vi.fn(() => []),
}));

vi.mock("../../../store/app-store.js", () => ({
  getState: vi.fn(() => ({ isCurrentUserOwner: false })),
  setState: vi.fn(),
}));

const $ = window.jQuery;

const SEARCH_HTML = `
  <button id="URLSearchFilterIcon"></button>
  <button id="URLSearchFilterIconClose" class="hidden"></button>
  <div id="SearchURLWrap" class="hidden"></div>
  <input id="URLContentSearch" value="" />
  <div id="UTubDescriptionSubheaderWrap"></div>
  <button id="URLDeckSubheaderCreateDescription"></button>
  <div id="URLDeckSubheader"></div>
  <p id="URLDeckNoDescription" class="hidden"></p>
  <p id="URLSearchNoResults" class="hidden"></p>
  <span id="URLSearchAnnouncement"></span>
  <div id="listURLs"></div>
`;

describe("URL search metrics — UI_SEARCH_OPEN / UI_SEARCH_CLOSE", () => {
  beforeEach(() => {
    document.body.innerHTML = SEARCH_HTML;
    vi.clearAllMocks();
  });

  afterEach(() => {
    document.body.innerHTML = "";
  });

  it("emits ui_search_open with target 'urls' when the search icon is clicked", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setURLSearchEventListener();
    $("#URLSearchFilterIcon").trigger("click.urlSearchInputShow");

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_SEARCH_OPEN,
      target: "urls",
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("emits ui_search_close with target 'urls' when closing while panel is open (visible-flex)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setURLSearchEventListener();
    $("#URLSearchFilterIcon").trigger("click.urlSearchInputShow");
    vi.mocked(emit).mockClear();

    closeURLSearchAndEraseInput();

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_SEARCH_CLOSE,
      target: "urls",
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not emit ui_search_close when called while the panel is hidden", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setURLSearchEventListener();

    closeURLSearchAndEraseInput();

    expect(emit).not.toHaveBeenCalled();
  });

  it("does not emit ui_search_close from disableURLSearch when panel is not visible (UTub deselect)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setURLSearchEventListener();

    disableURLSearch();

    expect(emit).not.toHaveBeenCalled();
  });

  it("emits ui_search_close exactly once when ESC closes the input while panel is open", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setURLSearchEventListener();
    $("#URLSearchFilterIcon").trigger("click.urlSearchInputShow");
    vi.mocked(emit).mockClear();

    const escEvent = $.Event("keydown.searchInputEsc", { key: "Escape" });
    $("#URLContentSearch").trigger("focus.searchInputEsc");
    $("#URLContentSearch").trigger(escEvent);

    expect(emit).toHaveBeenCalledWith({
      event: UI_EVENTS.UI_SEARCH_CLOSE,
      target: "urls",
    });
    expect(emit).toHaveBeenCalledTimes(1);
  });

  it("does not emit on listener setup alone (no init emit)", async () => {
    const { emit } = await import("../../../lib/metrics-client.js");

    setURLSearchEventListener();

    expect(emit).not.toHaveBeenCalled();
  });
});
